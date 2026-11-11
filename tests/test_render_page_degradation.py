"""第三批 C3：带页定位的渲染失败降级为整页图像，另存新 IR 后有界重渲染；前提不满足按当次错误失败。"""
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from billiard.exceptions import SoftTimeLimitExceeded
from docx import Document
from docx.enum.section import WD_SECTION_START
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.domains.document_jobs.base_quality import BaseQualityContribution, SourcePageCounts
from app.main import create_app
from app.services.document_ir import MinerUToDocumentIRService
from app.services.document_ir.integrity import build_page_counts
from app.services.document_ir.models import (
    DocumentIR, DocumentIRBlock, DocumentIRBlockLayout, DocumentIRMetadata, DocumentIRPage,
)
from app.services.document_ir.artifact_validator import DEFERRABLE_ISSUE_CODES
from app.services.document_ir.page_degradation import (
    DEGRADED_REASON_LABELS, NOTICE_RESERVE_EMU, PageDegradationPolicy, drop_degraded_table_groups, replace_degraded_pages,
)
from app.services.renderer.render_evidence_validation import validate_render_result
from app.services.renderer.table_renderer import TableRenderError
from app.services.document_ir.table_placeholder import PdfCropSource, checksum
from app.services.renderer.word_renderer import DocumentIRWordRenderer
from tests import test_fastapi_jobs_backend as fixtures
from tests.test_page_degradation import PDF, _FakeRasterizer, _png

ORIGINAL_RENDER_BLOCK = DocumentIRWordRenderer._render_block
TABLE = "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>"


def _pages(count):
    return [{"type": "text", "text": f"Page {index + 1} body", "page_idx": index} for index in range(count)]


def _zip(blocks):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list.json", json.dumps(blocks))
    return buffer.getvalue()


def _failing_on(*texts, error=ValueError):
    def failing(renderer, document, block, *args, **kwargs):
        if block.text in texts:
            raise error("内部细节不得进入事件")
        return ORIGINAL_RENDER_BLOCK(renderer, document, block, *args, **kwargs)
    return failing


