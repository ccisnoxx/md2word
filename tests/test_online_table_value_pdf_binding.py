"""通过正式 Worker、Word 实物和交付 API 验证线上原排版参数列核定。"""

from contextlib import contextmanager, nullcontext
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from os import getenv
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from docx import Document

from app.domains.document_jobs.base_quality import current_base
from app.domains.document_jobs.table_evidence import verify_report
from app.services.document_ir.pdf_value_column_observer import observe_pdf_value_column_page
from app.services.preview.models import PreviewPolicy
from tests.document_job_list_query_v2_publication_fixtures import RecordingPreviewProvider, V2PublicationFixture
from tests.document_job_use_case_support import replace_dependency
from tests.test_fastapi_jobs_backend import TestClient, build_auth_header, create_app
from tests.test_pdf_value_column_observer import make_pdf
from tests.test_table_value_pdf_binding_poppler import _ruled_table_package


@skipUnless(all(which(tool) for tool in ("pdfinfo", "pdftotext", "pdftocairo", "pdftohtml")), "需要实际 Poppler")
class OnlineTableValuePdfBindingTests(V2PublicationFixture, TestCase):
    @contextmanager
    def worker_case(self, package: bytes, pdf: bytes, *, filename: str = "source.pdf", kind: str = "file",
                    companies: frozenset[tuple[str, str]] = frozenset({("tenant_default", "company_default")}),
                    echoed_data_id: bool = True, raw_metadata: dict | None = None):
        with TemporaryDirectory(prefix="online-table-value-") as directory:
            runtime = self._build_runtime(Path(directory), kind)
            runtime.settings.document_table_value_pdf_binding_enabled = True
            runtime.settings.document_table_value_pdf_binding_company_allowlist = companies
            runtime.settings.document_publication_enabled = True
            execution = runtime.document_job_execution_service
            mineru = execution.fake_mineru_client
            mineru.result_zip_bytes = package
            upload = mineru.upload_files_batch

            def accept_upload(paths, **kwargs):
                self.assertEqual(Path(paths[0]).read_bytes(), pdf)
                mineru.query_data_id = kwargs["task_uuids"][0] if echoed_data_id else None
                return upload(paths, **kwargs)

            def register_result(**kwargs):
                if kwargs["file_type"] == "mineru_raw_result":
                    kwargs["metadata"] = {**kwargs["metadata"], **raw_metadata}
                return register(**kwargs)

            preview = execution.rendering.results.word_preview_service
            preview.provider = RecordingPreviewProvider()
            preview.audit_service = runtime.audit_service
            replace_dependency(runtime.document_job_use_cases, "audit_service", runtime.audit_service)
            replace_dependency(runtime.document_job_use_cases, "word_preview_service", preview)
            register = runtime.file_upload_service.register_generated_content
            registration = (patch.object(runtime.file_upload_service, "register_generated_content", side_effect=register_result)
                            if raw_metadata is not None else nullcontext())
            with (
                patch.object(mineru, "upload_files_batch", side_effect=accept_upload),
                registration,
                TestClient(create_app(runtime)) as client,
            ):
                owner = build_auth_header(client)
                admin = build_auth_header(client, username="admin", password="admin-pass")
                source = self._upload_source_pdf(client, owner, filename=filename, pdf_content=pdf)
                self.assertEqual(source["checksum_sha256"], "sha256:" + sha256(pdf).hexdigest())
                # 仅暂停首次渲染以安装现有发布夹具的资源版本，正式 Worker 已完成解析和 IR 登记。
                with patch.object(execution.rendering, "render_and_save_word", side_effect=lambda job, **_: job):
                    created = client.post("/api/v1/document-jobs", headers=owner, json={
                        "source_file_id": source["id"], "translation_mode": "direct", "document_language": "en",
                    })
                self.assertEqual(created.status_code, 201, created.text)
                job = runtime.document_job_repository.get_document_job(created.json()["job_id"])
                if job.status == "failed" and raw_metadata is not None:
                    yield runtime, execution, job, client, owner, admin
                    return
                self.assertEqual((job.status, job.stage), ("running", "rendering"), job.error_message)
                job = self.install_publication_resources(runtime, execution, job)
                preview_policy = PreviewPolicy(backend="sandboxed", required=True, render_pages=True)
                runtime.document_job_repository.update_document_job(job.id, request_snapshot={
                    **job.request_snapshot, "word_preview": preview_policy.model_dump(mode="json"),
                })
                result = execution.execute_job(job.id)
                self.assertEqual((result.status, result.stage), ("succeeded", "completed"), result.error_message)
                raw = runtime.document_file_repository.get_document_file(result.mineru_raw_result_file_id)
                self.assertEqual(raw.checksum_sha256, "sha256:" + sha256(package).hexdigest())
                self.assertEqual(runtime.file_upload_service.read_file_content(raw), package)
                yield runtime, execution, result, client, owner, admin

    def read_verified_word(self, runtime, job):
        file = runtime.document_file_repository.get_document_file(job.result_file_id)
        report = verify_report(job, file, file_repository=runtime.document_file_repository,
                               file_service=runtime.file_upload_service, job_repository=runtime.document_job_repository)
        self.assertIsNotNone(report)
        word = runtime.file_upload_service.read_file_content(file)
        return report, word

    def check_blocked_delivery(self, client, owner, admin, job_id: str) -> None:
        url = f"/api/v1/document-jobs/{job_id}"
        ticket = client.get(f"{url}/download-url", headers=owner)
        self.assertEqual(ticket.status_code, 200, ticket.text)
        self.assertEqual(ticket.json()["classification"], "internal_only")
        self.assertEqual(ticket.json()["warning_code"], "quality_blocked_not_deliverable")
        approval = client.patch(f"{url}/review", headers=owner, json={
            "status": "approved", "expected_source": self.review_source(client, owner, url),
        })
        self.assertEqual(approval.status_code, 409, approval.text)
        self.assertEqual(approval.json()["error"]["reason_code"], "review_quality_blocked")
        result = self.try_publish(client, admin, url)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(result.json()["error"]["reason_code"], "publication_quality_blocked")

    def review_source(self, client, headers, url: str) -> dict:
        response = client.get(f"{url}/review", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        source = response.json()["source"]
        del source["ir_file_id"]
        return source

    def try_publish(self, client, admin, url: str):
        response = client.get(f"{url}/publications", headers=admin)
        self.assertEqual(response.status_code, 200, response.text)
        return client.post(f"{url}/publish", headers=admin, json={
            "request_id": str(uuid4()), "note": "核对正式产物后发布",
            "expected_source": response.json()["expected_source"],
        })

    def _check_ruled_word(self, report, word: bytes, *, last_row: list[tuple[str, int]]) -> None:
        table, = report.envelope.report.tables
        output, = table.outputs
        rendered = Document(BytesIO(word)).tables[output.actual.table_index]
        self.assertEqual([cell.text for cell in rendered.rows[0].cells][2:], ["LOW", "HIGH", "UNIT"])
        self.assertEqual([[(c.text, c.grid_span) for c in row.cells[2:]] for row in rendered.rows[1:]], [
            [("", 1), ("7.2e-4", 1), ("s", 1)],
            [("43", 1), ("", 1), ("ms", 1)],
            last_row,
        ])

    def test_ruled_table_keeps_the_unresolved_cell_blocked_in_review_and_publication(self) -> None:
        with TemporaryDirectory() as directory:
            package, source = _ruled_table_package(Path(directory))
            with self.worker_case(package.read_bytes(), source.read_bytes(), echoed_data_id=False) as (
                runtime, _, job, client, owner, admin,
            ):
                report, word = self.read_verified_word(runtime, job)
                self.assertIsNone(report.document.metadata.pdf_value_column_page_equivalence)
                self._check_ruled_word(report, word, last_row=[("48", 2), ("48", 2), ("ms", 1)])
                quality = current_base(job)
                self.assertEqual((quality.quality_status, quality.counts.blocker_count), ("blocked", 1))
                ir_waiting, = report.document.metadata.pdf_value_column_unresolved
                table, = report.envelope.report.tables
                self.assertEqual(len(table.validation.findings), 3)
                self.assertEqual(len(table.value_column_corrections), 2)
                self.assertEqual({flag.identity for flag in table.flags if flag.severity == "blocker"},
                                 {ir_waiting.finding_id})
                response = client.get(f"/api/v1/document-jobs/{job.id}/quality/tables", headers=owner)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["source"]["generation"], job.retry_count)
                item, = response.json()["items"]
                waiting, = item["unresolved_value_columns"]
                self.assertEqual(waiting["finding_id"], ir_waiting.finding_id)
                self.assertEqual(waiting["fragment_id"], ir_waiting.fragment_id)
                self.assertEqual((waiting["source_page_index"], waiting["source_row_index"], waiting["source_cell_index"]),
                                 (0, 3, 2))
                self.assertEqual(waiting["reason_code"], ir_waiting.reason)
                self.assertIn(waiting["reason_code"], {"column_ambiguous", "value_visibility_unverified"})
                self.check_blocked_delivery(client, owner, admin, job.id)

    def test_admin_replays_the_same_package_and_publishes_after_actual_word_certification(self) -> None:
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), TemporaryDirectory() as directory:
                package, source = _ruled_table_package(Path(directory), manual_review_case=True)
                pdf = source.read_bytes()
                with self.worker_case(package.read_bytes(), pdf, kind=kind) as (runtime, execution, first, client, owner, admin):
                    self._certify_last_value(runtime, execution, first, client, owner, admin, pdf,
                                             disable_after_acceptance=kind == "sqlite")

    @staticmethod
    def _with_returned_pdf(package: bytes, pdf: bytes) -> bytes:
        result = BytesIO()
        with ZipFile(BytesIO(package)) as original, ZipFile(result, "w") as rewritten:
            origin, = (entry for entry in original.namelist() if entry.endswith("_origin.pdf"))
            for entry in original.namelist():
                rewritten.writestr(entry, pdf if entry == origin else original.read(entry))
        return result.getvalue()

    def _assert_page_equivalent_replay(self, package: bytes, pdf: bytes) -> None:
        # EOF 后的注释改变文件摘要，同时保持 PDF 的页面、词框及绘制内容。
        returned = pdf + b"\n% processed PDF\n"
        package = self._with_returned_pdf(package, returned)

        def observe_upload(path, **kwargs):
            self.assertEqual(path.read_bytes(), pdf)
            return observe_pdf_value_column_page(path, **kwargs)

        with (
            patch("app.services.document_ir.pdf_value_column_observer.observe_pdf_value_column_page",
                  side_effect=observe_upload) as observation,
            self.worker_case(package, pdf, kind="sqlite") as (runtime, execution, first, client, owner, admin),
        ):
            report, _ = self.read_verified_word(runtime, first)
            proof = report.document.metadata.pdf_value_column_page_equivalence
            self.assertIsNotNone(proof)
            upload_binding = first.mineru_upload_binding
            self.assertIsNotNone(upload_binding)
            self.assertEqual((upload_binding.source_file_id, upload_binding.source_pdf_sha256,
                              upload_binding.parse_generation),
                             (first.source_file_id, "sha256:" + sha256(pdf).hexdigest(), first.retry_count))
            self.assertEqual(proof.source_pdf_sha256.removeprefix("sha256:"), sha256(pdf).hexdigest())
            self.assertEqual(proof.returned_pdf_sha256.removeprefix("sha256:"), sha256(returned).hexdigest())
            self.assertEqual(proof.lineage.raw_file_id, first.mineru_raw_result_file_id)
            self.assertEqual(proof.lineage.raw_sha256.removeprefix("sha256:"), sha256(package).hexdigest())
            self.assertEqual((proof.lineage.batch_id, proof.lineage.data_id, proof.lineage.parse_generation),
                             (first.mineru_batch_id, first.mineru_data_id, first.retry_count))
            self._certify_last_value(runtime, execution, first, client, owner, admin, pdf, disable_after_acceptance=True)
            second = runtime.document_job_repository.get_document_job(first.id)
            replayed_report, _ = self.read_verified_word(runtime, second)
            self.assertEqual(second.mineru_upload_binding, upload_binding)
            self.assertEqual(replayed_report.document.metadata.pdf_value_column_page_equivalence, proof)
            self.assertGreaterEqual(observation.call_count, 2)

    @skipUnless(which("pdftoppm"), "逐页比对需要 Poppler 栅格渲染")
    def test_page_equivalent_package_replays_and_publishes_using_the_uploaded_pdf(self) -> None:
        with TemporaryDirectory() as directory:
            package, source = _ruled_table_package(Path(directory), manual_review_case=True)
            self._assert_page_equivalent_replay(package.read_bytes(), source.read_bytes())

    @skipUnless(which("pdftoppm") and getenv("MD2WORD_TABLE_VALUE_LOW_HIGH_DIR"), "需要隔离验收的嵌字体划线夹具")
    def test_embedded_low_high_package_replays_with_different_origin_digest(self) -> None:
        directory = Path(getenv("MD2WORD_TABLE_VALUE_LOW_HIGH_DIR"))
        self._assert_page_equivalent_replay(
            (directory / "qualification-embedded.zip").read_bytes(),
            (directory / "qualification-embedded.pdf").read_bytes(),
        )

    @skipUnless(which("pdftoppm") and getenv("MD2WORD_TABLE_VALUE_P7_PDF") and getenv("MD2WORD_TABLE_VALUE_P7_ZIP"),
                "需要隔离验收保留的真实 P7 提交及原包")
    def test_retained_p7_real_package_keeps_unproven_columns_blocked_after_page_comparison(self) -> None:
        source = Path(getenv("MD2WORD_TABLE_VALUE_P7_PDF")).read_bytes()
        package = Path(getenv("MD2WORD_TABLE_VALUE_P7_ZIP")).read_bytes()
        self.assertEqual(sha256(source).hexdigest(), "24f724cf0e795f6afeb6fec5c72ff8f144085c59d57fbf0a5c9efbf1808b1eb3")
        self.assertEqual(sha256(package).hexdigest(), "5de05d59fdacea166361bde14625ff8045350b0aefc894a923ff181a030fe033")
        with self.worker_case(package, source, filename="OPA228_P7.pdf") as (runtime, _, job, client, owner, admin):
            report, word = self.read_verified_word(runtime, job)
            self.assertIsNotNone(report.document.metadata.pdf_value_column_page_equivalence)
            table, = report.envelope.report.tables
            output, = table.outputs
            rows = Document(BytesIO(word)).tables[output.actual.table_index].rows
            header = [cell.text.strip() for cell in rows[0].cells]
            # 新鲜回包的表框右侧切入 UNIT 表头，既有列核定必须保留歧义。
            for value, columns in (("±5", (("MIN", 2), ("TYP", 2))), ("±100", (("MAX", 1),))):
                occurrences = [(index, cell.grid_span) for row in rows[1:]
                               for index, cell in enumerate(row.cells) if cell.text.strip() == value]
                self.assertEqual(occurrences, [(header.index(column), span) for column, span in columns])
            self.assertEqual(len(table.validation.findings), 18)
            waiting = report.document.metadata.pdf_value_column_unresolved
            self.assertFalse(table.value_column_corrections)
            self.assertEqual({item.reason for item in waiting}, {"header_ambiguous"})
            self.assertEqual({item.finding_id for item in waiting}, {item.finding_id for item in table.validation.findings})
            self.check_blocked_delivery(client, owner, admin, job.id)

    @skipUnless(which("pdftoppm"), "逐页比对需要 Poppler 栅格渲染")
    def test_changed_page_value_or_table_line_remains_blocked(self) -> None:
        with TemporaryDirectory() as directory:
            package, source = _ruled_table_package(Path(directory))
            pdf = source.read_bytes()
            self.assertIn(b"(43)", pdf)
            self.assertIn(b"50 390 m 450 390 l S", pdf)
            for returned in (
                make_pdf(b"BT /F1 10 Tf 20 140 Td (Other page) Tj ET", width=500, height=500),
                pdf.replace(b"(43)", b"(44)", 1),
                pdf.replace(b"50 390 m 450 390 l S", b"50 389 m 450 389 l S", 1),
            ):
                with self.subTest(returned_sha256=sha256(returned).hexdigest()), self.worker_case(
                    self._with_returned_pdf(package.read_bytes(), returned), pdf,
                ) as (runtime, _, job, client, owner, admin):
                    self._assert_missing_page_proof(runtime, job, client, owner, admin, pdf)

    def test_page_equivalence_requires_echoed_provider_identity(self) -> None:
        with TemporaryDirectory() as directory:
            package, source = _ruled_table_package(Path(directory))
            pdf = source.read_bytes()
            rewritten = self._with_returned_pdf(package.read_bytes(), pdf + b"\n% processed PDF\n")
            with self.worker_case(rewritten, pdf, echoed_data_id=False) as (runtime, _, job, client, owner, admin):
                self._assert_missing_page_proof(runtime, job, client, owner, admin, pdf)

    def test_raw_archive_from_another_batch_cannot_reach_current_word(self) -> None:
        with TemporaryDirectory() as directory:
            package, source = _ruled_table_package(Path(directory))
            pdf = source.read_bytes()
            rewritten = self._with_returned_pdf(package.read_bytes(), pdf + b"\n% processed PDF\n")
            with self.worker_case(rewritten, pdf, raw_metadata={"mineru_batch_id": "another-batch"}) as (
                _, _, job, _, _, _,
            ):
                self.assertEqual((job.status, job.failed_stage, job.error_code),
                                 ("failed", "ir_converting", "document_ir_failed"))
                self.assertIn("内容完整性校验失败", job.error_message)
                self.assertIsNone(job.document_ir_file_id)
                self.assertIsNone(job.result_file_id)

    def _assert_missing_page_proof(self, runtime, job, client, owner, admin, pdf: bytes) -> None:
        report, _ = self.read_verified_word(runtime, job)
        table, = report.envelope.report.tables
        self.assertIsNone(report.document.metadata.pdf_value_column_page_equivalence)
        self.assertFalse(table.value_column_corrections)
        unresolved = report.document.metadata.pdf_value_column_unresolved
        self.assertEqual(len(unresolved), 3)
        self.assertEqual({item.reason for item in unresolved}, {"source_pair_unverified"})
        self.assertEqual(current_base(job).counts.blocker_count, 3)
        self.check_blocked_delivery(client, owner, admin, job.id)
        waiting = next(item for item in unresolved if item.source_row_index == 3)
        url = f"/api/v1/document-jobs/{job.id}"
        payload = self._last_value_review_request(report, waiting, pdf, self.review_source(client, admin, url))
        rejected = client.post(f"{url}/new-generation", headers=admin, json=payload)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(rejected.json()["error"]["reason_code"], "table_value_column_source_unverified")
        self.assertEqual(runtime.document_job_repository.get_document_job(job.id).retry_count, job.retry_count)

    def test_worker_keeps_original_spans_outside_test_company(self) -> None:
        with TemporaryDirectory() as directory:
            package, source = _ruled_table_package(Path(directory))
            companies = frozenset({("other_tenant", "company_default")})
            with self.worker_case(package.read_bytes(), source.read_bytes(), companies=companies) as (
                runtime, _, job, client, owner, admin,
            ):
                report, _ = self.read_verified_word(runtime, job)
                table, = report.envelope.report.tables
                self.assertFalse(table.value_column_corrections)
                self.assertFalse(report.document.metadata.pdf_value_column_unresolved)
                self.assertEqual(current_base(job).counts.blocker_count, 3)
                self.check_blocked_delivery(client, owner, admin, job.id)

    def _last_value_review_request(self, report, waiting, pdf: bytes, expected_source: dict) -> dict:
        table, = report.envelope.report.tables
        evidence, = (finding.evidence for finding in table.validation.findings if finding.finding_id == waiting.finding_id)
        raw_cell, = (cell for cell in table.validation.cells if cell.id == evidence.cell_id)
        group, = report.document.metadata.logical_table_groups
        fragment, = group.fragments
        return {
            "request_id": str(uuid4()),
            "note": "源 PDF 最后一行的 48 ms 清楚位于 HIGH，条件文字为两行",
            "expected_source": expected_source,
            "action": "replay_table_value_columns",
            "table_value_column_reviews": [{
                "schema_version": "table-value-column-review/v1",
                "source_pdf_sha256": sha256(pdf).hexdigest(),
                "content_list_sha256": table.validation.source_content_sha256,
                "page_index": fragment.source_span.page_index,
                "json_pointer": fragment.source_span.json_pointer,
                "raw_html_sha256": fragment.raw_html_sha256,
                "normalizer_version": table.validation.normalizer_version,
                "corrections": [{
                    "source_row_index": waiting.source_row_index,
                    "source_cell_index": waiting.source_cell_index,
                    "content_sha256": raw_cell.content_sha256,
                    "original_column_range": [evidence.column, evidence.end_column],
                    "target_column": 3,
                    "target_header": "HIGH",
                }],
            }],
        }

    def _certify_last_value(self, runtime, execution, first, client, owner, admin, pdf: bytes, *,
                            disable_after_acceptance: bool) -> None:
        report, first_word = self.read_verified_word(runtime, first)
        self._check_ruled_word(report, first_word, last_row=[("48", 2), ("48", 2), ("ms", 1)])
        waiting, = report.document.metadata.pdf_value_column_unresolved
        self.assertEqual(waiting.reason, "row_ambiguous")
        self.check_blocked_delivery(client, owner, admin, first.id)
        table, = report.envelope.report.tables
        url = f"/api/v1/document-jobs/{first.id}"
        payload = self._last_value_review_request(report, waiting, pdf, self.review_source(client, admin, url))
        denied = client.post(f"{url}/new-generation", headers=owner, json=payload)
        self.assertEqual(denied.status_code, 403, denied.text)
        companies = runtime.settings.document_table_value_pdf_binding_company_allowlist
        runtime.settings.document_table_value_pdf_binding_company_allowlist = frozenset()
        outside_pilot = client.post(f"{url}/new-generation", headers=admin, json=payload)
        self.assertEqual(outside_pilot.status_code, 409, outside_pilot.text)
        self.assertEqual(outside_pilot.json()["error"]["reason_code"], "table_value_column_review_disabled")
        runtime.settings.document_table_value_pdf_binding_company_allowlist = companies
        stale = deepcopy(payload)
        stale["table_value_column_reviews"][0]["source_pdf_sha256"] = "0" * 64
        rejected = client.post(f"{url}/new-generation", headers=admin, json=stale)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(runtime.document_job_repository.get_document_job(first.id).retry_count, first.retry_count)

        uploads = len(execution.fake_mineru_client.calls)
        downloads = len(execution.fake_mineru_client.download_calls)
        dispatch = (patch.object(runtime.document_job_use_cases.publication.task_queue, "enqueue")
                    if disable_after_acceptance else nullcontext())
        with dispatch:
            accepted = client.post(f"{url}/new-generation", headers=admin, json=payload)
        self.assertEqual(accepted.status_code, 202, accepted.text)
        if disable_after_acceptance:
            queued = runtime.document_job_repository.get_document_job(first.id)
            self.assertEqual((queued.status, queued.stage), ("running", "parsed"))
            runtime.settings.document_table_value_pdf_binding_enabled = False
            runtime.settings.document_table_value_pdf_binding_company_allowlist = frozenset()
            execution.execute_job(first.id)
        second = runtime.document_job_repository.get_document_job(first.id)
        self.assertEqual((second.status, second.stage), ("succeeded", "completed"), second.error_message)
        self.assertEqual(second.retry_count, first.retry_count + 1)
        self.assertEqual(second.mineru_raw_result_file_id, first.mineru_raw_result_file_id)
        self.assertEqual((len(execution.fake_mineru_client.calls), len(execution.fake_mineru_client.download_calls)),
                         (uploads, downloads))
        self.assertNotEqual(second.result_file_id, first.result_file_id)
        self.assertIsNotNone(second.started_at)
        self.assertIsNotNone(second.timeout_at)
        replayed = client.post(f"{url}/new-generation", headers=admin, json=payload)
        self.assertEqual(replayed.status_code, 200, replayed.text)
        self.assertEqual(replayed.json()["accepted_generation"], accepted.json()["accepted_generation"])
        conflicting = deepcopy(payload)
        conflicting["table_value_column_reviews"][0]["corrections"][0].update(target_column=2, target_header="LOW")
        duplicate = client.post(f"{url}/new-generation", headers=admin, json=conflicting)
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        self.assertEqual(duplicate.json()["error"]["reason_code"], "new_generation_request_conflict")
        source_file = runtime.document_file_repository.get_document_file(first.result_file_id)
        self.assertEqual(runtime.file_upload_service.read_file_content(source_file), first_word)

        verified, second_word = self.read_verified_word(runtime, second)
        self._check_ruled_word(verified, second_word, last_row=[("", 1), ("48", 1), ("ms", 1)])
        self.assertFalse(verified.document.metadata.pdf_value_column_unresolved)
        second_table, = verified.envelope.report.tables
        self.assertEqual(second_table.validation.findings, table.validation.findings)
        self.assertEqual({item.finding_id for item in second_table.value_column_corrections},
                         {finding.finding_id for finding in table.validation.findings})
        self.assertEqual([item.finding_id for item in second_table.value_column_corrections if not item.pdf_binding_sha256],
                         [waiting.finding_id])
        quality = current_base(second)
        self.assertIn(quality.quality_status, {"passed", "warning"})
        self.assertEqual((quality.evaluation_state, quality.counts.blocker_count), ("complete", 0))
        result_file = runtime.document_file_repository.get_document_file(second.result_file_id)
        self.assertIn("layout_wide_table:block_0001", result_file.metadata["layout_quality_flags"])

        approval = client.patch(f"{url}/review", headers=owner, json={
            "status": "approved", "expected_source": self.review_source(client, owner, url),
        })
        self.assertEqual(approval.status_code, 200, approval.text)
        published = self.try_publish(client, admin, url)
        self.assertEqual(published.status_code, 201, published.text)
        current = runtime.document_job_repository.get_document_job(first.id)
        self.assertEqual(current.delivery_status, "published")
        self.assertEqual(current.result_file_id, second.result_file_id)
