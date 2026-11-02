"""P0-6：渲染失败附带 RenderPlan 操作定位，经白名单落入事件并投影为失败诊断。"""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.document_ir.models import (
    DocumentIR, DocumentIRBlock, DocumentIRBlockLayout, DocumentIRMetadata, DocumentIRPage,
)
from app.services.renderer.evidence import build_renderer_event_summary
from app.services.renderer.table_renderer import TableRenderError
from app.services.renderer.word_renderer import FAILURE_CONTEXT_ATTRIBUTE, DocumentIRWordRenderer
from tests import test_fastapi_jobs_backend as fixtures

ORIGINAL_RENDER_BLOCK = DocumentIRWordRenderer._render_block


def _document():
    def block(block_id, order, page, text, block_type="paragraph", html=None):
        return DocumentIRBlock(id=block_id, type=block_type, order=order, page_index=page, text=text, html=html,
                               layout=DocumentIRBlockLayout(page_index=page, bbox=(72, 80 + order * 40, 300, 110 + order * 40),
                                                            role="body"))
    return DocumentIR(
        schema_version="document-ir/v2",
        metadata=DocumentIRMetadata(job_id="docjob_ctx", source_file_id="file_ctx", document_language="en"),
        pages=[DocumentIRPage(index=0, width=400.0, height=600.0), DocumentIRPage(index=1, width=400.0, height=600.0)],
        blocks=[block("block_0001", 0, 0, "Intro"), block("block_0002", 1, 1, "Body on page two"),
                block("block_0003", 2, 1, None, "table", "<table><tr><td>A</td></tr></table>")],
    )


def _render(document):
    return DocumentIRWordRenderer().render_to_bytes(document, template_path=None, config_path=None,
                                                     image_loader=lambda _asset: None)


class RendererFailureContextTests(TestCase):
    def test_operation_failure_keeps_type_and_gains_location(self):
        def failing(renderer, document, block, *args, **kwargs):
            if block.id == "block_0002":
                raise ValueError("内部细节不得进入事件")
            return ORIGINAL_RENDER_BLOCK(renderer, document, block, *args, **kwargs)

        with patch.object(DocumentIRWordRenderer, "_render_block", failing), self.assertRaises(ValueError) as caught:
            _render(_document())
        context = getattr(caught.exception, FAILURE_CONTEXT_ATTRIBUTE)
        self.assertEqual((context["operation_kind"], context["block_ids"], context["source_page_index"]),
                         ("block", ["block_0002"], 1))
        self.assertIsInstance(context["operation_index"], int)

    def test_table_preparation_failure_is_located_by_block(self):
        stub_plan = SimpleNamespace(units=[])
        with patch("app.services.renderer.word_renderer.build_content_table_plan", return_value=stub_plan), \
                patch("app.services.renderer.word_renderer.prepare_table_input",
                      side_effect=TableRenderError("table_html_unsupported_structure", block_index=2)), \
                self.assertRaises(TableRenderError) as caught:
            _render(_document())
        context = getattr(caught.exception, FAILURE_CONTEXT_ATTRIBUTE)
        self.assertEqual((context["operation_kind"], context["block_ids"], context["source_page_index"]),
                         ("table_prepare", ["block_0003"], 1))


class FailureContextWhitelistTests(TestCase):
    def _summary(self, context):
        return build_renderer_event_summary({"failure_context": context}).get("failure_context")

    def test_valid_context_is_kept_and_unknown_values_dropped(self):
        valid = {"operation_index": 7, "operation_kind": "logical_table", "section_id": "section:0001",
                 "block_ids": ["block_0012"], "source_page_index": 3, "unit_id": "unit:abc", "reason_code": "table_render_geometry",
                 "message": "不得透传"}
        self.assertEqual(self._summary(valid), {key: value for key, value in valid.items() if key != "message"})
        self.assertEqual(self._summary({**valid, "source_page_index": -1, "unit_id": "坏 ID"})["source_page_index"], None)
        for bad in ({**valid, "operation_kind": "shell"}, {**valid, "reason_code": "内部消息"},
                    {**valid, "block_ids": ["block_1"] * 21}, {**valid, "block_ids": ["坏 ID"]}, "not-a-dict"):
            with self.subTest(bad=str(bad)[:40]):
                self.assertIsNone(self._summary(bad))
        self.assertEqual(self._summary({**valid, "reason_code": "ValueError"})["reason_code"], "ValueError")


class RenderFailureDiagnosticApiTests(TestCase):
    def test_render_failure_is_projected_with_page_and_block(self):
        def failing(renderer, document, block, *args, **kwargs):
            if block.type == "list":
                raise ValueError("内部细节不得进入事件")
            return ORIGINAL_RENDER_BLOCK(renderer, document, block, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory), auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            )
            with TestClient(create_app(runtime)) as client, patch.object(DocumentIRWordRenderer, "_render_block", failing):
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                job_id = client.post("/api/v1/document-jobs", headers=headers, json={"source_file_id": source["id"]}).json()["job_id"]
                detail = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers).json()
                diagnostics = client.get(f"/api/v1/document-job-incidents/{job_id}/diagnostics", headers=headers).json()
                events = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers).json()["items"]
        self.assertEqual((detail["status"], detail["failed_stage"], detail["error_code"]), ("failed", "rendering", "render_failed"))
        diagnostic = detail["failure_diagnostic"]
        self.assertEqual((diagnostic["source"], diagnostic["scope"], diagnostic["page_number"], diagnostic["operation_kind"],
                          diagnostic["reason_code"], diagnostic["affected_page_numbers"]),
                         ("render_operation", "page", 2, "block", "ValueError", [2]))
        self.assertEqual(len(diagnostic["block_ids"]), 1)
        self.assertTrue(diagnostic["block_ids"][0].startswith("block_"))
        self.assertEqual(diagnostics["failure_diagnostic"], diagnostic)
        failed = next(event for event in events if event["event_type"] == "stage_failed")
        # error_message 记录异常消息属既有行为（不在本任务范围）；新增的 failure_context 不得含消息原文。
        self.assertNotIn("内部细节", str(failed["payload"]["failure_context"]))
        self.assertEqual(set(failed["payload"]["failure_context"]),
                         {"operation_index", "operation_kind", "section_id", "block_ids", "source_page_index", "unit_id", "reason_code"})