class RenderPageDegradationPipelineTests(TestCase):
    def run_job(self, blocks, failing, *, rasterizer=True, max_attempts=None, policy=None):
        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory), auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            )
            service = runtime.document_job_execution_service
            service.fake_mineru_client.result_zip_bytes = _zip(blocks)
            service.document_ir_service.page_rasterizer = _FakeRasterizer() if rasterizer else None
            if max_attempts is not None:
                service.settings.render_degradation_max_attempts = max_attempts
            if policy is not None:
                service.document_ir_service.degradation_policy = policy
            with TestClient(create_app(runtime)) as client, patch.object(DocumentIRWordRenderer, "_render_block", failing):
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                job_id = client.post("/api/v1/document-jobs", headers=headers, json={"source_file_id": source["id"]}).json()["job_id"]
                job = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers).json()
                events = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers).json()["items"]
                approve = None
                if job["status"] == "succeeded":
                    review = client.get(f"/api/v1/document-jobs/{job_id}/review", headers=headers).json()
                    expected = {key: review["source"][key] for key in
                                ("generation", "result_file_id", "result_sha256", "file_review_source_revision", "receipt_sha256")}
                    approve = client.patch(f"/api/v1/document-jobs/{job_id}/review", headers=headers,
                                           json={"status": "approved", "expected_source": expected})
            files = {file.id: file for file in runtime.document_file_repository.list_document_files() if file.job_id == job_id}
            record = runtime.document_job_repository.get_document_job(job_id)
            read = service.file_service.read_file_content
            contents = {file_id: read(file) for file_id, file in files.items()}
        return job, events, approve, files, record, contents

    def test_failed_page_is_degraded_and_rerendered(self):
        job, events, approve, files, record, contents = self.run_job(_pages(3), _failing_on("Page 2 body"))
        self.assertEqual(job["status"], "succeeded", (job["error_code"], job["error_message"]))
        self.assertEqual((job["quality_status"], job["delivery_status"]), ("blocked", "internal_draft"))
        self.assertEqual(job["quality_summary"]["checks_v1"]["document_base"]["degraded_pages"],
                         [{"page_number": 2, "trigger": "render", "reason_codes": ["render_failed"]}])
        self.assertGreaterEqual(approve.status_code, 400, approve.text)
        switch = next(event for event in events if event["payload"].get("degraded_from_document_ir_file_id"))
        self.assertEqual(switch["payload"]["degraded_page_indexes"], [1])
        self.assertNotIn("内部细节", json.dumps(events, ensure_ascii=False))
        # 任务指针、结果绑定都指向降级后的新 IR；旧 IR 保留但不再权威。
        new_ir_id = switch["payload"]["document_ir_file_id"]
        self.assertEqual(record.document_ir_file_id, new_ir_id)
        word = files[record.result_file_id]
        self.assertEqual(word.metadata["document_ir_file_id"], new_ir_id)
        self.assertEqual(word.metadata["source_integrity"]["render_degraded_page_count"], 1)
        ir = DocumentIR.model_validate_json(contents[new_ir_id])
        self.assertEqual([(block.page_index, block.text) for block in ir.blocks if block.type == "paragraph"],
                         [(0, "Page 1 body"), (1, "第 2 页因排版渲染失败无法转换，已按原 PDF 页面图像保留，本页不可编辑。"),
                          (2, "Page 3 body")])
        record_ = ir.metadata.degraded_pages[0]
        self.assertEqual((record_["trigger"], record_["operation_kind"], record_["render_reason_code"]),
                         ("render", "block", "ValueError"))
        raster = next(file for file in files.values() if file.metadata.get("origin") == "pdf_page_raster")
        self.assertIn(raster.id, record.image_asset_file_ids)
        with zipfile.ZipFile(io.BytesIO(contents[word.id])) as archive:
            media = [archive.read(name) for name in archive.namelist() if name.startswith("word/media/")]
        self.assertIn(contents[raster.id], media)

    def test_unmet_preconditions_fail_with_original_render_error(self):
        cases = {
            "无栅格器": dict(blocks=_pages(3), failing=_failing_on("Page 2 body"), rasterizer=False),
            "基础设施错误": dict(blocks=_pages(3), failing=_failing_on("Page 2 body", error=OSError)),
            "超过阈值": dict(blocks=_pages(1), failing=_failing_on("Page 1 body")),
            "重渲染超过阈值": dict(blocks=_pages(4), failing=_failing_on("Page 2 body", "Page 3 body", "Page 4 body")),
        }
        for name, options in cases.items():
            with self.subTest(name):
                job, events, _approve, files, record, _contents = self.run_job(**options)
                self.assertEqual((job["status"], job["failed_stage"]), ("failed", "rendering"))
                self.assertIsNone(record.result_file_id)
                switched = [event for event in events if event["payload"].get("degraded_from_document_ir_file_id")]
                self.assertEqual(len(switched), 2 if name == "重渲染超过阈值" else 0)
                if name == "重渲染超过阈值":
                    # 第三页已超阈值：按本次错误定位，指针保持在最后一次降级的新 IR。
                    self.assertEqual(job["failure_diagnostic"]["page_number"], 4)
                    self.assertEqual(record.document_ir_file_id, switched[-1]["payload"]["document_ir_file_id"])

    def test_independent_failed_pages_are_all_degraded(self):
        job, events, _approve, files, record, contents = self.run_job(
            _pages(6), _failing_on("Page 2 body", "Page 5 body"))
        self.assertEqual(job["status"], "succeeded", (job["error_code"], job["error_message"]))
        self.assertEqual((job["quality_status"], job["delivery_status"]), ("blocked", "internal_draft"))
        self.assertEqual([item["page_number"] for item in job["quality_summary"]["checks_v1"]["document_base"]["degraded_pages"]],
                         [2, 5])
        switches = [event["payload"] for event in events if event["payload"].get("degraded_from_document_ir_file_id")]
        self.assertEqual([payload["degraded_page_indexes"] for payload in switches], [[1], [4]])
        self.assertEqual(switches[1]["degraded_from_document_ir_file_id"], switches[0]["document_ir_file_id"])
        self.assertEqual(record.document_ir_file_id, switches[1]["document_ir_file_id"])
        self.assertEqual(files[record.result_file_id].metadata["source_integrity"]["render_degraded_page_count"], 2)
        self.assertEqual(job["quality_summary"]["checks_v1"]["document_base"]["page_counts"], {
            "source_page_count": 6, "converted_page_count": 4, "degraded_page_count": 2, "filtered_page_count": 0,
            "page_count_basis": "content_blocks"})
        ir = DocumentIR.model_validate_json(contents[record.document_ir_file_id])
        self.assertEqual([item["page_index"] for item in ir.metadata.degraded_pages], [1, 4])

    def test_attempt_limit_fails_with_current_page(self):
        job, events, _approve, _files, record, _contents = self.run_job(
            _pages(6), _failing_on("Page 2 body", "Page 5 body"), max_attempts=1)
        self.assertEqual((job["status"], job["failed_stage"]), ("failed", "rendering"))
        self.assertEqual(job["failure_diagnostic"]["page_number"], 5)
        self.assertEqual((job["failure_diagnostic"]["source_page_count"], job["failure_diagnostic"]["page_count_basis"]),
                         (6, "content_blocks"))
        self.assertIsNone(record.result_file_id)
        self.assertEqual(len([event for event in events if event["payload"].get("degraded_from_document_ir_file_id")]), 1)

    def test_zero_attempts_disables_render_degradation(self):
        job, events, *_rest = self.run_job(_pages(3), _failing_on("Page 2 body"), max_attempts=0)
        self.assertEqual((job["status"], job["failed_stage"]), ("failed", "rendering"))
        self.assertFalse([event for event in events if event["payload"].get("degraded_from_document_ir_file_id")])

    def test_policy_applies_to_render_stage(self):
        single, *_rest = self.run_job(_pages(1), _failing_on("Page 1 body"),
                                      policy=PageDegradationPolicy(allow_single_page=True))
        self.assertEqual(single["status"], "succeeded", (single["error_code"], single["error_message"]))
        strict, *_rest = self.run_job(_pages(4), _failing_on("Page 2 body", "Page 3 body"),
                                      policy=PageDegradationPolicy(max_page_ratio=0.25))
        self.assertEqual((strict["status"], strict["failure_diagnostic"]["page_number"]), ("failed", 3))

    def test_timeout_is_not_degraded(self):
        job, events, _approve, _files, _record, _contents = self.run_job(
            _pages(3), _failing_on("Page 2 body", error=SoftTimeLimitExceeded))
        self.assertEqual(job["status"], "failed")
        self.assertFalse([event for event in events if event["payload"].get("degraded_from_document_ir_file_id")])

    def test_table_plan_failure_is_degraded_by_located_page(self):
        def failing_build(block, index):
            raise TableRenderError("table_render_geometry", block_index=index)
        blocks = [*_pages(3), {"type": "table", "html": TABLE, "page_idx": 1}]
        with patch("app.services.renderer.logical_table_plan._build_current", failing_build):
            job, events, _approve, _files, record, contents = self.run_job(blocks, ORIGINAL_RENDER_BLOCK)
        self.assertEqual(job["status"], "succeeded", (job["error_code"], job["error_message"]))
        switch = next(event["payload"] for event in events if event["payload"].get("degraded_from_document_ir_file_id"))
        self.assertEqual(switch["failure_context"]["operation_kind"], "table_plan")
        self.assertEqual(switch["failure_context"]["reason_code"], "table_render_geometry")
        self.assertEqual(switch["degraded_page_indexes"], [1])
        ir = DocumentIR.model_validate_json(contents[record.document_ir_file_id])
        self.assertFalse(any(block.type == "table" for block in ir.blocks))


