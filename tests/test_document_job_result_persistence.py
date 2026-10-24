"""结果凭据的真实 adapter 竞争、进程中断恢复和内容可见性合同。"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from dataclasses import replace
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import io
import zipfile
from xml.etree import ElementTree
from threading import Event, current_thread
from unittest import TestCase
from unittest.mock import Mock, patch

from docx import Document

from app.core.errors import ApiError
from app.domains.document_jobs.router import _build_download_token
from app.domains.document_jobs.models import DocumentJobPreparedResult, DocumentJobRecord
from app.domains.files.models import DocumentFileRecord
from app.domains.files.retention import DocumentFileRetentionPlanner
from app.domains.resources.models import utc_now
from app.infrastructure.persistence import build_file_persistence_adapters, build_sqlite_persistence_adapters
from app.services.document_ir.models import DocumentIR, DocumentIRBlock, DocumentIRMetadata
from app.services.renderer.evidence import (build_renderer_evidence, build_renderer_aggregate_evidence,
    build_renderer_event_summary, validate_render_result, LEGACY_RENDERER_EVIDENCE_KEYS)
from tests import test_database_job_repository as persistence
from tests import test_fastapi_jobs_backend as fixtures
from tests import test_document_job_execution_stages as stages
from tests.test_image_group_rendering import legacy_image_docx, image_ir, image_loader, change_docx, NS
from app.services.renderer import image_evidence
from app.services.renderer.word_renderer import DocumentIRRenderOptions


class SimulatedProcessExit(BaseException):
    """不经过 Worker 的异常收尾，用于模拟四个持久化点的进程中断。"""


def _adapters(kind, root):
    root = Path(root)
    if kind == "file":
        return build_file_persistence_adapters(root)
    return build_sqlite_persistence_adapters(root / "metadata.sqlite3")


def _candidate(file_id="candidate", *, generation=0, ir_id="ir"):
    now = utc_now()
    return DocumentFileRecord(
        id=file_id, tenant_id="tenant", company_id="company", job_id="job", created_by="operator",
        file_type="generated_word", storage_provider="local_file", bucket="local-file",
        object_key=f"document-files/tenant/{file_id}/result.docx", original_filename="result.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=7, checksum_sha256=f"sha256:{hashlib.sha256(b'payload').hexdigest()}", etag="etag",
        status="uploaded", expires_at=now + timedelta(days=1), created_at=now, updated_at=now,
        metadata={"document_job_result_protocol": 1, "retry_count": generation, "document_ir_file_id": ir_id,
                  "source_integrity": {}, "docx_quality": {}, "blocking_quality_flags": []},
    )


def _job():
    return DocumentJobRecord(id="job", tenant_id="tenant", company_id="company", created_by="operator",
                             source_file_id="source", template_version_id="default@2", status="running",
                             stage="uploading", document_ir_file_id="ir", timeout_at=utc_now() + timedelta(minutes=5))


def _process_compete(kind, root, action, descriptor, ready, start, output):
    repository = _adapters(kind, root).document_job_repository
    ready.put(True)
    if not start.wait(15):
        raise RuntimeError("等待竞争开始超时。")
    if action == "prepare":
        job = repository.prepare_document_job_result("job", expected_retry_count=0,
            expected_document_ir_file_id="ir", candidate=DocumentFileRecord.model_validate(descriptor))
        output.put(job.prepared_result.file.id if job else None)
    else:
        job = repository.retry_document_job("job", expected_retry_count=0, max_retries=2,
            status="running", stage="rendering", retry_count=1, updated_at=utc_now())
        output.put(job.retry_count if job else None)


def _process_exit_with_lock(kind, root, locked, exit_now):
    repository = _adapters(kind, root).document_job_repository
    with repository._locked_job("job") as (connection, existing):
        # SQLite 写入未提交后退出，必须回滚；file 的锁由独立 inode 承载。
        if kind == "sqlite":
            repository._write_job(connection, existing.model_copy(update={"progress": 88}))
        locked.set()
        exit_now.wait(15)
        os._exit(0)


class DocumentJobResultPersistenceTests(TestCase):
    _upload_source_pdf = fixtures.FastAPIJobsBackendTests._upload_source_pdf
    _create = stages.DocumentJobExecutionStageTests._create
    _files = stages.DocumentJobExecutionStageTests._files
    _pause_after_ir = stages.DocumentJobExecutionStageTests._pause_after_ir

    def _install_toc_ir(self, runtime, job):
        """登记真实 TOC 归并与独立尾段的合成 IR，供导航和恢复合同共用。"""
        blocks = [DocumentIRBlock(id=block_id, type="paragraph", order=index, text=text,
            metadata={"source_type": "text"}) for index, (block_id, text) in enumerate((
                ("first", "1 Overview ........ 3"), ("merged", "2 Detail ........ 4"),
                ("tail", "Ordinary body tail.")))]
        ir = DocumentIR(metadata=DocumentIRMetadata(job_id=job.id, source_file_id=job.source_file_id,
            document_language="en", source_block_count=len(blocks), source_type_counts={"text": len(blocks)}),
            blocks=blocks)
        ir_file = runtime.file_upload_service.register_generated_content(
            tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
            file_type="document_ir", filename="toc.document-ir.json", mime_type="application/json",
            content=ir.model_dump_json().encode(), metadata={})
        return runtime.document_job_repository.update_document_job(job.id, document_ir_file_id=ir_file.id), ir

    def _install_formula_ir(self, runtime, execution, job, source=r"$\unknown{VOUT}$"):
        """登记新的合成最终 IR，保留源清单与现有结构，不覆写历史文件。"""
        original = execution._get_document_ir_file(job)
        ir = DocumentIR.model_validate_json(runtime.file_upload_service.read_file_content(original))
        block = next(block for block in ir.blocks if block.type == "paragraph")
        ir = ir.model_copy(update={"blocks": [
            item.model_copy(update={"text": source}) if item.id == block.id else item for item in ir.blocks
        ]})
        ir_file = runtime.file_upload_service.register_generated_content(
            tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
            file_type="document_ir", filename="formula.document-ir.json", mime_type="application/json",
            content=ir.model_dump_json().encode(), metadata=original.metadata,
        )
        return runtime.document_job_repository.update_document_job(job.id, document_ir_file_id=ir_file.id), ir

    def _install_image_ir(self, runtime, execution, job, *, variant="original", image_count=2, annotations=True):
        """登记指定数量的中性图片最终 IR，不修改历史资产或原 IR。"""
        ir = image_ir(image_count, annotations=annotations)
        ir.metadata = ir.metadata.model_copy(update={"job_id": job.id, "source_file_id": job.source_file_id,
            "source_block_count": image_count, "source_type_counts": {"image": image_count}})
        for block in ir.blocks:
            block.metadata["source_type"] = "image"
        if variant != "original":
            ir.blocks[0].captions = ["Figure 99: current generation has different source"]
        file_ids = []
        for asset in ir.assets:
            file = runtime.file_upload_service.register_generated_content(
                tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                file_type="image_asset", filename=asset.id + ".png", mime_type="image/png",
                content=image_loader(asset), metadata={},
            )
            asset.file_id = file.id
            file_ids.append(file.id)
        ir_file = runtime.file_upload_service.register_generated_content(
            tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
            file_type="document_ir", filename="images.document-ir.json", mime_type="application/json",
            content=ir.model_dump_json().encode(), metadata={},
        )
        return runtime.document_job_repository.update_document_job(job.id, document_ir_file_id=ir_file.id,
            image_asset_file_ids=file_ids), ir

    def _image_recovery_case(self, entry, writer_policy, damage=None):
        """可供正常构建与实际 B1 reader 选择器复用的三入口验收。"""
        with self._runtime() as (root, runtime, execution, job, _client, _headers):
            job, ir = self._install_image_ir(runtime, execution, job)
            config = root / "history-layout.yaml"
            rules = root / "history-format.yaml"
            config.write_text("schema_version: template-config/v1\npage_setup:\n  page_width_cm: 19\n  left_margin: 1\n  right_margin: 1\n", encoding="utf-8")
            rules.write_text("subscript_rules:\n  symbols:\n    DemoToken: PRIVATE_FORMAT_SENTINEL\n", encoding="utf-8")
            with patch.object(image_evidence, "IMAGE_GENERATION_POLICY", writer_policy):
                rendered = execution.word_renderer.render_to_result(ir, template_path=None, config_path=config,
                    image_loader=execution._build_image_loader(job), options=DocumentIRRenderOptions(
                        subscript_config_path=rules, template_version_id=job.template_version_id))
            metadata = build_renderer_evidence(ir, rendered.content, formula_report=rendered.formula_report,
                image_layout_report=rendered.image_layout_report, expected_template_version_id=job.template_version_id,
                expected_generation_policy=writer_policy)
            content = rendered.content
            if damage == "annotation":
                def change(root):
                    note = next(node for node in root.findall(".//w:t", NS) if node.text == "Note 1: extra")
                    note.text = "Changed note"
                content = change_docx(content, change)
            elif damage == "missing_report":
                metadata.pop("image_layout_report")
            elif damage == "missing_both_reports":
                metadata.pop("image_layout_report")
                metadata.pop("image_layout_summary")
            elif damage == "missing_inputs":
                metadata["image_layout_report"].pop("render_inputs")
            elif damage == "private_style":
                report = metadata["image_layout_report"]
                report["render_inputs"]["caption_style"]["font_size"] = "PRIVATE_FORMAT_SENTINEL"
                report["render_inputs_sha256"] = image_evidence.canonical_sha256(report["render_inputs"])
            elif damage == "unknown_version":
                report = metadata["image_layout_report"]
                report["render_inputs"]["projection_version"] = "unknown/v9"
                report["render_inputs_sha256"] = image_evidence.canonical_sha256(report["render_inputs"])
            elif damage == "wrong_template":
                metadata["template_version_id"] = "other@9"
            word = runtime.file_upload_service.register_generated_content(
                tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                file_type="generated_word", filename="images.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                content=content, metadata={"retry_count": job.retry_count, "document_ir_file_id": job.document_ir_file_id,
                    "template_version_id": job.template_version_id, **metadata},
            )
            # 首次报告绑定由元数据单独保存；之后当前配置和路径不再是恢复来源。
            config.unlink(); rules.unlink()
            job = runtime.document_job_repository.update_document_job(job.id, stage="uploading")
            if entry == "explicit":
                job, _new_ir = self._install_image_ir(runtime, execution, job, variant="current")
                job = runtime.document_job_repository.update_document_job(job.id, retry_count=1,
                    result_file_id=word.id, template_version_id="current-other@9")
            elif entry == "receipt":
                job = runtime.document_job_repository.prepare_document_job_result(job.id,
                    expected_retry_count=job.retry_count, expected_document_ir_file_id=job.document_ir_file_id, candidate=word)
            with patch.object(execution.word_renderer, "render_to_result") as rerender, patch.object(
                execution.template_read_service, "resolve_template_version", side_effect=AssertionError("恢复不得读取当前模板")):
                result = execution.execute_job(job.id)
            rerender.assert_not_called()
            if damage:
                self.assertEqual((result.status, result.failed_stage, result.error_code), ("failed", "uploading", "oss_failed"))
                self.assertEqual(result.prepared_result, job.prepared_result)
                self.assertNotIn("PRIVATE_FORMAT_SENTINEL", result.error_message)
            else:
                self.assertEqual((result.status, result.result_file_id), ("succeeded", word.id), result.error_message)
            for event in runtime.document_job_event_repository.list_document_job_events(job.id):
                self.assertNotIn("image_layout_report", event.payload)
                self.assertNotIn("PRIVATE_FORMAT_SENTINEL", str(event.payload))

    def test_image_report_all_recovery_entries_use_frozen_original_inputs(self):
        for writer_policy in ("grouped/v1", "single-only/v1"):
            for entry in ("legacy", "explicit", "receipt"):
                with self.subTest(writer_policy=writer_policy, entry=entry):
                    self._image_recovery_case(entry, writer_policy)

    def test_image_report_all_recovery_entries_reject_corruption_without_reselection(self):
        for damage in ("annotation", "missing_report", "missing_both_reports", "missing_inputs", "private_style", "unknown_version", "wrong_template"):
            for entry in ("legacy", "explicit", "receipt"):
                with self.subTest(damage=damage, entry=entry):
                    self._image_recovery_case(entry, "grouped/v1", damage)

    @contextmanager
    def _image_result_without_report_fields(self, writer_policy, image_count, *, marker_free=False):
        """删除完整报告字段集，防止残留计数键替测试触发新 reader。"""
        with self._runtime() as (_root, runtime, execution, job, _client, _headers):
            job, ir = self._install_image_ir(runtime, execution, job, image_count=image_count, annotations=False)
            with patch.object(image_evidence, "IMAGE_GENERATION_POLICY", writer_policy):
                rendered = execution.word_renderer.render_to_result(
                    ir, template_path=None, config_path=None, image_loader=execution._build_image_loader(job),
                    options=DocumentIRRenderOptions(template_version_id=job.template_version_id),
                )
            metadata = build_renderer_evidence(ir, rendered.content, formula_report=rendered.formula_report,
                image_layout_report=rendered.image_layout_report, expected_template_version_id=job.template_version_id)
            report_keys = image_evidence.IMAGE_EVIDENCE_KEYS | {"formula_report", "formula_summary"}
            self.assertTrue(report_keys.issubset(metadata))
            for key in report_keys:
                metadata.pop(key)
            content = legacy_image_docx(rendered.content) if marker_free else rendered.content
            with zipfile.ZipFile(io.BytesIO(content)) as package:
                self.assertFalse(ElementTree.fromstring(package.read("word/document.xml")).findall(".//w:tbl", NS))
            self.assertEqual(image_evidence.has_image_markers(content), not marker_free)
            word = runtime.file_upload_service.register_generated_content(
                tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                file_type="generated_word", filename="without-reports.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                content=content, metadata={"retry_count": job.retry_count, "document_ir_file_id": job.document_ir_file_id,
                    "template_version_id": job.template_version_id, **metadata},
            )
            self.assertNotIn("document_job_result_protocol", word.metadata)
            self.assertFalse(report_keys.intersection(word.metadata))
            job = runtime.document_job_repository.update_document_job(job.id, stage="uploading")
            yield runtime, execution, job, word

    def test_legacy_missing_all_reports_rejects_image_markers_before_candidate_selection(self):
        for policy, count in (("grouped/v1", 1), ("single-only/v1", 2)):
            with self.subTest(policy=policy), self._image_result_without_report_fields(policy, count) as (
                runtime, execution, job, _word,
            ):
                self.assertIsNone(job.prepared_result)
                with self.assertRaisesRegex(ValueError, "图片布局标记"):
                    execution._get_existing_result_file(job)
                self.assertIsNone(runtime.document_job_repository.get_document_job(job.id).prepared_result)

    def test_missing_all_reports_three_recovery_entries_preserve_receipt_and_do_not_rerender(self):
        for policy, count in (("grouped/v1", 1), ("single-only/v1", 2)):
            for entry in ("legacy", "explicit", "receipt"):
                with self.subTest(policy=policy, entry=entry), self._image_result_without_report_fields(policy, count) as (
                    runtime, execution, job, word,
                ):
                    if entry == "explicit":
                        job = runtime.document_job_repository.update_document_job(job.id, result_file_id=word.id)
                    elif entry == "receipt":
                        job = runtime.document_job_repository.prepare_document_job_result(job.id,
                            expected_retry_count=job.retry_count, expected_document_ir_file_id=job.document_ir_file_id,
                            candidate=word)
                    with patch.object(execution.word_renderer, "render_to_result") as render, patch.object(
                        runtime.document_job_repository, "prepare_document_job_result",
                        wraps=runtime.document_job_repository.prepare_document_job_result,
                    ) as select, patch.object(runtime.document_file_repository, "materialize_prepared_result",
                        wraps=runtime.document_file_repository.materialize_prepared_result,
                    ) as materialize:
                        result = execution.execute_job(job.id)
                    self.assertEqual((result.status, result.failed_stage, result.error_code),
                        ("failed", "uploading", "oss_failed"))
                    self.assertEqual(result.prepared_result, job.prepared_result)
                    self.assertEqual(result.result_file_id, job.result_file_id)
                    self.assertEqual(runtime.document_file_repository.get_document_file(word.id).metadata, word.metadata)
                    render.assert_not_called()
                    select.assert_not_called()
                    if entry != "receipt":
                        materialize.assert_not_called()

    def test_marker_free_legacy_single_images_without_report_fields_still_recover(self):
        for policy, count in (("grouped/v1", 1), ("single-only/v1", 2)):
            with self.subTest(policy=policy), self._image_result_without_report_fields(policy, count, marker_free=True) as (
                runtime, execution, job, word,
            ):
                self.assertEqual(execution._get_existing_result_file(job).id, word.id)
                with patch.object(execution.word_renderer, "render_to_result") as render:
                    result = execution.execute_job(job.id)
                self.assertEqual((result.status, result.result_file_id), ("succeeded", word.id), result.error_message)
                self.assertEqual(result.prepared_result.file.id, word.id)
                render.assert_not_called()

    def test_formula_fallback_quality_summary_and_events_use_selected_result(self):
        for quality, expected in (("pending", "pending"), ("blocked", "blocked"), ("passed", "warning"), ("warning", "warning")):
            with self.subTest(quality=quality), self._runtime() as (root, runtime, execution, job, client, headers):
                job, ir = self._install_formula_ir(runtime, execution, job)
                runtime.document_job_repository.update_document_job(
                    job.id, quality_status=quality, quality_summary={"retained": {"check": "existing"}},
                )
                result = execution.execute_job(job.id)
                self.assertEqual(result.status, "succeeded", result.error_message)
                self.assertEqual(result.quality_status, expected)
                self.assertEqual(result.quality_summary["retained"], {"check": "existing"})
                self.assertEqual(result.quality_summary["formula"]["fallback_count"], 1)
                self.assertEqual((result.review_status, result.delivery_status), ("unreviewed", "internal_draft"))
                word = runtime.document_file_repository.get_document_file(result.result_file_id)
                self.assertEqual(word.metadata["formula_summary"], result.quality_summary["formula"])
                events = runtime.document_job_event_repository.list_document_job_events(job.id)
                for event in events:
                    self.assertNotIn("formula_report", event.payload)
                    self.assertNotIn("latex_residue_examples", event.payload.get("docx_quality", {}))
                    self.assertNotIn(r"\unknown{VOUT}", str(event.payload))
                # blocked 与 unreviewed 仍是内部可下载草稿，发布资格由现有服务判断。
                response = client.get(f"/api/v1/document-jobs/{job.id}/download-url", headers=headers)
                self.assertEqual(response.status_code, 200, response.text)

    def test_formula_report_all_recovery_entries_reject_changed_output(self):
        for entry in ("legacy", "explicit", "receipt"):
            for corrupt in (False, True):
                with self.subTest(entry=entry, corrupt=corrupt), self._runtime() as (root, runtime, execution, job, client, headers):
                    job, ir = self._install_formula_ir(runtime, execution, job, source="$x^2+3$")
                    template = execution.template_read_service.resolve_template_version(job.template_version_id)
                    rendered = execution.word_renderer.render_to_result(
                        ir, template_path=template.template_path, config_path=template.layout_config_path,
                        image_loader=execution._build_image_loader(job),
                    )
                    content = legacy_image_docx(rendered.content)
                    evidence = build_renderer_evidence(ir, content, formula_report=rendered.formula_report)
                    if corrupt:
                        # 保留 anchor/mode/count 与原报告，只改最终字节中的一个数学值。
                        altered = io.BytesIO()
                        with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(altered, "w") as target:
                            for item in source.infolist():
                                data = source.read(item.filename)
                                if item.filename == "word/document.xml":
                                    xml = ElementTree.fromstring(data)
                                    math = xml.find(".//{http://schemas.openxmlformats.org/officeDocument/2006/math}t")
                                    self.assertIsNotNone(math)
                                    math.text = "9"
                                    data = ElementTree.tostring(xml, encoding="utf-8", xml_declaration=True)
                                target.writestr(item, data)
                        content = altered.getvalue()
                    word = runtime.file_upload_service.register_generated_content(
                        tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                        file_type="generated_word", filename="recovered.docx",
                        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        content=content, metadata={"retry_count": job.retry_count,
                            "document_ir_file_id": job.document_ir_file_id, **evidence},
                    )
                    job = runtime.document_job_repository.update_document_job(job.id, stage="uploading")
                    if entry == "explicit":
                        # 明确指针维持旧代复用；仍按旧文件 IR 校验，不导入新代摘要。
                        new_job, _ir = self._install_formula_ir(runtime, execution, job, source="$y^3$")
                        job = runtime.document_job_repository.update_document_job(
                            job.id, retry_count=1, result_file_id=word.id,
                        )
                    elif entry == "receipt":
                        job = runtime.document_job_repository.prepare_document_job_result(
                            job.id, expected_retry_count=job.retry_count,
                            expected_document_ir_file_id=job.document_ir_file_id, candidate=word,
                        )
                    with patch.object(execution.word_renderer, "render_to_result") as render:
                        result = execution.execute_job(job.id)
                    render.assert_not_called()
                    if corrupt:
                        self.assertEqual((result.status, result.failed_stage, result.error_code), ("failed", "uploading", "oss_failed"))
                        self.assertEqual(result.prepared_result, job.prepared_result)
                    else:
                        self.assertEqual((result.status, result.result_file_id), ("succeeded", word.id), result.error_message)
                        if entry == "explicit":
                            self.assertNotIn("formula", result.quality_summary)
                        else:
                            self.assertEqual(result.quality_summary["formula"], evidence["formula_summary"])

    def _build_runtime(self, root, kind):
        return fixtures.build_test_runtime(
            root, repository_factory=lambda path: _adapters(kind, path),
            jobs_artifact_storage_backend="local_object", auth_jwt_secret_key="test-jwt-secret",
            auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
        )

    @contextmanager
    def _runtime(self, kind="file", *, preview=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = self._build_runtime(root, kind)
            execution = runtime.document_job_execution_service
            with fixtures.TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                job = self._pause_after_ir(runtime, execution, client, headers)
                if not preview:
                    # 既有receipt/公式/图片合同使用历史无预览快照，组合行为在专用预览测试验证。
                    snapshot = {key: value for key, value in job.request_snapshot.items() if key != "word_preview"}
                    job = runtime.document_job_repository.update_document_job(job.id, request_snapshot=snapshot)
                yield root, runtime, execution, job, client, headers

    def _assert_result_bytes(self, runtime, result):
        self.assertEqual(result.status, "succeeded", result.error_message)
        files = self._files(runtime, result.id, "generated_word")
        uploaded = [file for file in files if file.status == "uploaded"]
        self.assertEqual([file.id for file in uploaded], [result.result_file_id])
        self.assertEqual(result.prepared_result.file.id, result.result_file_id)
        file = uploaded[0]
        content = runtime.file_upload_service.read_file_content(file)
        self.assertEqual(file.size_bytes, len(content))
        self.assertEqual(file.checksum_sha256, f"sha256:{hashlib.sha256(content).hexdigest()}")
        ir_file = runtime.document_file_repository.get_document_file(result.document_ir_file_id)
        ir = DocumentIR.model_validate_json(runtime.file_upload_service.read_file_content(ir_file))
        self.assertTrue(all(file.metadata[key] == value for key, value in build_renderer_evidence(ir, content).items() if key != "render_trace_status"))
        self.assertEqual(file.metadata["render_trace_status"], "complete")
        self.assertEqual(file.metadata["block_render_evidence"]["docx_sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(len({file.object_key for file in files}), len(files))
        return files

    def test_actual_render_upload_interleaving_selects_one_result_and_isolates_bytes(self):
        for kind in ("file", "sqlite"):
            for interrupted_winner in (False, True):
                with self.subTest(kind=kind, interrupted_winner=interrupted_winner), self._runtime(kind) as (
                    root, runtime, execution, job, client, headers,
                ):
                    entered, release = Event(), Event()
                    original_write = runtime.file_upload_service._write_object
                    original_materialize = runtime.document_file_repository.materialize_prepared_result
                    original_render = execution.word_renderer.render_to_result
                    rendered = []

                    def render(*args, **kwargs):
                        # 在正式 renderer 读取/冻结前产生两个有效模板；bytes 与 trace 始终同次。
                        template = Document(str(kwargs["template_path"]))
                        template.core_properties.comments = current_thread().name
                        with tempfile.NamedTemporaryFile(suffix=".docx", dir=root) as stream:
                            template.save(stream.name)
                            same_call = original_render(*args, **{**kwargs, "template_path": Path(stream.name)})
                        validate_render_result(args[0], same_call.content, same_call)
                        rendered.append(same_call)
                        return same_call

                    def write(record, content):
                        if current_thread().name.startswith("late-uploader") and record.file_type == "generated_word":
                            entered.set()
                            if not release.wait(15):
                                raise RuntimeError("上传屏障等待超时。")
                        return original_write(record, content)

                    def materialize(descriptor):
                        if interrupted_winner and not current_thread().name.startswith("late-uploader"):
                            raise SimulatedProcessExit()
                        return original_materialize(descriptor)

                    with patch.object(runtime.file_upload_service, "_write_object", side_effect=write), patch.object(
                        runtime.document_file_repository, "materialize_prepared_result", side_effect=materialize,
                    ), patch.object(execution.word_renderer, "render_to_result", side_effect=render), ThreadPoolExecutor(max_workers=1, thread_name_prefix="late-uploader") as pool:
                        late = pool.submit(execution.execute_job, job.id)
                        try:
                            self.assertTrue(entered.wait(15))
                            if interrupted_winner:
                                with self.assertRaises(SimulatedProcessExit):
                                    execution.execute_job(job.id)
                                selected = runtime.document_job_repository.get_document_job(job.id)
                                self.assertIsNotNone(selected.prepared_result)
                            else:
                                selected = execution.execute_job(job.id)
                            release.set()
                            result = late.result(timeout=15)
                        finally:
                            release.set()
                    files = self._assert_result_bytes(runtime, result)
                    winner = next(file for file in files if file.id == result.result_file_id)
                    actual = [item for item in rendered if "sha256:" + hashlib.sha256(item.content).hexdigest() == winner.checksum_sha256]
                    self.assertEqual(len(actual), 1)
                    self.assertEqual(winner.metadata["render_plan"], actual[0].plan.model_dump(mode="json"))
                    self.assertEqual(winner.metadata["block_render_evidence"], actual[0].block_evidence.model_dump(mode="json"))
                    self.assertEqual(result.result_file_id, selected.prepared_result.file.id)
                    self.assertEqual(sorted(file.status for file in files), ["pending_upload", "uploaded"])
                    self.assertEqual(len({file.checksum_sha256 for file in files}), 2)
                    loser = next(file for file in files if file.id != result.result_file_id)
                    listed = client.get(f"/api/v1/document-jobs/{job.id}/files", headers=headers)
                    self.assertNotIn(loser.id, str(listed.json()))
                    denied = client.get(f"/api/v1/document-jobs/{job.id}/download-url", params={"file_id": loser.id}, headers=headers)
                    self.assertEqual(denied.status_code, 409)
                    token = _build_download_token(runtime, job_id=job.id, file_id=loser.id, expires_at=utc_now() + timedelta(minutes=5))
                    self.assertEqual(client.get(f"/api/v1/document-jobs/{job.id}/download", params={"token": token}).status_code, 409)
                    self.assertFalse(any(event.event_type == "stage_failed" for event in
                        runtime.document_job_event_repository.list_document_job_events(job.id)))

    def test_four_interruptions_restart_service_and_preserve_selected_identity(self):
        for kind in ("file", "sqlite"):
            for point in ("pending", "object", "receipt", "materialized"):
                with self.subTest(kind=kind, point=point), self._runtime(kind, preview=True) as (
                    root, runtime, execution, job, client, headers,
                ):
                    target = runtime.document_file_repository if point in {"pending", "materialized"} else (
                        runtime.file_upload_service if point == "object" else runtime.document_job_repository)
                    method = {"pending": "create_document_file", "object": "_write_object",
                              "receipt": "prepare_document_job_result", "materialized": "materialize_prepared_result"}[point]
                    original = getattr(target, method)

                    def interrupt(*args, **kwargs):
                        value = original(*args, **kwargs)
                        raise SimulatedProcessExit()

                    with patch.object(target, method, side_effect=interrupt), self.assertRaises(SimulatedProcessExit):
                        execution.execute_job(job.id)
                    before = runtime.document_job_repository.get_document_job(job.id)
                    before_files = self._files(runtime, job.id, "generated_word")
                    self.assertEqual(len(before_files), 1)
                    restarted = self._build_runtime(root, kind)
                    new_execution = restarted.document_job_execution_service
                    write = Mock()
                    original_write = restarted.file_upload_service._write_object

                    def observe_primary_write(record, content):
                        # 预览追加独立manifest，原断言继续保护主DOCX不重写。
                        if record.file_type == "generated_word":
                            write(record, content)
                        return original_write(record, content)

                    with patch.object(new_execution.word_renderer, "render_to_result", wraps=new_execution.word_renderer.render_to_result) as render, patch.object(
                        restarted.file_upload_service, "_write_object", side_effect=observe_primary_write,
                    ):
                        result = new_execution.execute_job(job.id)
                    files = self._assert_result_bytes(restarted, result)
                    self.assertEqual(len(self._files(restarted, job.id, "word_preview_manifest")), 1)
                    if point in {"receipt", "materialized"}:
                        self.assertEqual(result.result_file_id, before.prepared_result.file.id)
                        render.assert_not_called()
                        write.assert_not_called()
                        self.assertEqual(len(files), 1)
                        after_file = files[0]
                        self.assertEqual(after_file.expires_at, before_files[0].expires_at)
                        self.assertEqual(after_file.metadata, before_files[0].metadata)
                    else:
                        self.assertEqual(len(files), 2)
                        self.assertNotEqual(result.result_file_id, before_files[0].id)
                        self.assertEqual(render.call_count, 1)
                        self.assertEqual(write.call_count, 1)

    def test_selected_receipt_rejects_stale_rollback_and_candidate_failure(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self._runtime(kind) as (root, runtime, execution, job, client, headers):
                repo = runtime.document_job_repository
                original_prepare = repo.prepare_document_job_result

                def prepare(*args, **kwargs):
                    selected = original_prepare(*args, **kwargs)
                    raise SimulatedProcessExit()

                with patch.object(repo, "prepare_document_job_result", side_effect=prepare), self.assertRaises(SimulatedProcessExit):
                    execution.execute_job(job.id)
                selected = repo.get_document_job(job.id)
                self.assertIsNone(repo.update_document_job_if_current(job.id, allowed_statuses={"running"},
                    allowed_stages={"uploading"}, expected_retry_count=0,
                    expected_document_ir_file_id=job.document_ir_file_id, require_no_prepared_result=True, stage="rendering"))
                failed = execution._mark_failed(selected.model_copy(update={"prepared_result": None}), failed_stage="uploading",
                    error_code="oss_failed", error_message="落选候选的迟到失败", trace_id=None)
                self.assertEqual(failed.prepared_result, selected.prepared_result)
                self.assertEqual(failed.status, "running")
                self._assert_result_bytes(runtime, execution._render_and_save_word(job, trace_id=None))

    def test_late_outer_exception_does_not_fail_another_attempts_stage(self):
        with self._runtime() as (root, runtime, execution, job, client, headers):
            def fail_after_other_attempt(snapshot, **kwargs):
                with patch.object(execution, "_render_and_save_word", wraps=real_render):
                    runtime.document_job_repository.update_document_job(job.id, stage="uploading")
                    with patch.object(runtime.document_file_repository, "materialize_prepared_result", side_effect=SimulatedProcessExit):
                        with self.assertRaises(SimulatedProcessExit):
                            real_render(runtime.document_job_repository.get_document_job(job.id), trace_id=None)
                raise RuntimeError("旧调用退出时的迟到异常")

            real_render = execution._render_and_save_word
            with patch.object(execution, "_render_and_save_word", side_effect=fail_after_other_attempt):
                result = execution.execute_job(job.id)
            self.assertEqual(result.status, "running")
            self.assertIsNotNone(result.prepared_result)
            self._assert_result_bytes(runtime, execution.execute_job(job.id))

    def test_cancel_timeout_and_generation_change_during_candidate_upload(self):
        for kind in ("file", "sqlite"):
            for action in ("cancel", "timeout", "retry", "different_ir"):
                with self.subTest(kind=kind, action=action), self._runtime(kind) as (
                    root, runtime, execution, job, client, headers,
                ):
                    original = runtime.file_upload_service._write_object
                    def write(record, content):
                        if record.file_type == "generated_word":
                            repo = runtime.document_job_repository
                            if action == "cancel":
                                response = client.post(f"/api/v1/document-jobs/{job.id}/cancel", headers=headers)
                                self.assertEqual(response.status_code, 200)
                            elif action == "timeout":
                                repo.update_document_job(job.id, timeout_at=utc_now() - timedelta(seconds=1))
                            elif action == "retry":
                                repo.update_document_job(job.id, status="failed", stage="failed", failed_stage="uploading")
                                repo.retry_document_job(job.id, expected_retry_count=0, max_retries=2,
                                    retry_count=1, status="running", stage="rendering")
                            else:
                                repo.update_document_job(job.id, document_ir_file_id="other-final-ir")
                        return original(record, content)
                    with patch.object(runtime.file_upload_service, "_write_object", side_effect=write):
                        result = execution.execute_job(job.id)
                    self.assertIsNone(result.result_file_id)
                    self.assertIsNone(result.prepared_result)
                    self.assertEqual([file.status for file in self._files(runtime, job.id, "generated_word")], ["pending_upload"])
                    if action == "timeout":
                        self.assertEqual((result.status, result.failed_stage, result.error_code), ("failed", "uploading", "document_job_timeout"))
                    elif action == "cancel":
                        self.assertEqual(result.status, "canceled")
                    else:
                        self.assertEqual(result.status, "running")

    def test_pending_selected_and_losing_candidates_are_hidden_from_lists_and_tokens(self):
        with self._runtime() as (root, runtime, execution, job, client, headers):
            with patch.object(runtime.document_file_repository, "materialize_prepared_result", side_effect=SimulatedProcessExit):
                with self.assertRaises(SimulatedProcessExit):
                    execution.execute_job(job.id)
            selected = runtime.document_job_repository.get_document_job(job.id)
            file_id = selected.prepared_result.file.id
            response = client.get(f"/api/v1/document-jobs/{job.id}/files", headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn(file_id, str(response.json()))
            response = client.get(f"/api/v1/document-jobs/{job.id}/download-url", params={"file_id": file_id}, headers=headers)
            self.assertEqual(response.status_code, 409, response.text)
            with self.assertRaises(ApiError):
                runtime.document_job_service.get_file_for_authorized_download(job.id, file_id=file_id)
            token = _build_download_token(runtime, job_id=job.id, file_id=file_id, expires_at=utc_now() + timedelta(minutes=5))
            self.assertEqual(client.get(f"/api/v1/document-jobs/{job.id}/download", params={"token": token}).status_code, 409)
            result = execution.execute_job(job.id)
            self.assertEqual(result.result_file_id, file_id)
            response = client.get(f"/api/v1/document-jobs/{job.id}/download-url", params={"file_id": file_id}, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            link = response.json()["download_url"]
            self.assertEqual(client.get(link).status_code, 200)
            runtime.document_job_repository.update_document_job(job.id, status="canceled", stage="canceled")
            self.assertEqual(client.get(link).status_code, 409)

    def test_materialization_failure_closes_selected_receipt_without_replacing_it(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self._runtime(kind) as (root, runtime, execution, job, client, headers):
                original = runtime.document_file_repository.materialize_prepared_result
                def expire(descriptor):
                    runtime.document_file_repository.update_document_file(descriptor.id, status="expired")
                    return original(descriptor)
                with patch.object(runtime.document_file_repository, "materialize_prepared_result", side_effect=expire):
                    result = execution.execute_job(job.id)
                self.assertEqual((result.status, result.failed_stage, result.error_code), ("failed", "uploading", "oss_failed"))
                self.assertIsNotNone(result.prepared_result)
                self.assertIsNone(result.result_file_id)
                before = len(self._files(runtime, job.id, "generated_word"))
                execution.execute_job(job.id)
                self.assertEqual(len(self._files(runtime, job.id, "generated_word")), before)

    def test_all_adapters_keep_receipt_across_patches_and_atomically_retry(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                database = persistence._FakeMysqlDatabase()
                adapters = _adapters(kind, directory) if kind != "mysql" else persistence.build_mysql_persistence_adapters(
                    persistence._mysql_config(), connect_factory=database.connect)
                repo, files = adapters.document_job_repository, adapters.document_file_repository
                job = _job()
                self.assertIsNone(DocumentJobRecord.model_validate(job.model_dump(exclude={"prepared_result"})).prepared_result)
                repo.create_document_job(job)
                with self.assertRaises(Exception):
                    repo.create_document_job(job.model_copy(update={"progress": 1}))
                first, second = _candidate("first"), _candidate("second")
                for candidate in (first, second):
                    files.create_document_file(candidate.model_copy(update={"status": "pending_upload", "etag": None}))
                selected = repo.prepare_document_job_result(job.id, expected_retry_count=0,
                    expected_document_ir_file_id="ir", candidate=first)
                repeated = repo.prepare_document_job_result(job.id, expected_retry_count=0,
                    expected_document_ir_file_id="ir", candidate=second)
                self.assertEqual(selected.prepared_result, repeated.prepared_result)
                self.assertIsNone(repo.update_document_job_if_current(job.id, allowed_statuses={"running"},
                    allowed_stages={"uploading"}, expected_retry_count=0, expected_document_ir_file_id="ir",
                    expected_prepared_result_file_id="second", status="succeeded", stage="completed", result_file_id="second"))
                patched = repo.update_document_job(job.id, translation_qa_note="非结果补丁保留凭据")
                self.assertEqual(patched.prepared_result, selected.prepared_result)
                self.assertIsNone(repo.prepare_document_job_result(job.id, expected_retry_count=1,
                    expected_document_ir_file_id="ir", candidate=second))
                self.assertIsNone(repo.prepare_document_job_result(job.id, expected_retry_count=0,
                    expected_document_ir_file_id="different", candidate=second))
                with self.assertRaises(ValueError):
                    repo.update_document_job_if_current(job.id, allowed_statuses={"running"}, allowed_stages={"uploading"},
                        require_no_prepared_result=True, expected_prepared_result_file_id="first", progress=99)
                repo.update_document_job(job.id, status="failed", stage="failed", failed_stage="uploading")
                next_job = repo.retry_document_job(job.id, expected_retry_count=0, max_retries=2,
                    retry_count=1, status="running", stage="rendering")
                self.assertEqual(next_job.retry_count, 1)
                self.assertIsNone(next_job.prepared_result)
                self.assertIsNone(repo.retry_document_job(job.id, expected_retry_count=0, max_retries=2,
                    retry_count=1, status="running", stage="rendering"))
                self.assertIsNone(repo.update_document_job_if_current(job.id, allowed_statuses={"running"},
                    allowed_stages={"rendering"}, expected_retry_count=0, status="failed", stage="failed"))
                if kind == "mysql":
                    self.assertTrue(any("from document_jobs where job_id = %s for update" in sql for sql in database.executed_sql))
                    self.assertFalse(any("insert into document_jobs" in sql and "duplicate key" in sql for sql in database.executed_sql))

    def test_descriptor_conflicts_and_expiry_never_revive_files(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                adapters = _adapters(kind, directory) if kind != "mysql" else persistence.build_mysql_persistence_adapters(
                    persistence._mysql_config(), connect_factory=persistence._FakeMysqlDatabase().connect)
                repo = adapters.document_file_repository
                descriptor = _candidate()
                pending = descriptor.model_copy(update={"status": "pending_upload", "etag": None})
                repo.create_document_file(pending)
                self.assertEqual(repo.create_document_file(pending), pending)
                with self.assertRaises(ValueError):
                    repo.create_document_file(pending.model_copy(update={"expires_at": pending.expires_at + timedelta(days=1)}))
                with self.assertRaises(ValueError):
                    repo.materialize_prepared_result(descriptor.model_copy(update={"metadata": {**descriptor.metadata, "new_evidence": True}}))
                materialized = repo.materialize_prepared_result(descriptor)
                self.assertEqual(repo.materialize_prepared_result(descriptor), materialized)
                self.assertEqual(materialized.expires_at, pending.expires_at)
                repo.update_document_file(descriptor.id, status="expired")
                with self.assertRaises(ValueError):
                    repo.materialize_prepared_result(descriptor)
                repo.update_document_file(descriptor.id, status="deleted")
                with self.assertRaises(ValueError):
                    repo.materialize_prepared_result(descriptor)
                with self.assertRaises(ValueError):
                    repo.update_document_file(descriptor.id, status="uploaded")

    def test_retention_expires_only_protocol_pending_and_materialization_loses_to_expiry(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                files = _adapters(kind, directory).document_file_repository
                descriptor = _candidate()
                now = descriptor.expires_at + timedelta(seconds=1)
                files.create_document_file(descriptor.model_copy(update={"status": "pending_upload", "etag": None}))
                source = descriptor.model_copy(update={"id": "source", "file_type": "source_pdf", "metadata": {}, "status": "pending_upload"})
                files.create_document_file(source)
                DocumentFileRetentionPlanner(files, retention_days=1).mark_expired(now=now)
                self.assertEqual(files.get_document_file(descriptor.id).status, "expired")
                self.assertEqual(files.get_document_file(source.id).status, "pending_upload")
                with self.assertRaises(ValueError):
                    files.materialize_prepared_result(descriptor)

    def test_prepare_refuses_foreign_expired_missing_generation_or_bad_quality(self):
        for field, value in (("tenant_id", "foreign"), ("company_id", "foreign"), ("job_id", "foreign"),
                             ("expires_at", utc_now() - timedelta(seconds=1)), ("checksum_sha256", None)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                repo = _adapters("sqlite", directory).document_job_repository
                repo.create_document_job(_job())
                with self.assertRaises(ValueError):
                    repo.prepare_document_job_result("job", expected_retry_count=0,
                        expected_document_ir_file_id="ir", candidate=_candidate().model_copy(update={field: value}))
        for metadata in ({}, {"retry_count": True}, {"retry_count": 0, "document_ir_file_id": "different"},
                         {"retry_count": 0, "document_ir_file_id": "ir", "blocking_quality_flags": ["missing"]}):
            with self.subTest(metadata=metadata), tempfile.TemporaryDirectory() as directory:
                repo = _adapters("sqlite", directory).document_job_repository
                repo.create_document_job(_job())
                with self.assertRaises(ValueError):
                    repo.prepare_document_job_result("job", expected_retry_count=0,
                        expected_document_ir_file_id="ir", candidate=_candidate().model_copy(update={"metadata": metadata}))

    def test_real_processes_serialize_prepare_and_double_retry(self):
        context = multiprocessing.get_context("spawn")
        for kind in ("file", "sqlite"):
            for action in ("prepare", "retry"):
                with self.subTest(kind=kind, action=action), tempfile.TemporaryDirectory() as directory:
                    repository = _adapters(kind, directory).document_job_repository
                    job = _job()
                    if action == "retry":
                        job = job.model_copy(update={"status": "failed", "stage": "failed"})
                    repository.create_document_job(job)
                    ready, output = context.Queue(), context.Queue()
                    start = context.Event()
                    processes = [context.Process(target=_process_compete,
                        args=(kind, directory, action, _candidate(f"candidate_{index}").model_dump(mode="json"), ready, start, output))
                        for index in range(2)]
                    try:
                        for process in processes:
                            process.start()
                        for _ in processes:
                            self.assertTrue(ready.get(timeout=15))
                        start.set()
                        results = [output.get(timeout=15) for _ in processes]
                        for process in processes:
                            process.join(15)
                            self.assertEqual(process.exitcode, 0)
                        if action == "prepare":
                            self.assertEqual(len(set(results)), 1)
                            self.assertEqual(repository.get_document_job(job.id).prepared_result.file.id, results[0])
                        else:
                            self.assertCountEqual(results, [1, None])
                            self.assertEqual(repository.get_document_job(job.id).retry_count, 1)
                    finally:
                        for process in processes:
                            if process.is_alive():
                                process.terminate()
                            process.join(5)
                        ready.close()
                        output.close()

    def test_process_exit_releases_file_lock_and_rolls_back_sqlite(self):
        context = multiprocessing.get_context("spawn")
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                repository = _adapters(kind, directory).document_job_repository
                repository.create_document_job(_job())
                locked, exit_now = context.Event(), context.Event()
                process = context.Process(target=_process_exit_with_lock, args=(kind, directory, locked, exit_now))
                process.start()
                try:
                    self.assertTrue(locked.wait(15))
                    exit_now.set()
                    process.join(15)
                    self.assertEqual(process.exitcode, 0)
                    current = repository.get_document_job("job")
                    self.assertEqual(current.progress, 0)
                    selected = repository.prepare_document_job_result("job", expected_retry_count=0,
                        expected_document_ir_file_id="ir", candidate=_candidate())
                    self.assertIsNotNone(selected.prepared_result)
                    if kind == "file":
                        self.assertTrue((Path(directory) / "document_jobs/job/job.lock").exists())
                finally:
                    if process.is_alive():
                        process.terminate()
                    process.join(5)

    def test_legacy_discovery_refuses_ambiguous_or_checksum_corrupt_objects(self):
        for failure in ("multiple", "checksum", "evidence"):
            with self.subTest(failure=failure), self._runtime() as (root, runtime, execution, job, client, headers):
                # 先走真实渲染获取合法字节和证据，再模拟只有 legacy uploaded 文件而无 receipt 的旧记录。
                result = execution.execute_job(job.id)
                original = runtime.document_file_repository.get_document_file(result.result_file_id)
                runtime.document_file_repository.update_document_file(original.id, metadata={
                    key: value for key, value in original.metadata.items() if key != "document_job_result_protocol"})
                runtime.document_job_repository.update_document_job(job.id, status="running", stage="uploading",
                    prepared_result=None, result_file_id=None)
                if failure == "multiple":
                    content = runtime.file_upload_service.read_file_content(original)
                    runtime.file_upload_service.register_generated_content(
                        tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                        file_type="generated_word", filename="second.docx", mime_type=original.mime_type,
                        content=content, metadata={key: value for key, value in original.metadata.items() if key != "document_job_result_protocol"})
                elif failure == "checksum":
                    path = runtime.file_upload_service.resolve_local_object_path(original.object_key)
                    path.write_bytes(b"corrupt")
                else:
                    runtime.document_file_repository.update_document_file(original.id, metadata={
                        "retry_count": 0, "document_ir_file_id": job.document_ir_file_id})
                with patch.object(execution.word_renderer, "render_to_result") as render:
                    failed = execution.execute_job(job.id)
                self.assertEqual((failed.status, failed.failed_stage, failed.error_code), ("failed", "uploading", "oss_failed"))
                self.assertIsNone(failed.prepared_result)
                render.assert_not_called()

    def test_pending_protocol_retention_api_reports_real_changes_and_audits_count(self):
        with self._runtime() as (root, runtime, execution, job, client, headers):
            now = utc_now()
            descriptor = _candidate().model_copy(update={"expires_at": now - timedelta(seconds=1)})
            pending = descriptor.model_copy(update={"status": "pending_upload", "etag": None})
            runtime.document_file_repository.create_document_file(pending)
            runtime.document_file_repository.create_document_file(pending.model_copy(update={
                "id": "ordinary-source", "file_type": "source_pdf", "metadata": {}}))
            admin_headers = fixtures.build_auth_header(client, username="admin", password="admin-pass")
            response = client.post("/api/v1/files/retention/mark-expired", headers=admin_headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["marked_file_ids"], [descriptor.id])
            statuses = {item["file_id"]: item["status"] for item in response.json()["candidates"]}
            self.assertEqual(statuses[descriptor.id], "expired")
            self.assertEqual(statuses["ordinary-source"], "pending_upload")
            events = [event for event in runtime.audit_event_repository.list_audit_events()
                      if event.action == "file.retention_mark_expired"]
            self.assertEqual(len(events), 1)
            self.assertIn("marked=1", events[0].reason)
            repeated = client.post("/api/v1/files/retention/mark-expired", headers=admin_headers)
            self.assertEqual(repeated.json()["marked_file_ids"], [])

    def test_cancel_or_timeout_after_receipt_prevents_completion_and_download(self):
        for kind in ("file", "sqlite"):
            for action in ("cancel", "timeout"):
                with self.subTest(kind=kind, action=action), self._runtime(kind) as (
                    root, runtime, execution, job, client, headers,
                ):
                    materialize = runtime.document_file_repository.materialize_prepared_result
                    def change_state(descriptor):
                        if action == "cancel":
                            response = client.post(f"/api/v1/document-jobs/{job.id}/cancel", headers=headers)
                            self.assertEqual(response.status_code, 200)
                        else:
                            runtime.document_job_repository.update_document_job(job.id, timeout_at=utc_now() - timedelta(seconds=1))
                        return materialize(descriptor)
                    with patch.object(runtime.document_file_repository, "materialize_prepared_result", side_effect=change_state):
                        result = execution.execute_job(job.id)
                    self.assertEqual(result.status, "canceled" if action == "cancel" else "failed")
                    self.assertIsNotNone(result.prepared_result)
                    self.assertIsNone(result.result_file_id)
                    if action == "timeout":
                        self.assertEqual(result.error_code, "document_job_timeout")
                    file_id = result.prepared_result.file.id
                    response = client.get(f"/api/v1/document-jobs/{job.id}/download-url", params={"file_id": file_id}, headers=headers)
                    self.assertEqual(response.status_code, 409)
                    before = self._files(runtime, job.id, "generated_word")
                    execution.execute_job(job.id)
                    self.assertEqual(self._files(runtime, job.id, "generated_word"), before)

    def test_two_receipt_recoverers_materialize_same_identity_once(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self._runtime(kind) as (root, runtime, execution, job, client, headers):
                with patch.object(runtime.document_file_repository, "materialize_prepared_result", side_effect=SimulatedProcessExit):
                    with self.assertRaises(SimulatedProcessExit):
                        execution.execute_job(job.id)
                restarted = self._build_runtime(root, kind)
                entered, release = Event(), Event()
                materialize = runtime.document_file_repository.materialize_prepared_result
                def paused(descriptor):
                    entered.set()
                    if not release.wait(15):
                        raise RuntimeError("物化屏障超时。")
                    return materialize(descriptor)
                with patch.object(runtime.document_file_repository, "materialize_prepared_result", side_effect=paused), ThreadPoolExecutor(max_workers=1) as pool:
                    first = pool.submit(execution.execute_job, job.id)
                    try:
                        self.assertTrue(entered.wait(15))
                        result = restarted.document_job_execution_service.execute_job(job.id)
                        release.set()
                        late = first.result(timeout=15)
                    finally:
                        release.set()
                self.assertEqual(result.result_file_id, late.result_file_id)
                self._assert_result_bytes(restarted, result)
                completed_events = [event for event in runtime.document_job_event_repository.list_document_job_events(job.id)
                                    if event.event_type == "stage_succeeded" and event.stage == "completed"]
                self.assertEqual(len(completed_events), 1)

    def test_committed_receipt_response_loss_finishes_same_candidate(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self._runtime(kind) as (root, runtime, execution, job, client, headers):
                prepare = runtime.document_job_repository.prepare_document_job_result
                def response_lost(*args, **kwargs):
                    prepare(*args, **kwargs)
                    raise OSError("receipt 已提交但响应丢失")
                with patch.object(runtime.document_job_repository, "prepare_document_job_result", side_effect=response_lost):
                    result = execution.execute_job(job.id)
                self._assert_result_bytes(runtime, result)
                self.assertEqual(len(self._files(runtime, job.id, "generated_word")), 1)
                self.assertFalse(any(event.event_type == "stage_failed" for event in
                    runtime.document_job_event_repository.list_document_job_events(job.id)))

    def test_file_lifecycle_serialization_prevents_inflight_materialization_from_reviving_expiry(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                files = _adapters(kind, directory).document_file_repository
                other = _adapters(kind, directory).document_file_repository
                descriptor = _candidate()
                files.create_document_file(descriptor.model_copy(update={"status": "pending_upload", "etag": None}))
                entered, release = Event(), Event()
                from app.domains.files.result_registration import materialized_file
                def paused(existing, incoming):
                    updated = materialized_file(existing, incoming)
                    entered.set()
                    if not release.wait(15):
                        raise RuntimeError("文件物化屏障超时。")
                    return updated
                module = f"app.infrastructure.persistence.{kind}.files.materialized_file"
                with patch(module, side_effect=paused), ThreadPoolExecutor(max_workers=2) as pool:
                    materializing = pool.submit(files.materialize_prepared_result, descriptor)
                    try:
                        self.assertTrue(entered.wait(15))
                        expiring = pool.submit(other.expire_document_file, descriptor.id,
                            now=descriptor.expires_at + timedelta(seconds=1))
                        release.set()
                        materializing.result(timeout=15)
                        self.assertEqual(expiring.result(timeout=15).status, "expired")
                    finally:
                        release.set()
                self.assertEqual(files.get_document_file(descriptor.id).status, "expired")
                with self.assertRaises(ValueError):
                    files.materialize_prepared_result(descriptor)

    def test_stale_render_snapshot_cannot_lower_progress_after_upload_recovery(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self._runtime(kind) as (root, runtime, execution, stale, client, headers):
                self.assertEqual((stale.stage, stale.progress), ("rendering", 60))
                repository = runtime.document_job_repository
                uploading = repository.update_document_job(stale.id, stage="uploading", progress=85)
                # B 已回到 rendering，但内存渲染中断；A 仍拿着先前 60% 的同代快照。
                with patch.object(execution.word_renderer, "render_to_result", side_effect=SimulatedProcessExit):
                    with self.assertRaises(SimulatedProcessExit):
                        execution._render_and_save_word(uploading, trace_id=None)
                self.assertEqual((repository.get_document_job(stale.id).stage, repository.get_document_job(stale.id).progress),
                                 ("rendering", 85))
                observed = []
                update = repository.update_document_job_if_current
                def record_progress(*args, **kwargs):
                    result = update(*args, **kwargs)
                    if result is not None:
                        observed.append((result.stage, result.progress))
                    return result
                with patch.object(repository, "update_document_job_if_current", side_effect=record_progress):
                    result = execution._render_and_save_word(stale, trace_id=None)
                self._assert_result_bytes(runtime, result)
                self.assertEqual(observed[0], ("quality_checking", 85))
                self.assertTrue(all(progress >= 85 for stage, progress in observed))

    def test_trace_json_and_receipt_recovery_events_are_safe_in_file_and_sqlite(self):
        canary = "PRIVATE_RND501_CANARY"
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self._runtime(kind) as (root, runtime, execution, job, client, headers):
                original = build_renderer_evidence
                def evidence(*args, **kwargs):
                    value = original(*args, **kwargs)
                    value["unknown_metadata"] = canary
                    return value
                with patch("app.domains.document_jobs.execution.build_renderer_evidence", side_effect=evidence), patch.object(
                        runtime.document_file_repository, "materialize_prepared_result", side_effect=SimulatedProcessExit):
                    with self.assertRaises(SimulatedProcessExit):
                        execution.execute_job(job.id)
                before = runtime.document_job_repository.get_document_job(job.id)
                self.assertIn(canary, json.dumps(before.prepared_result.file.metadata))
                # 普通投影仍拒绝自由 flags、残留正文及伪造计数；恢复夹具本身保持内容证据合法。
                hostile = {**before.prepared_result.file.metadata, "layout_quality_flags": [canary],
                    "quality_flags": [canary], "docx_quality": {"latex_residue_examples": [canary], "latex_residue_count": canary}}
                self.assertNotIn(canary, json.dumps(build_renderer_event_summary(hostile)))
                restarted = self._build_runtime(root, kind)
                new_execution = restarted.document_job_execution_service
                with patch.object(new_execution.word_renderer, "render_to_result", side_effect=AssertionError("receipt 恢复不能重新渲染")), patch.object(
                        new_execution.word_renderer, "render_to_bytes", side_effect=AssertionError("receipt 恢复不能调用 bytes wrapper")):
                    completed = new_execution.execute_job(job.id)
                file = restarted.document_file_repository.get_document_file(completed.result_file_id)
                self.assertEqual(file.metadata, before.prepared_result.file.metadata)
                self.assertEqual(completed.prepared_result, before.prepared_result)
                self.assertEqual(json.loads(json.dumps(file.metadata)), file.metadata)
                events = restarted.document_job_event_repository.list_document_job_events(job.id)
                selected = [event for event in events if event.stage == "quality_checking" or event.payload.get("file_type") == "generated_word"]
                self.assertTrue(selected)
                for event in selected:
                    serialized = json.dumps(event.payload)
                    self.assertNotIn(canary, serialized)
                    self.assertNotIn("block_render_map", serialized)
                    self.assertNotIn("latex_residue_examples", serialized)
                    self.assertNotIn(file.object_key, serialized)
                registered = next(event for event in selected if event.payload.get("file_type") == "generated_word")
                self.assertEqual(registered.payload["docx_sha256"], file.checksum_sha256.removeprefix("sha256:"))
                self.assertIn("mineru_validation", registered.payload)
                listed = client.get(f"/api/v1/document-jobs/{job.id}/files", headers=headers)
                self.assertEqual(listed.status_code, 200)
                self.assertNotIn(canary, listed.text)
                self.assertNotIn("block_render_map", listed.text)

    def test_invalid_new_trace_does_not_register_a_candidate_or_leak_failure_evidence(self):
        canary = "PRIVATE_FAILURE_RND501_CANARY"
        for failure in ("hash", "owner", "raw_error", "metadata_io"):
            with self.subTest(failure=failure), self._runtime() as (root, runtime, execution, job, client, headers):
                render = execution.word_renderer.render_to_result
                def invalid(*args, **kwargs):
                    result = render(*args, **kwargs)
                    trace = result.block_evidence.model_copy(deep=True)
                    if failure == "hash":
                        trace.docx_sha256 = "0" * 64
                    elif failure == "owner":
                        trace.block_render_map.pop()
                    return replace(result, block_evidence=trace)
                if failure in {"hash", "owner"}:
                    context = patch.object(execution.word_renderer, "render_to_result", side_effect=invalid)
                elif failure == "metadata_io":
                    context = patch.object(runtime.file_upload_service, "register_result_candidate", side_effect=OSError("模拟 metadata 登记失败"))
                else:
                    from app.services.document_ir.integrity import DocumentIntegrityError
                    context = patch("app.domains.document_jobs.execution.ensure_renderer_integrity", side_effect=DocumentIntegrityError(
                        "DocumentIR→DOCX", {"blocking_quality_flags": [canary, "ir_docx_integrity:table_count_mismatch"], "render_plan": {"body": canary}, "latex_residue_examples": [canary]}))
                with context:
                    failed = execution.execute_job(job.id)
                self.assertEqual(failed.status, "failed")
                self.assertEqual(failed.error_code, "oss_failed" if failure == "metadata_io" else "render_failed")
                self.assertEqual(failed.failed_stage, "uploading" if failure == "metadata_io" else "quality_checking")
                self.assertFalse(self._files(runtime, job.id, "generated_word"))
                self.assertIsNone(failed.prepared_result)
                events = runtime.document_job_event_repository.list_document_job_events(job.id)
                self.assertNotIn(canary, json.dumps([event.payload for event in events]))
                self.assertNotIn(canary, failed.error_message)

    def test_full_trace_metadata_round_trips_fake_mysql_descriptor(self):
        from tests.test_renderer_render_plan import make_ir, render
        ir = make_ir()
        result = render(ir)
        metadata = {**_candidate().metadata, **build_renderer_evidence(ir, result.content, render_result=result)}
        database = persistence._FakeMysqlDatabase()
        with tempfile.TemporaryDirectory() as directory:
            adapters = persistence.build_mysql_persistence_adapters(persistence._mysql_config(), connect_factory=database.connect)
            candidate = _candidate().model_copy(update={"metadata": metadata, "size_bytes": len(result.content),
                "checksum_sha256": "sha256:" + hashlib.sha256(result.content).hexdigest()})
            adapters.document_job_repository.create_document_job(_job())
            adapters.document_file_repository.create_document_file(candidate.model_copy(update={"status": "pending_upload", "etag": None}))
            selected = adapters.document_job_repository.prepare_document_job_result("job", expected_retry_count=0,
                expected_document_ir_file_id="ir", candidate=candidate)
            recovered = adapters.document_job_repository.get_document_job("job")
            self.assertEqual(recovered.prepared_result, selected.prepared_result)
            materialized = adapters.document_file_repository.materialize_prepared_result(recovered.prepared_result.file)
            self.assertEqual(materialized.metadata, metadata)
            self.assertEqual(materialized.metadata["block_render_evidence"]["docx_sha256"], hashlib.sha256(result.content).hexdigest())

    def test_legacy_recovery_checks_every_original_aggregate_key_without_new_fields(self):
        with self._runtime() as (root, runtime, execution, job, client, headers):
            completed = execution.execute_job(job.id)
            word = runtime.document_file_repository.get_document_file(completed.result_file_id)
            # 真正旧件没有新图片 marker；不能从新件删报告后要求旧合同放行。
            content = legacy_image_docx(runtime.file_upload_service.read_file_content(word))
            original_ir = DocumentIR.model_validate_json(runtime.file_upload_service.read_file_content(execution._get_document_ir_file(job)))
            aggregate = build_renderer_aggregate_evidence(original_ir, content)
            legacy = {key: aggregate[key] for key in LEGACY_RENDERER_EVIDENCE_KEYS}
            word = runtime.file_upload_service.register_generated_content(
                tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                file_type="generated_word", filename="legacy.docx", mime_type=word.mime_type,
                content=content, metadata=legacy)
            legacy.update(retry_count=job.retry_count, document_ir_file_id=job.document_ir_file_id)
            runtime.document_file_repository.update_document_file(word.id, metadata=legacy)
            old_job = runtime.document_job_repository.update_document_job(job.id, status="running", stage="uploading",
                prepared_result=None, result_file_id=None)
            self.assertEqual(execution._get_existing_result_file(old_job).id, word.id)
            for key in LEGACY_RENDERER_EVIDENCE_KEYS:
                with self.subTest(key=key):
                    damaged = {**legacy, key: {"invalid": True}}
                    runtime.document_file_repository.update_document_file(word.id, metadata=damaged)
                    with self.assertRaisesRegex(ValueError, "质量证据"):
                        execution._get_existing_result_file(old_job)
            runtime.document_file_repository.update_document_file(word.id, metadata=legacy)
            with patch.object(execution.word_renderer, "render_to_result") as render:
                recovered = execution.execute_job(job.id)
            self.assertEqual((recovered.status, recovered.result_file_id), ("succeeded", word.id))
            render.assert_not_called()
            self.assertNotIn("render_plan", recovered.prepared_result.file.metadata)


class DocumentJobBlockAnchorRecoveryTests(TestCase):
    """新通用 marker 和独立证明在三恢复入口保持，不改变原内容门禁。"""

    _build_runtime = DocumentJobResultPersistenceTests._build_runtime
    _upload_source_pdf = DocumentJobResultPersistenceTests._upload_source_pdf
    _create = DocumentJobResultPersistenceTests._create
    _files = DocumentJobResultPersistenceTests._files
    _pause_after_ir = DocumentJobResultPersistenceTests._pause_after_ir
    _runtime = DocumentJobResultPersistenceTests._runtime
    _install_toc_ir = DocumentJobResultPersistenceTests._install_toc_ir

    def test_tampered_toc_representative_three_recovery_entries_keep_primary_and_states(self):
        from app.domains.document_jobs.preview import _mapping_source

        for kind in ("file", "sqlite"):
            for entry in ("legacy", "explicit", "receipt"):
                with self.subTest(kind=kind, entry=entry), self._runtime(kind) as (
                        root, runtime, execution, job, client, headers):
                    job, ir = self._install_toc_ir(runtime, job)
                    rendered = execution.word_renderer.render_to_result(ir, template_path=None, config_path=None,
                        image_loader=execution._build_image_loader(job),
                        options=DocumentIRRenderOptions(template_version_id=job.template_version_id))
                    evidence = build_renderer_evidence(ir, rendered.content, render_result=rendered)
                    evidence["block_render_evidence"]["block_render_map"][1]["representative_block_id"] = "tail"
                    word = runtime.file_upload_service.register_generated_content(tenant_id=job.tenant_id,
                        company_id=job.company_id, job_id=job.id, created_by=job.created_by, file_type="generated_word",
                        filename="tampered-toc-trace.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        content=rendered.content, metadata={"source_file_id": job.source_file_id,
                            "document_ir_file_id": job.document_ir_file_id, "retry_count": job.retry_count,
                            "template_version_id": job.template_version_id, **evidence})
                    job = runtime.document_job_repository.update_document_job(job.id, stage="uploading")
                    if entry == "explicit":
                        job = runtime.document_job_repository.update_document_job(job.id, result_file_id=word.id)
                    elif entry == "receipt":
                        job = runtime.document_job_repository.prepare_document_job_result(job.id,
                            expected_retry_count=job.retry_count, expected_document_ir_file_id=job.document_ir_file_id, candidate=word)
                    with patch.object(execution.word_renderer, "render_to_result", side_effect=AssertionError("恢复不能重新渲染")):
                        result = execution.execute_job(job.id)
                    self.assertEqual((result.status, result.stage, result.quality_status, result.review_status,
                        result.delivery_status), ("succeeded", "completed", "pending", "unreviewed", "internal_draft"), result.error_message)
                    self.assertEqual(result.result_file_id, word.id)
                    self.assertIsNone(result.word_preview_state)
                    if entry == "explicit":
                        self.assertIsNone(result.prepared_result)
                    else:
                        self.assertEqual(result.prepared_result.file, word)
                    saved = runtime.document_file_repository.get_document_file(word.id)
                    self.assertEqual(saved.metadata, word.metadata)
                    self.assertEqual(runtime.file_upload_service.read_file_content(saved), rendered.content)
                    self.assertEqual(_mapping_source(saved, rendered.content,
                        runtime.document_file_repository, runtime.file_upload_service), (None, None, None))
                    self.assertEqual(saved.metadata["block_anchor_evidence"], evidence["block_anchor_evidence"])
                    signed = client.get(f"/api/v1/document-jobs/{job.id}/download-url", headers=headers)
                    self.assertEqual(signed.status_code, 200, signed.text)
                    self.assertEqual(client.get(signed.json()["download_url"]).content, rendered.content)

    def test_deep_optional_proof_stays_local_in_recovery_and_preview_source(self):
        import sys
        from app.domains.document_jobs.preview import _mapping_source

        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self._runtime(kind) as (root, runtime, execution, job, client, headers):
                ir = DocumentIR.model_validate_json(runtime.file_upload_service.read_file_content(execution._get_document_ir_file(job)))
                rendered = execution.word_renderer.render_to_result(ir, template_path=None, config_path=None,
                    image_loader=execution._build_image_loader(job), options=DocumentIRRenderOptions(template_version_id=job.template_version_id))
                evidence = build_renderer_evidence(ir, rendered.content, render_result=rendered)
                source = runtime.file_upload_service.register_generated_content(tenant_id=job.tenant_id,
                    company_id=job.company_id, job_id=job.id, created_by=job.created_by, file_type="generated_word",
                    filename="deep-optional-proof.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    content=rendered.content, metadata={"source_file_id": job.source_file_id,
                        "document_ir_file_id": job.document_ir_file_id, "retry_count": job.retry_count,
                        "template_version_id": job.template_version_id, **evidence})
                nested = 0
                for _ in range(sys.getrecursionlimit() + 1):
                    nested = [nested]
                # 深层值只进入可选证明边界，不经过无关的文件 metadata 编码器。
                proof = {"schema_version": "block-anchor-evidence/v1", "entries": [], "extra": nested}
                metadata = {**source.metadata, "block_anchor_evidence": proof}
                source = source.model_copy(update={"metadata": metadata})
                with self.assertLogs("business", "WARNING") as logs:
                    execution._validate_render_result_file(source)
                self.assertIn("reason_code=anchor_missing", " ".join(logs.output))
                plan, trace, anchors = _mapping_source(source, rendered.content,
                    runtime.document_file_repository, runtime.file_upload_service)
                self.assertEqual(plan, rendered.plan)
                self.assertEqual(trace, rendered.block_evidence)
                self.assertIsNone(anchors)
                self.assertIs(metadata["block_anchor_evidence"], proof)

    def test_three_recovery_entries_preserve_optional_proof_and_never_rerender(self):
        import importlib.util
        compat_root = os.environ.get("RND505_COMPAT_ROOT")
        compat = None
        if compat_root:
            path = Path(compat_root) / "app/domains/document_jobs/execution.py"
            spec = importlib.util.spec_from_file_location("rnd505_b1_execution_reader", path)
            compat = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(compat)
        for kind in ("file", "sqlite"):
            for entry in ("legacy", "explicit", "receipt"):
                for variant in ("valid", "missing", "unknown", "bad_hash", "bad_trace"):
                    with self.subTest(kind=kind, entry=entry, variant=variant), self._runtime(kind) as (
                            root, runtime, execution, job, client, headers):
                        ir = DocumentIR.model_validate_json(runtime.file_upload_service.read_file_content(execution._get_document_ir_file(job)))
                        rendered = execution.word_renderer.render_to_result(ir, template_path=None, config_path=None,
                            image_loader=execution._build_image_loader(job), options=DocumentIRRenderOptions(template_version_id=job.template_version_id))
                        evidence = build_renderer_evidence(ir, rendered.content, render_result=rendered)
                        self.assertIn("block_anchor_evidence", evidence)
                        if variant == "missing": evidence.pop("block_anchor_evidence")
                        elif variant == "unknown": evidence["block_anchor_evidence"]["schema_version"] = "future/v9"
                        elif variant == "bad_hash": evidence["block_anchor_evidence"]["evidence_sha256"] = "f" * 64
                        elif variant == "bad_trace": evidence["block_render_evidence"]["docx_sha256"] = "f" * 64
                        word = runtime.file_upload_service.register_generated_content(tenant_id=job.tenant_id,
                            company_id=job.company_id, job_id=job.id, created_by=job.created_by, file_type="generated_word",
                            filename="same-call-anchors.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            content=rendered.content, metadata={"source_file_id": job.source_file_id,
                                "document_ir_file_id": job.document_ir_file_id, "retry_count": job.retry_count,
                                "template_version_id": job.template_version_id, **evidence})
                        job = runtime.document_job_repository.update_document_job(job.id, stage="uploading")
                        if entry == "explicit":
                            job = runtime.document_job_repository.update_document_job(job.id, result_file_id=word.id)
                        elif entry == "receipt":
                            job = runtime.document_job_repository.prepare_document_job_result(job.id,
                                expected_retry_count=job.retry_count, expected_document_ir_file_id=job.document_ir_file_id, candidate=word)
                        if compat is not None:
                            # B1 只有 writer 停用；此类来自实际快照，依赖 reader 源码由快照指纹核对。
                            execution.__class__ = compat.DocumentJobExecutionService
                        with patch.object(execution.word_renderer, "render_to_result", side_effect=AssertionError("恢复不能重新渲染")):
                            result = execution.execute_job(job.id)
                        self.assertEqual((result.status, result.stage), ("succeeded", "completed"), result.error_message)
                        self.assertEqual(result.result_file_id, word.id)
                        if entry == "explicit":
                            self.assertIsNone(result.prepared_result)
                        else:
                            self.assertEqual(result.prepared_result.file.metadata, word.metadata)
                        saved = runtime.document_file_repository.get_document_file(word.id)
                        self.assertEqual(saved.metadata, word.metadata)
                        self.assertEqual(runtime.file_upload_service.read_file_content(saved), rendered.content)
                        self.assertEqual(result.quality_status, "pending")
                        payloads = json.dumps([event.payload for event in runtime.document_job_event_repository.list_document_job_events(job.id)])
                        self.assertNotIn("block_anchor_evidence", payloads)
                        self.assertNotIn("md2w_blk_", payloads)
                        listed = client.get(f"/api/v1/document-jobs/{job.id}/files", headers=headers).text
                        self.assertNotIn("block_anchor_evidence", listed)
                        self.assertNotIn("md2w_blk_", listed)
