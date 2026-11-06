"""B04：以 79f20cef 的可观察输出锁定失败策略，独立于执行器测试纯决策。"""

from copy import deepcopy
import json
from unittest import TestCase
import zipfile

from app.clients.mineru_client import MinerUError
from app.core.errors import ApiError
from app.domains.document_jobs import _failure_policy as policy
from app.domains.translation.document_ir_translator import DocumentIRTranslationError
from app.domains.translation.integrity import TranslationIntegrityError, TranslationIntegrityEvidence
from app.domains.translation.provider import TranslationProviderCallError, TranslationProviderResponseError
from app.services.document_ir.artifact_validator import MinerUArtifactValidationError, MinerUValidationReport
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.table_placeholder import TablePlaceholderError
from app.services.renderer.table_renderer import TableRenderError
from app.services.renderer.word_renderer import FAILURE_CONTEXT_ATTRIBUTE
from app.services.tables.evidence import TableEvidenceError
from app.services.tables.html_normalizer import TableBuildError
from app.services.tables.quality import TableValidationError


PRIVATE = "正文-B04 password=B04-secret https://user:pass@example.invalid/private?token=B04-token#secret"
STAGES = ("uploaded", "parsing", "ir_converting", "translating", "translation_validating",
          "rendering", "quality_checking", "uploading")
WORKER, MINERU, IR, TRANSLATION, RENDER, STORAGE = (
    "document_job_worker_failed", "mineru_failed", "document_ir_failed",
    "translation_failed", "render_failed", "oss_failed",
)
# 固定矩阵来自提取前的分类结果；顺序对应 STAGES，不从新实现计算期望。
CODES = {
    "ordinary": (WORKER, MINERU, IR, TRANSLATION, TRANSLATION, RENDER, RENDER, STORAGE),
    "storage": (STORAGE, MINERU, IR, STORAGE, STORAGE, RENDER, RENDER, STORAGE),
    "mineru": (MINERU,) * 8,
    "translation": (TRANSLATION, MINERU, TRANSLATION, TRANSLATION, TRANSLATION, TRANSLATION, TRANSLATION, TRANSLATION),
    "zip": (IR, MINERU, IR, IR, IR, IR, IR, IR),
    "integrity": (WORKER, MINERU, IR, TRANSLATION, TRANSLATION, RENDER, RENDER, RENDER),
}


def _translation_evidence():
    return TranslationIntegrityEvidence(
        status="failed", stage="response", error_code=None, expected_item_count=1,
        actual_item_count=0, checked_item_count=0, failed_item_count=1,
        source_char_count=1, encoded_char_count=1, response_char_count=0, restored_char_count=None,
        source_sha256="sha256:" + "a" * 64, encoded_sha256=None, response_sha256=None,
        restored_sha256=None, expected_token_counts=(), actual_token_counts=None,
    )


def _cases():
    """覆盖分类、消息白名单及未预期异常分支中的真实异常类型。"""
    report = MinerUValidationReport(package_sha256="a" * 64, can_convert=False)
    return (
        (ValueError(PRIVATE), "ordinary", "Worker 执行失败（ValueError），详见事件 trace_id。", False),
        (RuntimeError(PRIVATE), "ordinary", "Worker 执行失败（RuntimeError），详见事件 trace_id。", False),
        (KeyError(PRIVATE), "ordinary", "Worker 执行失败（KeyError），详见事件 trace_id。", True),
        (TypeError(PRIVATE), "ordinary", "Worker 执行失败（TypeError），详见事件 trace_id。", True),
        (Exception(PRIVATE), "ordinary", "Worker 执行失败（Exception），详见事件 trace_id。", True),
        (ApiError(503, "service_unavailable", PRIVATE), "storage", "Worker 执行失败（ApiError），详见事件 trace_id。", False),
        (OSError(PRIVATE), "storage", "Worker 文件或对象存储操作失败。", False),
        (FileNotFoundError(PRIVATE), "storage", "Worker 文件或对象存储操作失败。", False),
        (MinerUError(PRIVATE), "mineru", "MinerU 外部调用失败。", False),
        (zipfile.BadZipFile(PRIVATE), "zip", "Worker 执行失败（BadZipFile），详见事件 trace_id。", False),
        (DocumentIRTranslationError(PRIVATE), "translation", "翻译处理失败：translation_provider_failed。", False),
        (TranslationProviderCallError(PRIVATE), "ordinary", "Worker 执行失败（TranslationProviderCallError），详见事件 trace_id。", False),
        (TranslationProviderResponseError(PRIVATE), "ordinary", "Worker 执行失败（TranslationProviderResponseError），详见事件 trace_id。", False),
        (MinerUArtifactValidationError(report), "ordinary", "MinerU 产物验证失败：mineru_input_invalid。", False),
        (TablePlaceholderError("table_placeholder_crop_failed"), "integrity", "表格占位处理失败：table_placeholder_crop_failed。", False),
        (TableRenderError("table_render_geometry", block_index=3), "ordinary", "表格渲染失败：table_render_geometry，块索引=3。", False),
        (TableBuildError("table_build_limit", fragment_id="fragment_1"), "ordinary", "表格构建失败：table_build_limit。", False),
        (TableEvidenceError("table_evidence_integrity"), "integrity", "表格证据处理失败：table_evidence_integrity。", False),
        (TableValidationError("table_validation_input"), "ordinary", "表格验证失败：table_validation_input。", False),
        (TranslationIntegrityError("translation_integrity_item_missing", _translation_evidence()), "translation", "翻译返回项缺少预期 ID。", False),
        (DocumentIntegrityError("DocumentIR→DOCX", {"blocking_quality_flags": ["ir_docx_integrity:table_count_mismatch"]}),
         "integrity", "DocumentIR→DOCX 内容完整性校验失败：ir_docx_integrity:table_count_mismatch", False),
    )