class DegradedPageIsolationTests(TestCase):
    """每个降级页独占一个分节；结构在此断言，实际分页另用 LibreOffice 核对。"""

    def _render(self, page_count, degraded, *, exclusive=True):
        document = DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="job", source_file_id="file", document_language="en"),
            pages=[DocumentIRPage(index=index, width=100.0, height=100.0) for index in range(page_count)],
            blocks=[DocumentIRBlock(id=f"block_{index}", type="paragraph", order=index, page_index=index,
                                    text=f"Page {index + 1} body", layout=DocumentIRBlockLayout(page_index=index, role="body"))
                    for index in range(page_count)],
        )
        _removed, pending = replace_degraded_pages(
            document, {page: _png() for page in degraded}, {page: {"reason_codes": ["render_failed"]} for page in degraded},
            source_pdf_sha256="sha256:x", dpi=144, trigger="render")
        if not exclusive:
            for block in document.blocks:
                block.metadata.pop("exclusive_page", None)
                block.metadata.pop("notice_reserve_emu", None)
        content = {item.asset_id: item.content for item in pending}
        result = DocumentIRWordRenderer().render_to_result(document, template_path=None, config_path=None,
                                                           image_loader=lambda asset: content.get(asset.id))
        validate_render_result(document, result.content, result)
        return result, Document(io.BytesIO(result.content))

    def test_each_degraded_page_gets_its_own_section_without_extra_sections(self):
        for degraded, expected_sections in (({1}, 3), ({1, 2}, 4), ({0}, 2), ({3}, 2), ({0, 3}, 3)):
            with self.subTest(degraded=degraded):
                result, word = self._render(4, degraded)
                self.assertEqual(len(word.sections), expected_sections)
                self.assertEqual([section.start_type for section in word.sections[1:]],
                                 [WD_SECTION_START.NEW_PAGE] * (expected_sections - 1))
                self.assertEqual(sum(operation.kind == "section" for operation in result.plan.operations), expected_sections)

    def test_notice_stays_with_image_and_image_leaves_notice_room(self):
        _result, word = self._render(3, {1})
        notice = next(paragraph for paragraph in word.paragraphs if paragraph.text.startswith("第 2 页"))
        self.assertTrue(notice.paragraph_format.keep_with_next)
        section = word.sections[1]
        usable = section.page_height - section.top_margin - section.bottom_margin
        self.assertLessEqual(word.inline_shapes[0].height, usable - NOTICE_RESERVE_EMU)

    def test_historical_degraded_page_keeps_flowing_layout(self):
        result, word = self._render(3, {1}, exclusive=False)
        self.assertEqual(len(word.sections), 1)
        self.assertEqual(sum(operation.kind == "section" for operation in result.plan.operations), 1)


