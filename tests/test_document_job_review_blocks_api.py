"""复核内容接口的真实装配回归：/review/blocks 与 /review/blocks/{block_id} 经正式用例组装可读。

单元测试 test_document_job_review_hints 以 Mock 替代 service，覆盖不到用例装配；这里走完整 runtime。
"""

import io
import json
import tempfile
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.main import create_app
from tests import test_fastapi_jobs_backend as fixtures


class _PaddedAnnotationProvider(fixtures.TruncatingOnceDocumentJobTranslationProvider):
    def translate(self, request):
        result = super().translate(request)
        return replace(result, items=tuple(
            replace(item, text=f"  {item.text}  ") if ".footnotes." in item.id else item
            for item in result.items
        ))


def _annotated_mineru_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(fixtures.make_english_mineru_zip_bytes())) as basis:
        blocks = json.loads(basis.read("content_list_v2.json"))
        blocks[1]["text"] = "The analog reading is low."
        blocks[2]["table_footnote"] = ["Monitor input offset voltage above 5 V.", "Keep below 12 V."]
        blocks[3]["image_footnote"] = ["Image note."]
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("content_list_v2.json", json.dumps(blocks))
            archive.writestr("images/figure1.png", basis.read("images/figure1.png"))
    return buffer.getvalue()


