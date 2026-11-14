"""页映射的版本兼容、定位置信度与预览读取边界。"""

import hashlib
import json
from copy import deepcopy
from unittest import TestCase

from app.domains.document_jobs.preview_evidence import read_current_preview_evidence
from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRBlock,
    DocumentIRBlockLayout,
    DocumentIRMetadata,
    DocumentIRPage,
)
from app.services.preview.models import sha256
from app.services.preview.page_mapping import MappingBinding, build_page_mapping, read_page_mapping
from app.services.renderer.word_renderer import DocumentIRWordRenderer
from tests.document_job_list_query_v2_publication_fixtures import V2PublicationFixture


def mapping_digest(mapping: dict) -> str:
    """按持久化格式计算内层哈希，让绑定错误独立于哈希错误。"""
    payload = {key: value for key, value in mapping.items() if key != "mapping_sha256"}
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class PreviewPageMappingTests(TestCase):
    def test_read_historical_v1_mapping(self) -> None:
        binding = MappingBinding(
            source_pdf_file_id="source-v1",
            document_ir_file_id="ir-v1",
            input_ir_sha256="a" * 64,
            plan_sha256="b" * 64,
            source_generation=0,
            result_file_id="docx-v1",
            docx_sha256="sha256:" + "c" * 64,
            run_id="run-v1",
            attempt=1,
            profile_sha256="sha256:" + "d" * 64,
            preview_pdf_file_id="preview-v1",
            preview_pdf_sha256="sha256:" + "e" * 64,
            page_count=1,
        )
        # 保留旧算法的单页正文记录，兼容夹具独立于当前 writer。
        mapping = {
            "schema_version": "pdf-ir-word-page-map/v1",
            "algorithm_version": "source-order-nearest/v1",
            "status": "available",
            "reason_code": None,
            "binding": binding.model_dump(mode="json"),
            "counts": {"total": 1, "located": 1, "high": 1, "low": 0, "anchor_available": 1},
            "entries": [{
                "block_id": "body",
                "anchor_ref": "render-block:c4d6383f41613b11f0666f795cb32269b2a84d60ff377a2d82a3904b4491b0bf",
                "bookmark_name": "md2w_blk_c4d6383f41613b11f0666f795cb322",
                "anchor_reason_code": None,
                "disposition": "rendered",
                "representative_block_id": None,
                "source": {
                    "provenance_status": "legacy_layout",
                    "source_spans": [],
                    "logical_group_id": None,
                    "fragment_ids": [],
                    "layout_page_index": 0,
                    "bbox": [0.0, 0.0, 100.0, 20.0],
                },
                "location": {
                    "kind": "single_page",
                    "preview_page_index": 0,
                    "page_range": None,
                    "confidence": "high",
                    "reason_code": "single_page",
                    "nearest_block_id": None,
                },
                "fallback": None,
            }],
        }
        mapping["mapping_sha256"] = mapping_digest(mapping)

        self.assertEqual(read_page_mapping(mapping, binding=binding), mapping)

    def test_multi_page_mapping_keeps_zero_and_only_estimates_the_start(self) -> None:
        source_pages = (2, 8, 15)
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(
                job_id="mapping-job", source_file_id="mapping-source", document_language="zh",
            ),
            pages=[DocumentIRPage(index=page, width=400.0, height=600.0) for page in source_pages],
            blocks=[
                DocumentIRBlock(
                    id=f"body-{page}", type="paragraph", order=order, text=f"正文段落 {order + 1}。",
                    layout=DocumentIRBlockLayout(page_index=page, bbox=(0, 0, 100, 20)),
                )
                for order, page in enumerate(source_pages)
            ],
        )
        rendered = DocumentIRWordRenderer().render_to_result(
            document, template_path=None, config_path=None, image_loader=lambda _: None,
        )
        binding = MappingBinding(
            source_pdf_file_id=document.metadata.source_file_id,
            document_ir_file_id="mapping-ir",
            input_ir_sha256=rendered.plan.input_ir_sha256,
            plan_sha256=rendered.plan.plan_sha256,
            source_generation=0,
            result_file_id="mapping-docx",
            docx_sha256=sha256(rendered.content),
            run_id="mapping-run",
            attempt=1,
            profile_sha256="sha256:" + "d" * 64,
            preview_pdf_file_id="mapping-preview",
            preview_pdf_sha256="sha256:" + "e" * 64,
            page_count=5,
        )
        mapping = build_page_mapping(
            binding=binding, plan=rendered.plan, block_evidence=rendered.block_evidence,
            block_anchor_evidence=rendered.block_anchor_evidence,
        )

        self.assertEqual(read_page_mapping(mapping, binding=binding), mapping)
        self.assertEqual(mapping["algorithm_version"], "source-order-nearest/v2")
        self.assertEqual((mapping["status"], mapping["reason_code"]), ("degraded", "estimated_start"))
        self.assertEqual(
            [(entry["block_id"], entry["location"]["preview_page_index"]) for entry in mapping["entries"]],
            [("body-2", 0), ("body-8", 2), ("body-15", 4)],
        )
        for entry in mapping["entries"]:
            self.assertEqual(
                (entry["location"]["kind"], entry["location"]["confidence"], entry["location"]["page_range"]),
                ("estimated_start", "low", None),
            )


