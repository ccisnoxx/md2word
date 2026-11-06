"""Worker 失败消息只保留固定码构造的消息，任意异常原文不进入任务 error_message。"""
from unittest import TestCase

from app.domains.document_jobs._failure_policy import worker_failure_message as message
from app.domains.translation.document_ir_translator import DocumentIRTranslationError
from app.services.document_ir.table_placeholder import TablePlaceholderError
from app.services.renderer.table_renderer import TableRenderError


class WorkerFailureMessageTests(TestCase):
    def test_fixed_code_errors_keep_their_message(self):
        self.assertEqual(message(TableRenderError("table_render_geometry", block_index=3)),
                         "表格渲染失败：table_render_geometry，块索引=3。")
        self.assertEqual(message(TablePlaceholderError("table_placeholder_crop_failed")),
                         "表格占位处理失败：table_placeholder_crop_failed。")

    def test_wrapped_translation_error_exposes_only_code(self):
        error = DocumentIRTranslationError("/srv/secret/profile.yaml 不存在", code="translation_profile_unavailable")
        self.assertEqual(message(error), "翻译处理失败：translation_profile_unavailable。")

    def test_arbitrary_errors_never_leak_their_text(self):
        for error in (ValueError("/tmp/job/a.png 内部路径"), KeyError("secret_key"), RuntimeError("provider said: 原文")):
            with self.subTest(type(error).__name__):
                text = message(error)
                self.assertEqual(text, f"Worker 执行失败（{type(error).__name__}），详见事件 trace_id。")
