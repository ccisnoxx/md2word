"""直接验证题注事实的只读提示投影，不启动应用、数据库或渲染器。"""

from __future__ import annotations

import copy
import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.core.errors import ApiError
from app.domains.document_jobs import review_content
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.quality_review_projection import decode_cursor
from app.domains.files.models import DocumentFileRecord
from app.services.document_ir.caption_reconciler import reconcile_captions
from app.services.document_ir.models import (
    DocumentIR, DocumentIRBlock, DocumentIRBlockLayout, DocumentIRMetadata, DocumentIRPage,
)


def _source(index, captions=None, *, page=0, kind="image"):
    block = {
        "type": kind, "page_idx": page, "bbox": [10, 10, 50, 60],
        "_mineru_source": {"json_pointer": f"/{index}", "source_index": index,
                           "source_index_in_page": index, "page_index": page, "source_type": kind},
    }
    if captions is not None:
        block["image_caption"] = captions
    if kind == "text":
        block["text"] = "保留的普通正文"
    return block


class DocumentJobReviewHintsTests(unittest.TestCase):
    def setUp(self):
        self.raw = [
            _source(0, []), _source(1, ["图 5 幅值", "图 7 响应"]),
            _source(2, kind="text"),
            _source(3, [], page=20), _source(4, ["图 9 频率", "图 8 增益"], page=20),
            _source(5, kind="text", page=20), _source(6, ["图 10 独立题注"], page=None),
        ]
        self.raw_before = copy.deepcopy(self.raw)
        reconciled = reconcile_captions(self.raw)
        self.document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="job_review", source_file_id="pdf_source", document_language="zh"),
            pages=[DocumentIRPage(index=index, width=100, height=100,
                metadata={"pdf_page_size": [100, 100], "page_size_source": "pdf"}) for index in (0, 20)],
            blocks=[DocumentIRBlock(
                id=f"block_{index + 1:04d}", type="image" if raw["type"] == "image" else "paragraph",
                order=index, page_index=raw["page_idx"], text=raw.get("text"), captions=result.captions,
                layout=DocumentIRBlockLayout(page_index=raw["page_idx"], bbox=tuple(raw["bbox"]), source_index=index),
                metadata={"source_type": raw["type"], **(
                    {"caption_reconciliation": result.evidence} if result.evidence is not None else {})},
            ) for index, (raw, result) in enumerate(zip(self.raw, reconciled, strict=True))],
        )
        self.job = DocumentJobRecord(
            id="job_review", tenant_id="tenant", company_id="company", created_by="owner",
            source_file_id="pdf_source", document_ir_file_id="ir_current", source_document_ir_file_id="ir_old",
            result_file_id="word_current", template_version_id="template", retry_count=2,
            status="succeeded", stage="completed", quality_status="passed",
            quality_summary={"quality_flags": ["existing_quality_flag"]},
        )
        self.payloads = {"ir_current": self.document.model_dump_json().encode()}
        self.records = {}
        for file_id, file_type, mime, content in (
            ("pdf_source", "source_pdf", "application/pdf", b""),
            ("ir_current", "document_ir", "application/json", self.payloads["ir_current"]),
            ("word_current", "generated_word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b""),
        ):
            self.records[file_id] = DocumentFileRecord(
                id=file_id, tenant_id="tenant", company_id="company", job_id=self.job.id,
                file_type=file_type, storage_provider="local_file", bucket="test", object_key=file_id,
                original_filename=file_id, mime_type=mime, size_bytes=len(content), status="uploaded",
                checksum_sha256="sha256:" + hashlib.sha256(content).hexdigest(),
                metadata={"retry_count": 2, "source_file_id": self.job.source_file_id},
            )
        self.user = object()
        self.service = Mock(spec=[
            "_review_api_job", "_ensure_job_not_deleted", "_review_api_file", "_file_belongs_to_job",
            "_review_cursor", "_finish_review_read", "file_repository", "file_upload_service",
        ])
        self.service._review_api_job.return_value = self.job
        self.service._review_api_file.return_value = self.records["word_current"]
        self.service._file_belongs_to_job.return_value = True
        self.service._review_cursor.side_effect = lambda cursor, kind, job_id, limit: (
            decode_cursor(cursor, kind, job_id) if cursor is not None else None)
        self.service.file_repository = Mock(spec=["get_document_file"])
        self.service.file_repository.get_document_file.side_effect = self.records.get
        self.service.file_upload_service = Mock(spec=["read_file_content"])
        self.service.file_upload_service.read_file_content.side_effect = lambda record: self.payloads[record.id]

    def test_real_caption_facts_project_without_changing_content_or_private_evidence(self):
        before = self.document.model_dump(mode="json")
        read = review_content._load(self.service, self.job.id, self.user)
        rows = [review_content._block(read, block) for block in read.basis.blocks]
        self.assertEqual(
            [block.metadata.get("caption_reconciliation", {}).get("status") for block in read.basis.blocks],
            ["uncertain", "uncertain", None, "rebound", "rebound", None, "unchanged"],
        )
        self.assertEqual([[flag.model_dump() for flag in row.flags] for row in rows], [
            [{"code": "caption_binding_uncertain", "severity": "warning", "table_id": None}],
            [{"code": "caption_binding_uncertain", "severity": "warning", "table_id": None}], [],
            [{"code": "caption_reassociated", "severity": "info", "table_id": None}],
            [{"code": "caption_reassociated", "severity": "info", "table_id": None}], [], [],
        ])
        self.assertEqual(rows[0].source_spans[0].source_page_index, 0)
        self.assertEqual(rows[3].source_spans[0].source_page_index, 20)
        self.assertIsNone(rows[6].source_spans[0].source_page_index)
        self.assertTrue(rows[0].source_spans[0].coordinate_verified)
        self.assertIsNone(rows[3].location.preview_page_index)
        for row in rows:
            public = row.model_dump_json()
            for private_field in ("caption_reconciliation", "originals", "source_locator", "reasons", "bindings"):
                self.assertNotIn(private_field, public)
        self.assertEqual(read.basis.model_dump(mode="json"), before)
        self.assertEqual(self.document.model_dump(mode="json"), before)
        self.assertEqual(self.raw, self.raw_before)
        read.finish()

    def test_ordinary_unknown_and_derived_blocks_keep_existing_flags_only(self):
        read = review_content._load(self.service, self.job.id, self.user)
        receipts = [None, [], "uncertain", {}, {"status": "unchanged"}, {"status": "evidence_only"},
                    {"status": "future_status"}, {"status": ["uncertain"]}]
        cases = [(receipt, None) for receipt in receipts]
        cases.extend([({"status": status}, "block_owner") for status in ("uncertain", "rebound")])
        for receipt, owner in cases:
            with self.subTest(receipt=receipt, owner=owner):
                block = self.document.blocks[0].model_copy(deep=True)
                block.metadata = {"quality_flags": ["layout_bbox_missing:private_block", "manual_review"]}
                if receipt is not None:
                    block.metadata["caption_reconciliation"] = receipt
                if owner is not None:
                    block.metadata["source_block_id"] = owner
                before = block.model_dump(mode="json")
                projected = review_content._block(read, block)
                self.assertEqual([flag.model_dump() for flag in projected.flags], [
                    {"code": "layout_bbox_missing", "severity": "warning", "table_id": None}])
                self.assertEqual(block.model_dump(mode="json"), before)

    def test_existing_flags_dedupe_by_code_severity_and_table_identity(self):
        read = review_content._load(self.service, self.job.id, self.user)
        block = self.document.blocks[0].model_copy(deep=True)
        block.metadata["quality_flags"] = ["layout_bbox_missing:first", "layout_bbox_missing:second"]
        read.tables_by_block[block.id] = [
            SimpleNamespace(table_id="table_a", flags=[
                review_content.Flag(code="layout_bbox_missing", severity="warning"),
                review_content.Flag(code="layout_bbox_missing", severity="warning"),
                review_content.Flag(code="layout_bbox_missing", severity="blocker"),
            ]),
            SimpleNamespace(table_id="table_b", flags=[review_content.Flag(code="layout_bbox_missing", severity="warning")]),
        ]
        before = block.model_dump(mode="json")
        projected = review_content._block(read, block)
        self.assertEqual([(flag.code, flag.severity, flag.table_id) for flag in projected.flags], [
            ("layout_bbox_missing", "warning", "table_a"), ("layout_bbox_missing", "blocker", "table_a"),
            ("layout_bbox_missing", "warning", "table_b"), ("layout_bbox_missing", "warning", None),
            ("caption_binding_uncertain", "warning", None),
        ])
        self.assertEqual(projected.table_ids, ["table_a", "table_b"])
        self.assertEqual(block.model_dump(mode="json"), before)

    def test_list_blocks_preserves_source_snapshot_pagination_and_formal_states(self):
        before = (self.job.model_dump(mode="json"), copy.deepcopy(self.records), copy.deepcopy(self.payloads))
        first = review_content.list_blocks(self.service, self.job.id, user=self.user, problem="flagged",
                                          source_page_index=20, severity="info", limit=1)
        second = review_content.list_blocks(self.service, self.job.id, user=self.user, problem="flagged",
                                           source_page_index=20, severity="info", limit=1, cursor=first.next_cursor)
        self.assertEqual(first.availability, "available")
        self.assertEqual(first.total, 2)
        self.assertEqual([first.items[0].block_id, second.items[0].block_id], ["block_0004", "block_0005"])
        self.assertIsNotNone(first.next_cursor)
        self.assertIsNone(second.next_cursor)
        self.assertEqual(first.content_snapshot, second.content_snapshot)
        self.assertEqual(first.source, second.source)
        self.assertEqual(first.source.model_dump(), {
            "generation": 2, "ir_file_id": "ir_current", "result_file_id": "word_current",
            "result_sha256": self.records["word_current"].checksum_sha256,
            "file_review_source_revision": 0, "receipt_sha256": None,
        })
        self.assertEqual(first.content_snapshot.source_pdf_file_id, "pdf_source")
        self.assertEqual(first.content_snapshot.source_ir_file_id, "ir_current")
        self.assertEqual(first.content_snapshot.basis, "final")
        warnings = review_content.list_blocks(self.service, self.job.id, user=self.user,
                                             problem="flagged", severity="warning")
        self.assertEqual([row.block_id for row in warnings.items], ["block_0001", "block_0002"])
        self.assertEqual((self.job.model_dump(mode="json"), self.records, self.payloads), before)
        self.assertEqual(self.service._finish_review_read.call_count, 3)
        self.service._finish_review_read.assert_called_with(
            self.job, self.records["word_current"], self.user, preview=True)
        self.assertEqual({call.args[0].id for call in self.service.file_upload_service.read_file_content.call_args_list},
                         {"ir_current"})

    def test_cursor_rejects_changed_filters_and_changed_content_snapshot(self):
        first = review_content.list_blocks(self.service, self.job.id, user=self.user, problem="flagged", limit=1)
        with self.assertRaises(ApiError) as filtered:
            review_content.list_blocks(self.service, self.job.id, user=self.user,
                                       problem="flagged", severity="warning", limit=1, cursor=first.next_cursor)
        self.assertEqual(filtered.exception.reason_code, "invalid_review_cursor")
        self.service._review_api_job.return_value = self.job.model_copy(update={"retry_count": 3})
        with self.assertRaises(ApiError) as changed:
            review_content.list_blocks(self.service, self.job.id, user=self.user,
                                       problem="flagged", limit=1, cursor=first.next_cursor)
        self.assertEqual(changed.exception.reason_code, "quality_source_changed")

    def test_access_denied_prevents_content_read(self):
        self.service._review_api_job.side_effect = ApiError(403, "forbidden", "无权读取该任务。")
        with self.assertRaises(ApiError) as denied:
            review_content.list_blocks(self.service, self.job.id, user=self.user, problem="flagged")
        self.assertEqual(denied.exception.status_code, 403)
        self.service.file_repository.get_document_file.assert_not_called()
        self.service.file_upload_service.read_file_content.assert_not_called()

    def test_foreign_ir_owner_is_rejected_before_reading_bytes(self):
        self.records["ir_current"] = self.records["ir_current"].model_copy(update={"company_id": "another_company"})
        with self.assertRaises(ApiError) as denied:
            review_content.list_blocks(self.service, self.job.id, user=self.user, problem="flagged")
        self.assertEqual(denied.exception.reason_code, "review_access_denied")
        self.service.file_upload_service.read_file_content.assert_not_called()

    def test_invalid_selected_ir_does_not_fall_back_to_old_source(self):
        self.payloads["ir_current"] = b"{invalid"
        self.records["ir_current"] = self.records["ir_current"].model_copy(update={
            "size_bytes": len(self.payloads["ir_current"]),
            "checksum_sha256": "sha256:" + hashlib.sha256(self.payloads["ir_current"]).hexdigest(),
        })
        self.records["ir_old"] = self.records["ir_current"].model_copy(update={"id": "ir_old"})
        with self.assertRaises(ApiError) as invalid:
            review_content.list_blocks(self.service, self.job.id, user=self.user, problem="flagged")
        self.assertEqual(invalid.exception.reason_code, "quality_evidence_conflict")
        self.service.file_upload_service.read_file_content.assert_called_once_with(self.records["ir_current"])
        self.assertNotIn("ir_old", [call.args[0] for call in self.service.file_repository.get_document_file.call_args_list])

    def test_read_completion_rejects_generation_changed_after_projection(self):
        changed = self.job.model_copy(update={"retry_count": 3})
        self.service._review_api_job.side_effect = [self.job, self.job, changed]
        with self.assertRaises(ApiError) as conflict:
            review_content.list_blocks(self.service, self.job.id, user=self.user, problem="flagged")
        self.assertEqual(conflict.exception.reason_code, "quality_source_changed")
        self.service._finish_review_read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