class PreviewManifestPageMappingTests(V2PublicationFixture, TestCase):
    def setUp(self) -> None:
        runtime, execution, _, job, _, _, _ = self.enterContext(self.runtime())
        job = self.install_publication_resources(runtime, execution, job)
        self.job = execution.execute_job(job.id)
        self.assertEqual(self.job.status, "succeeded", self.job.error_message)
        self.assertEqual(self.job.word_preview_state.current_run.status, "succeeded")
        self.files = runtime.document_file_repository
        self.file_service = runtime.file_upload_service
        self.jobs = runtime.document_job_repository
        self.manifest_id = self.job.word_preview_state.current_run.manifest_file_id
        record = self.files.get_document_file(self.manifest_id)
        self.manifest = json.loads(self.file_service.read_file_content(record))
        self.manifest_path = self.file_service.resolve_file_object_path(record)

    def read_preview(self):
        return read_current_preview_evidence(self.job, self.files, self.file_service, include_mapping=True)

    def write_fixture_manifest(self, body: dict, *, valid_outer_hash: bool = True) -> bytes:
        # 只修改当前测试的临时存储，模拟已经落盘的旧产物或损坏产物。
        content = json.dumps(body, ensure_ascii=False).encode("utf-8")
        checksum = sha256(content) if valid_outer_hash else "sha256:" + "0" * 64
        self.files.update_document_file(self.manifest_id, size_bytes=len(content), checksum_sha256=checksum)
        self.manifest_path.write_bytes(content)
        return content

    def test_read_current_v2_mapping_preserves_single_page_zero(self) -> None:
        evidence = self.read_preview()
        self.assertTrue(evidence.observation.available)
        mapping = evidence.page_mapping
        self.assertEqual(mapping, self.manifest["page_mapping"])
        self.assertEqual(mapping["algorithm_version"], "source-order-nearest/v2")
        self.assertEqual(mapping["status"], "available")
        self.assertGreater(mapping["counts"]["high"], 0)
        for entry in mapping["entries"]:
            self.assertEqual(entry["disposition"], "rendered")
            self.assertEqual(
                (entry["location"]["kind"], entry["location"]["preview_page_index"],
                 entry["location"]["confidence"], entry["location"]["page_range"]),
                ("single_page", 0, "high", None),
            )

    def test_optional_mapping_failures_leave_authenticated_preview_available(self) -> None:
        original = self.read_preview()
        self.assertTrue(original.observation.available)
        self.assertEqual(original.page_mapping["status"], "available")

        legacy = deepcopy(self.manifest)
        legacy.pop("page_mapping")
        bad_hash = deepcopy(self.manifest)
        bad_hash["page_mapping"]["mapping_sha256"] = "0" * 64
        wrong_binding = deepcopy(self.manifest)
        wrong_binding["page_mapping"]["binding"]["run_id"] = "another-run"
        wrong_binding["page_mapping"]["mapping_sha256"] = mapping_digest(wrong_binding["page_mapping"])

        for case, body, reason in (
            ("旧产物缺字段", legacy, "legacy_evidence_missing"),
            ("内层哈希错误", bad_hash, "invalid_mapping"),
            ("有效哈希但绑定错误", wrong_binding, "invalid_mapping"),
        ):
            with self.subTest(case=case):
                content = self.write_fixture_manifest(body)
                file_records = self.files.list_document_files()
                evidence = self.read_preview()

                self.assertTrue(evidence.observation.available)
                self.assertEqual(evidence.observation.files, tuple(
                    self.files.get_document_file(file.id) for file in original.observation.files
                ))
                self.assertEqual(evidence.manifest, body)
                self.assertEqual(
                    (evidence.page_mapping["status"], evidence.page_mapping["reason_code"],
                     evidence.page_mapping["entries"]),
                    ("unavailable", reason, []),
                )
                self.assertEqual(evidence.page_mapping["binding"], original.page_mapping["binding"])
                self.assertEqual(self.manifest_path.read_bytes(), content)
                self.assertEqual(self.files.list_document_files(), file_records)
                self.assertEqual(self.jobs.get_document_job(self.job.id), self.job)

    def test_invalid_outer_manifest_hash_still_rejects_preview(self) -> None:
        self.write_fixture_manifest(self.manifest, valid_outer_hash=False)

        with self.assertRaisesRegex(ValueError, "预览Artifact字节与描述符不一致"):
            self.read_preview()
