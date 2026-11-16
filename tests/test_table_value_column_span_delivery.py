"""回放 gs-008 参数表片段，校验已登记 Word 的数值列及交付质量门禁。"""

import json
from io import BytesIO
from unittest import TestCase
from uuid import uuid4
from zipfile import ZipFile, ZipInfo

from docx import Document

from app.domains.document_jobs.base_quality import current_base
from app.services.tables.evidence import read_table_evidence
from tests.document_job_list_query_v2_publication_fixtures import V2PublicationFixture
from tests.test_fastapi_jobs_backend import build_auth_header
from tests.test_table_value_column_span import _CODE, _GS008_ROWS


_CORRECTED_ROWS = _GS008_ROWS.replace(
    "<td colspan='2'>±5</td>", "<td></td><td>±5</td>",
).replace(
    "<td colspan='3'>±100</td>", "<td></td><td></td><td>±100</td>",
)


def _gs008_package(rows: str) -> bytes:
    package = BytesIO()
    blocks = [{"type": "table", "html": f"<table>{rows}</table>", "page_idx": 0, "bbox": [40, 150, 550, 430]}]
    layout = {"pdf_info": [{"page_idx": 0, "page_size": [600, 800]}]}
    with ZipFile(package, "w") as archive:
        archive.writestr(ZipInfo("content_list_v2.json"), json.dumps(blocks, ensure_ascii=False))
        archive.writestr(ZipInfo("middle.json"), json.dumps(layout))
    return package.getvalue()


def _word_value_columns(table):
    headings = [cell.text for cell in table.rows[0].cells]
    indices = [headings.index(label) for label in ("MIN", "TYP", "MAX", "UNIT")]
    # Word 合并单元格会出现在它覆盖的每个格位，grid_span 仍是实际写入的跨度。
    return [tuple((cells[index].text, cells[index].grid_span) for index in indices)
            for cells in (row.cells for row in table.rows[2:])]


class TableValueColumnSpanDeliveryTests(V2PublicationFixture, TestCase):
    def _render_and_download(self, execution, job, client, headers):
        result = execution.execute_job(job.id)
        self.assertEqual((result.status, result.stage), ("succeeded", "completed"), result.error_message)
        authorization = client.get(f"/api/v1/document-jobs/{job.id}/download-url", headers=headers)
        self.assertEqual(authorization.status_code, 200, authorization.text)
        ticket = authorization.json()
        self.assertEqual(ticket["classification"], "internal_only")
        download = client.get(ticket["download_url"])
        self.assertEqual(download.status_code, 200, download.text)
        table, = Document(BytesIO(download.content)).tables
        return result, table, ticket

    def _span_severities(self, runtime, result):
        file = runtime.document_file_repository.get_document_file(result.result_file_id)
        self.assertIsNotNone(file)
        table, = read_table_evidence(file.metadata["table_evidence"]).tables
        return [flag.severity for flag in table.flags if flag.producer == "table_validator" and flag.code == _CODE]

    def test_gs008_default_gate_keeps_spanning_values_and_requires_confirmation(self) -> None:
        with self.runtime(source_package=_gs008_package(_GS008_ROWS)) as (
            runtime, execution, _, job, _, client, headers,
        ):
            runtime.settings.document_publication_enabled = True
            result, table, ticket = self._render_and_download(execution, job, client, headers)
            self.assertEqual(ticket["warning_code"], "document_unreviewed_not_deliverable")
            self.assertEqual(_word_value_columns(table), [
                (("±5", 2), ("±5", 2), ("±75", 1), ("μV", 1)),
                (("±100", 3), ("±100", 3), ("±100", 3), ("μV", 1)),
            ])
            self.assertEqual(self._span_severities(runtime, result), ["warning", "warning"])
            self.assertEqual(result.quality_status, "pending")
            base = current_base(result)
            self.assertIsNotNone(base)
            self.assertEqual((base.quality_status, base.counts.blocker_count), ("pending", 0))
            self.assertIn(_CODE, base.warning_codes)

            url = f"/api/v1/document-jobs/{job.id}"
            review = client.get(f"{url}/review", headers=headers)
            self.assertEqual(review.status_code, 200, review.text)
            review_source = review.json()["source"]
            del review_source["ir_file_id"]
            approval = client.patch(f"{url}/review", headers=headers, json={
                "status": "approved",
                "expected_source": review_source,
            })
            self.assertEqual(approval.status_code, 409, approval.text)
            self.assertEqual(approval.json()["error"]["reason_code"], "table_semantics_confirmation_required")

            admin = build_auth_header(client, username="admin", password="admin-pass")
            publications = client.get(f"{url}/publications", headers=admin)
            self.assertEqual(publications.status_code, 200, publications.text)
            publication = client.post(f"{url}/publish", headers=admin, json={
                "request_id": str(uuid4()),
                "note": "尝试发布 gs-008",
                "expected_source": publications.json()["expected_source"],
            })
            self.assertEqual(publication.status_code, 409, publication.text)
            self.assertEqual(publication.json()["error"]["reason_code"], "publication_quality_pending")

    def test_gs008_corrected_values_occupy_only_their_source_columns(self) -> None:
        with self.runtime(source_package=_gs008_package(_CORRECTED_ROWS)) as (
            runtime, execution, _, job, _, client, headers,
        ):
            result, table, _ = self._render_and_download(execution, job, client, headers)
            self.assertEqual(_word_value_columns(table), [
                (("", 1), ("±5", 1), ("±75", 1), ("μV", 1)),
                (("", 1), ("", 1), ("±100", 1), ("μV", 1)),
            ])
            self.assertEqual(self._span_severities(runtime, result), [])