class WorkerFailurePolicyTests(TestCase):
    def test_baseline_classification_messages_and_final_overrides(self):
        for error, category, message, unexpected in _cases():
            for index, stage in enumerate(STAGES):
                with self.subTest(error=type(error).__name__, stage=stage):
                    failed_stage = "quality_checking" if category == "integrity" and stage == "uploading" else stage
                    code = CODES[category][index]
                    self.assertEqual(policy.classify_worker_failure(error, stage), (failed_stage, code))
                    self.assertEqual(policy.worker_failure_message(error), message)
                    self.assertEqual(policy.stage_attempt_failure(error, stage), (
                        failed_stage, "document_job_unexpected_error" if unexpected else code,
                        "Worker 执行发生未预期异常。" if unexpected else message,
                    ))
                    render_stage = "quality_checking" if isinstance(error, TableEvidenceError) else failed_stage
                    render_code = RENDER if isinstance(error, TableEvidenceError) else (
                        "document_job_unexpected_error" if unexpected else code)
                    self.assertEqual(policy.render_failure(error, stage, validating_legacy=False), (
                        render_stage, render_code, failed_stage if unexpected else None,
                    ))
                    self.assertEqual(policy.render_failure(error, stage, validating_legacy=True), (
                        "uploading", STORAGE, failed_stage if unexpected else None,
                    ))

    def test_baseline_stage_mapping_and_legacy_v2_priority(self):
        for stage in STAGES:
            self.assertEqual(policy.failed_stage_for_current_stage(stage), stage)
        for stage in ("parsed", "completed", "failed", "canceled"):
            self.assertEqual(policy.failed_stage_for_current_stage(stage), "parsing")
            self.assertEqual(policy.classify_worker_failure(OSError(PRIVATE), stage), ("parsing", MINERU))
        error = DocumentIntegrityError("DocumentIR→DOCX", {"renderer_content_contract_version": "renderer-content/v2"})
        self.assertEqual(policy.render_failure(error, "uploading", validating_legacy=True), ("quality_checking", RENDER, None))

    def test_baseline_failure_context_reason_priority_and_redaction(self):
        context = {"operation_kind": "block", "operation_index": 3, "block_ids": ["block_0001"],
                   "source_page_index": 1, "source_page_count": 4, "page_count_basis": "content_blocks",
                   "section_id": "section:0001", "unit_id": None, "message": PRIVATE, "url": PRIVATE}
        cases = (
            (TableRenderError("table_render_geometry", block_index=3), "table_render_geometry"),
            (DocumentIntegrityError("DocumentIR→DOCX", {"blocking_quality_flags": ["ir_docx_integrity:table_count_mismatch"], "private": PRIVATE}), "ir_docx_integrity:table_count_mismatch"),
            (ValueError(PRIVATE), "ValueError"),
        )
        for error, reason in cases:
            setattr(error, FAILURE_CONTEXT_ATTRIBUTE, deepcopy(context))
            before = deepcopy(vars(error))
            with self.subTest(error=type(error).__name__, reason=reason):
                evidence = policy.worker_failure_evidence(error)
                self.assertEqual(evidence["failure_context"], {
                    **{key: value for key, value in context.items() if key not in {"message", "url"}},
                    "reason_code": reason,
                })
                self.assertNotIn(PRIVATE, json.dumps(evidence, ensure_ascii=False))
                self.assertEqual(vars(error), before)
        for error in (DocumentIntegrityError("DocumentIR→DOCX", {}), TableEvidenceError("table_evidence_integrity")):
            setattr(error, FAILURE_CONTEXT_ATTRIBUTE, context)
            self.assertNotIn("failure_context", policy.worker_failure_evidence(error))
        # 固定 code 优先于完整性阻断码；不合法 code 由既有白名单丢弃整个定位。
        error = cases[1][0]
        error.code = "table_render_geometry"
        self.assertEqual(policy.worker_failure_evidence(error)["failure_context"]["reason_code"], "table_render_geometry")
        error.code = PRIVATE
        self.assertNotIn("failure_context", policy.worker_failure_evidence(error))

    def test_placeholder_context_keeps_controlled_codes_and_filters_private_fields(self):
        context = {"operation_kind": "table_placeholder", "block_ids": ["block_0001"],
                   "source_page_index": 0, "source_page_count": 3, "page_count_basis": "content_blocks",
                   "message": PRIVATE, "url": PRIVATE, "html": PRIVATE, "bbox": [1, 2, 3, 4]}
        for code in ("table_placeholder_geometry_invalid", "table_placeholder_crop_failed",
                     "table_placeholder_source_unavailable", "table_placeholder_integrity_failed"):
            error = TablePlaceholderError(code)
            setattr(error, FAILURE_CONTEXT_ATTRIBUTE, context)
            with self.subTest(code=code):
                evidence = policy.worker_failure_evidence(error)
                self.assertEqual(evidence["failure_context"]["reason_code"], code)
                self.assertNotIn(PRIVATE, json.dumps(evidence, ensure_ascii=False))
                self.assertNotIn("bbox", evidence["failure_context"])
        for bad in ({"block_ids": [PRIVATE]}, {"operation_kind": PRIVATE}, {"block_ids": ["block"] * 21}):
            setattr(error, FAILURE_CONTEXT_ATTRIBUTE, {**context, **bad})
            self.assertNotIn("failure_context", policy.worker_failure_evidence(error))
        for page in (-1, True, "2"):
            setattr(error, FAILURE_CONTEXT_ATTRIBUTE, {**context, "source_page_index": page,
                                                       "source_page_count": -2, "page_count_basis": PRIVATE})
            safe = policy.worker_failure_evidence(error)["failure_context"]
            self.assertEqual((safe["source_page_index"], safe["source_page_count"], safe["page_count_basis"]),
                             (None, None, None))

    def test_baseline_empty_evidence_and_sensitive_exception_text(self):
        for error, _, _, _ in _cases():
            with self.subTest(error=type(error).__name__):
                evidence = policy.worker_failure_evidence(error)
                text = json.dumps(evidence, ensure_ascii=False) + policy.worker_failure_message(error)
                for secret in ("正文-B04", "B04-secret", "user:pass", "/private", "B04-token", "#secret"):
                    self.assertNotIn(secret, text)
                if isinstance(error, DocumentIntegrityError):
                    self.assertEqual(evidence, {"blocking_quality_flags": ["ir_docx_integrity:table_count_mismatch"],
                                                "blocking_quality_flags_unknown_count": 0})
                elif isinstance(error, MinerUArtifactValidationError):
                    expected = deepcopy(MINERU_EVIDENCE)
                    expected.pop("mineru_validation_input")
                    expected["mineru_validation"]["inventory"] = {}
                    expected["mineru_validation"]["content_list_path"] = None
                    self.assertEqual(evidence, expected)
                else:
                    self.assertEqual(evidence, {})

    def test_baseline_mineru_reports_and_validation_input(self):
        report = MinerUValidationReport(package_sha256="a" * 64, can_convert=False,
                                       content_list_path=PRIVATE, inventory={"raw_page_count": 3, "secret": PRIVATE})
        direct = MinerUArtifactValidationError(report)
        placeholder = TablePlaceholderError("table_placeholder_crop_failed")
        placeholder.mineru_validation_report = report
        for error in (direct, placeholder):
            for generation in (0, 2):
                binding = {"mineru_raw_result_file_id": "file_raw", "mineru_raw_result_sha256": "b" * 64,
                           "retry_count": generation}
                error.mineru_validation_input = {**binding, "private": PRIVATE}
                with self.subTest(error=type(error).__name__, generation=generation):
                    evidence = policy.worker_failure_evidence(error)
                    self.assertEqual(evidence, {**MINERU_EVIDENCE, "mineru_validation_input": binding})
                    self.assertNotIn(PRIVATE, json.dumps(evidence, ensure_ascii=False))


# 以下摘要由 79f20cef 原实现生成并固定；不把生产白名单函数作为测试期望生成器。
MINERU_EVIDENCE = {'mineru_validation': {'schema_version': 'mineru-artifact-validation/v1',
                       'validator_version': 'mineru-artifact-validator/v4',
                       'policy_version': 'mineru-input-policy/v2',
                       'package_sha256': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                       'content_list_sha256': None,
                       'details_truncated': False,
                       'omitted_issue_count': 0,
                       'complete': True,
                       'can_convert': False,
                       'table_check_count': 0,
                       'warning_count': 0,
                       'omitted_table_check_count': 0,
                       'fatal_count': 0,
                       'blocker_count': 0,
                       'warnings': [],
                       'blockers': [],
                       'table_checks': [],
                       'first_fatal': None,
                       'issue_counts': {'warning': {}, 'blocker': {}},
                       'inventory': {'raw_page_count': 3},
                       'effective_inventory': {},
                       'normalization': {}},
 'mineru_validation_input': {}}