class DocumentJobReviewBlocksApiTests(TestCase):
    def _annotation_runtime(self, directory):
        runtime = fixtures.build_test_runtime(
            Path(directory), auth_jwt_secret_key="test-jwt-secret",
            auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            translation_debug_archive_enabled=True,
        )
        execution = runtime.document_job_execution_service
        execution.translation_batches.deps.document_ir_translation_service = (
            DocumentIRTranslationService(_PaddedAnnotationProvider())
        )
        execution.fake_mineru_client.result_zip_bytes = _annotated_mineru_zip()
        return runtime

    def _create_annotated_job(self, client, headers):
        source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
        created = client.post("/api/v1/document-jobs", headers=headers, json={
            "source_file_id": source["id"], "mode": "en2zh_pdf_to_word", "debug_full_text": True,
        })
        self.assertEqual(created.status_code, 201, created.text)
        base = f"/api/v1/document-jobs/{created.json()['job_id']}"
        job = client.get(base, headers=headers).json()
        self.assertEqual(job["status"], "succeeded", (job["error_code"], job["error_message"]))
        listed = client.get(f"{base}/review/blocks", headers=headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        snapshot = listed.json()["content_snapshot"]
        self.assertEqual(snapshot["translation"]["availability"], "available")
        return base, snapshot["snapshot_id"]

    def test_review_blocks_list_and_detail_use_real_use_case_wiring(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory), auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            )
            with TestClient(create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                job_id = client.post("/api/v1/document-jobs", headers=headers,
                                     json={"source_file_id": source["id"]}).json()["job_id"]
                job = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers).json()
                self.assertEqual(job["status"], "succeeded", (job["error_code"], job["error_message"]))

                listed = client.get(f"/api/v1/document-jobs/{job_id}/review/blocks", headers=headers)
                self.assertEqual(listed.status_code, 200, listed.text)
                body = listed.json()
                self.assertEqual(body["source"]["generation"], job["retry_count"])
                self.assertTrue(body["items"])

                block = body["items"][0]
                detail = client.get(
                    f"/api/v1/document-jobs/{job_id}/review/blocks/{block['block_id']}",
                    headers=headers, params={"snapshot_id": body["content_snapshot"]["snapshot_id"]},
                )
                self.assertEqual(detail.status_code, 200, detail.text)
                self.assertEqual(detail.json()["block"]["block_id"], block["block_id"])

    def test_annotation_parts_and_debug_segments_share_verified_translation_units(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._annotation_runtime(directory)
            with TestClient(create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                base, snapshot_id = self._create_annotated_job(client, headers)
                qa = client.get(f"{base}/translation-qa", headers=headers)
                self.assertEqual(qa.status_code, 200, qa.text)
                segments = {segment["id"]: segment for segment in qa.json()["segments"]}
                expected = {
                    "block_0003": ("Electrical Characteristics", ["Monitor input offset voltage above 5 V.", "Keep below 12 V."]),
                    "block_0004": ("Figure 1. Pin diagram", ["Image note."]),
                }
                for block_id, (caption, notes) in expected.items():
                    with self.subTest(block_id=block_id):
                        detail = client.get(f"{base}/review/blocks/{block_id}", headers=headers, params={
                            "snapshot_id": snapshot_id,
                        })
                        self.assertEqual(detail.status_code, 200, detail.text)
                        items = detail.json()["items"]
                        annotations = {(part["side"], part["unit_id"]): part["text"] for part in items
                                       if part["kind"] in ("caption", "footnote")}
                        captions_id = f"{block_id}.captions.0000"
                        self.assertEqual(annotations["source", captions_id], caption)
                        self.assertEqual(len(annotations), 2 * (1 + len(notes)))
                        self.assertNotIn(f"{block_id}.text", segments)
                        self.assertFalse(any(part["kind"] == "text" for part in items))
                        batches = {part["unit_id"]: part["batch"] for part in items if part["kind"] == "batch"}
                        self.assertEqual(batches[captions_id]["integrity_status"], "passed")
                        for index, note in enumerate(notes):
                            unit_id = f"{block_id}.footnotes.{index:04d}"
                            self.assertEqual(annotations["source", unit_id], note)
                            self.assertEqual(annotations["target", unit_id], f"  译文:{note}  ")
                            self.assertEqual(segments[unit_id]["final_text"], annotations["target", unit_id])
                            self.assertTrue(segments[unit_id]["source_available"])
                            self.assertEqual(batches[unit_id]["integrity_status"], "passed")
                        if block_id == "block_0003":
                            note_id = f"{block_id}.footnotes.0000"
                            self.assertNotEqual(batches[note_id]["batch_id"], batches[captions_id]["batch_id"])
                            self.assertTrue(any(
                                part["unit_id"] == note_id and part["term"]["batch_id"] == batches[note_id]["batch_id"]
                                for part in items if part["kind"] == "term"
                            ))

    def test_legacy_annotation_does_not_change_audit_coverage_or_debug_segments(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._annotation_runtime(directory)
            converter = runtime.document_job_execution_service.document_ir_service
            convert_zip = converter.convert_zip

            def convert_without_scope(*args, **kwargs):
                # 用历史序列化范围创建源件，后续批次、恢复摘要和审核走正式实现。
                kwargs["translation_item_scope"] = None
                result = convert_zip(*args, **kwargs)
                result.document.metadata.source_item_ledger_scope = None
                for block in result.document.blocks:
                    for key in ("annotation_ledger", "caption_text_alias_index", "table_annotation_source"):
                        block.metadata.pop(key, None)
                    if block.type == "list":
                        block.metadata["list_item_ledger"] = {
                            "version": "list-item-ledger/v1", "selected_field": "items", "mode": "legacy_items",
                            "source_item_count": 2, "empty_item_count": 0, "item_count": 2,
                        }
                return result

            with patch.object(converter, "convert_zip", side_effect=convert_without_scope):
                with TestClient(create_app(runtime)) as client:
                    headers = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                    base, snapshot_id = self._create_annotated_job(client, headers)
                    detail = client.get(f"{base}/review/blocks/block_0003", headers=headers, params={
                        "snapshot_id": snapshot_id,
                    })
                    self.assertEqual(detail.status_code, 200, detail.text)
                    parts = detail.json()["items"]
                    self.assertTrue(any(part["batch"]["integrity_status"] == "passed"
                                        for part in parts if part["kind"] == "batch"))
                    self.assertEqual(
                        [(part["side"], part["text"], part["unit_id"]) for part in parts if part["kind"] == "caption"],
                        [("source", "Electrical Characteristics", None), ("target", "Electrical Characteristics", None)],
                    )
                    self.assertTrue(any(part["unit_id"] == "block_0003.text" for part in parts))
                    qa = client.get(f"{base}/translation-qa", headers=headers)
                    self.assertEqual(qa.status_code, 200, qa.text)
                    segment_ids = {segment["id"] for segment in qa.json()["segments"]}
                    self.assertIn("block_0003.text", segment_ids)
                    self.assertFalse(any(".captions." in item_id or ".footnotes." in item_id for item_id in segment_ids))

    def test_scoped_debug_comparison_uses_only_the_adopted_annotation_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._annotation_runtime(directory)
            with TestClient(create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                base, _ = self._create_annotated_job(client, headers)
                unit_id = "block_0003.footnotes.0000"
                before = client.get(f"{base}/translation-qa", headers=headers).json()
                adopted, = [segment for segment in before["segments"] if segment["id"] == unit_id]
                self.assertIsNotNone(adopted["ai_translation_text"])
                job = runtime.document_job_repository.get_document_job(base.rsplit("/", 1)[-1])
                file_service = runtime.document_job_execution_service.file_service

                # 同代旧 attempt 在获胜结果之后结束，留下真实可读取的诊断档案。
                pending_evidence = {"prompt": {"items": [{"id": unit_id, "text": "过期原文"}]},
                                    "response": {"items": [{"id": unit_id, "text": "过期译文"}]}}
                late_archive = file_service.register_generated_content(
                    tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                    file_type="ai_debug_archive", filename="late_annotation.json", mime_type="application/json",
                    content=json.dumps(pending_evidence).encode(), object_version="late_annotation",
                    metadata={"retry_count": job.retry_count, "contains_full_text": True},
                )
                late_log = file_service.register_generated_content(
                    tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                    file_type="ai_call_log", filename="late_annotation_call.json", mime_type="application/json",
                    content=json.dumps({"status": "succeeded", "glossary_trace": [
                        {"segment_id": unit_id, "target_term": "过期术语"},
                    ]}).encode(), object_version="late_annotation_call", metadata={"retry_count": job.retry_count},
                )
                after = client.get(f"{base}/translation-qa", headers=headers)
                self.assertEqual(after.status_code, 200, after.text)
                payload = after.json()
                self.assertIn(late_archive.id, payload["artifacts"]["ai_debug_archive_file_ids"])
                self.assertIn(late_log.id, {call["file_id"] for call in payload["ai_calls"]})
                self.assertNotIn("过期术语", {trace["target_term"] for trace in payload["term_traces"]})
                current, = [segment for segment in payload["segments"] if segment["id"] == unit_id]
                self.assertEqual(current, adopted)