class SourcePageCountsTests(TestCase):
    def _document(self, *, flags=(), degraded=(), layout=False):
        metadata = {"page_size_source": "layout.json"} if layout else {}
        return DocumentIR(
            schema_version="document-ir/v2",
            metadata=DocumentIRMetadata(job_id="job", source_file_id="file", document_language="en",
                                        degraded_pages=[{"page_index": index} for index in degraded]),
            pages=[DocumentIRPage(index=index, width=100.0, height=100.0, metadata=metadata) for index in range(4)],
            quality_flags=list(flags),
        )

    def test_counts_add_up_with_filtered_and_degraded_pages(self):
        counts = build_page_counts(self._document(flags=["final_promotional_page_filtered:4"], degraded=[1, 2], layout=True))
        self.assertEqual(counts, {"source_page_count": 5, "converted_page_count": 2, "degraded_page_count": 2,
                                  "filtered_page_count": 1, "page_count_basis": "mineru_layout"})

    def test_legacy_document_without_pages_has_no_counts(self):
        document = self._document()
        document.pages = []
        self.assertIsNone(build_page_counts(document))

    def test_invalid_counts_are_rejected_and_missing_counts_stay_absent(self):
        with self.assertRaises(ValidationError):
            SourcePageCounts.model_validate({"source_page_count": -1})
        self.assertNotIn("page_counts", BaseQualityContribution(generation=0).model_dump(mode="json"))


class DegradedNoticeTests(TestCase):
    def test_every_degradable_reason_has_chinese_label(self):
        self.assertLessEqual({*DEFERRABLE_ISSUE_CODES, "render_failed"}, set(DEGRADED_REASON_LABELS))


class DropDegradedTableGroupsTests(TestCase):
    def test_removed_table_group_leaves_valid_ir(self):
        blocks = [{"type": "text", "text": "Intro", "page_idx": 0},
                  {"type": "table", "html": TABLE, "page_idx": 1},
                  {"type": "text", "text": "After", "page_idx": 2}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.zip"
            path.write_bytes(_zip(blocks))
            document = MinerUToDocumentIRService().convert_zip(
                path, job_id="job", source_file_id="file_source", document_language="en",
                placeholder_source_loader=lambda: PdfCropSource("file_source", checksum(PDF), PDF)).document
        self.assertEqual(len(document.metadata.logical_table_groups), 1)
        removed, _pending = replace_degraded_pages(document, {1: _png()}, {1: {"reason_codes": ["render_failed"]}},
                                                   source_pdf_sha256="sha256:x", dpi=144, trigger="render")
        drop_degraded_table_groups(document, removed)
        rebuilt = DocumentIR.model_validate(document.model_dump(mode="python"))
        self.assertEqual((rebuilt.metadata.logical_table_groups, rebuilt.metadata.logical_table_group_counts["group_count"]),
                         ([], 0))
        self.assertFalse(any(block.type == "table" for block in rebuilt.blocks))
