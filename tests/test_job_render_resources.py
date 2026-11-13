"""任务资源实物认证、原子物化、Renderer 消费和发布证明的定向回归。"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from zipfile import ZipFile

from docx import Document
import yaml

from app.core.config import Settings
from app.domains.jobs.models import ConversionOptions, JobResourceSnapshot
from app.domains.jobs.paths import build_job_paths
from app.domains.jobs.resource_snapshots import JobResourceSnapshotError, JobResourceSnapshotService
from app.domains.resources.integrity import content_sha256, resource_payload_sha256
from app.domains.resources.models import ResourceVersionRecord, ResourceVersionStatus
from app.domains.resources.service import ResourceVersionService
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID
from app.domains.term_rules.yaml_codec import TermRuleYamlCodec
from tests import test_document_job_execution_stages as stages
from tests import test_fastapi_jobs_backend as fixtures
from tests.test_resource_versioning import _MemoryResourceVersionRepository
from tests.test_template_package_contract import bundled_template_paths


def _register(service, resource_type, resource_id, version, payload, *, status=ResourceVersionStatus.PUBLISHED):
    return service.repository.save_resource_version(ResourceVersionRecord(
        resource_type=resource_type, resource_id=resource_id, version=version, status=status,
        snapshot_hash=resource_payload_sha256(payload), payload=payload,
    ))


def _register_template(service, version, docx, layout, *, status=ResourceVersionStatus.PUBLISHED):
    return _register(service, "template", "default", version, {
        "docx_path": str(docx),
        "docx_sha256": content_sha256(docx.read_bytes()),
        "layout_config_path": str(layout),
        "layout_config_sha256": content_sha256(layout.read_bytes()),
    }, status=status)


def _register_rules(service, version, term):
    store = fixtures.build_test_term_rules_store(term)
    return _register(service, "term_rule_set", DEFAULT_TERM_RULE_SET_ID, version, {
        "store": store.model_dump(mode="json"),
    })


def _copy_bundled_inputs(directory):
    template, layout = bundled_template_paths()
    docx = directory / "template.docx"
    config = directory / "layout.yaml"
    docx.write_bytes(template.read_bytes())
    config.write_bytes(layout.read_bytes())
    return docx, config


class JobRenderResourceMaterializationTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="md2word-resources-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.docx, self.layout = _copy_bundled_inputs(self.root)
        self.repository = _MemoryResourceVersionRepository()
        self.versions = ResourceVersionService(self.repository)
        self.service = JobResourceSnapshotService(Settings(_env_file=None), self.versions)
        self.template = _register_template(self.versions, "2", self.docx, self.layout)
        _register_rules(self.versions, "1", "VONE")
        self.versions.set_default("template", "default", "2")
        self.versions.set_default("term_rule_set", DEFAULT_TERM_RULE_SET_ID, "1")
        self.snapshot = self.service.build_snapshot(options=ConversionOptions(), source_kind="source_pdf", job_id="sample")
        self.paths = build_job_paths(self.root, "sample")

    def assert_error(self, code, *, snapshot=None, paths=None):
        with self.assertRaises(JobResourceSnapshotError) as raised:
            self.service.materialize_render_resources(snapshot or self.snapshot, paths or self.paths)
        self.assertEqual(raised.exception.code, code)
        self.assertNotIn(str(self.root), str(raised.exception))

    def test_cached_copies_survive_shared_files_changed_or_removed(self):
        cached = self.service.materialize_render_resources(self.snapshot, self.paths)
        self.assertTrue(cached.template_path.is_relative_to(self.paths.resources_dir))
        self.assertTrue(cached.layout_config_path.is_relative_to(self.paths.resources_dir))
        self.assertTrue(cached.subscript_config_path.is_relative_to(self.paths.resources_dir))
        self.assertEqual(cached.template_content, self.docx.read_bytes())
        self.assertEqual(cached.layout_config_content, self.layout.read_bytes())
        self.docx.unlink()
        self.layout.write_bytes(b"changed")
        self.assertEqual(self.service.materialize_render_resources(self.snapshot, self.paths), cached)

    def test_first_use_rejects_changed_or_missing_shared_resources(self):
        original = self.docx.read_bytes()
        self.docx.write_bytes(b"tampered")
        self.assert_error("template_docx_hash_mismatch")
        self.docx.write_bytes(original)
        self.layout.write_bytes(b"tampered")
        self.assert_error("template_layout_config_hash_mismatch")
        self.layout.unlink()
        self.assert_error("resource_snapshot_file_unavailable")

    def test_changed_cache_is_rejected_even_with_original_available(self):
        cached = self.service.materialize_render_resources(self.snapshot, self.paths)
        for path, original, code in (
            (cached.template_path, cached.template_content, "template_docx_hash_mismatch"),
            (cached.layout_config_path, cached.layout_config_content, "template_layout_config_hash_mismatch"),
            (cached.subscript_config_path, cached.subscript_content, "term_rule_hash_mismatch"),
        ):
            with self.subTest(code=code):
                path.write_bytes(b"tampered")
                self.assert_error(code)
                self.assertEqual(path.read_bytes(), b"tampered")
                path.write_bytes(original)

    def test_payload_and_record_hash_are_both_authenticated(self):
        altered = {**self.template.payload, "description": "changed"}
        self.repository.save_resource_version(self.template.model_copy(update={"payload": altered}))
        self.assert_error("resource_snapshot_payload_hash_mismatch")
        _register(self.versions, "template", "default", "2", altered)
        self.assert_error("resource_snapshot_hash_mismatch")

    def test_concurrent_workers_materialize_complete_copies(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.service.materialize_render_resources(self.snapshot, self.paths), range(8)))
        first = results[0]
        self.assertTrue(all(result == first for result in results))
        for path, content in (
            (first.template_path, first.template_content),
            (first.layout_config_path, first.layout_config_content),
            (first.subscript_config_path, first.subscript_content),
        ):
            self.assertEqual(path.read_bytes(), content)
        self.assertEqual(list(self.paths.resources_dir.rglob(".resource-*")), [])

    def test_fsync_failure_keeps_temporary_file_out_of_task_cache(self):
        with patch("app.domains.jobs.resource_snapshots.os.fsync", side_effect=OSError(str(self.root))):
            self.assert_error("resource_snapshot_materialization_failed")
        self.assertEqual(list(self.paths.resources_dir.rglob("template.docx")), [])
        self.assertEqual(list(self.paths.resources_dir.rglob(".resource-*")), [])
        self.assertTrue(self.service.materialize_render_resources(self.snapshot, self.paths).template_path.is_file())

    def test_rule_version_or_department_rebind_does_not_replace_previous_inputs(self):
        first = self.service.materialize_render_resources(self.snapshot, self.paths)
        _register_rules(self.versions, "2", "VTWO")
        self.versions.set_default("term_rule_set", DEFAULT_TERM_RULE_SET_ID, "2")
        latest = self.service.build_snapshot(options=ConversionOptions(), source_kind="source_pdf", job_id="sample")
        second = self.service.materialize_render_resources(latest, self.paths)
        department = self.service.materialize_render_resources(
            latest.model_copy(update={"term_rule_department_id": "engineering"}), self.paths,
        )
        self.assertEqual(first.template_path, second.template_path)
        self.assertNotEqual(first.subscript_config_path, second.subscript_config_path)
        self.assertNotEqual(second.subscript_config_path, department.subscript_config_path)
        self.assertIn(b"VONE", first.subscript_config_path.read_bytes())
        self.assertIn(b"VTWO", second.subscript_config_path.read_bytes())
        self.assertEqual(self.service.materialize_render_resources(self.snapshot, self.paths), first)

    def test_only_bound_draft_is_allowed_and_remains_bound_after_publication(self):
        record = _register_template(self.versions, "3", self.docx, self.layout, status=ResourceVersionStatus.DRAFT)
        draft = self.versions.resolve_version("template", "default", "3", allow_draft=True)
        snapshot = self.snapshot.model_copy(update={"template": draft})
        self.assert_error("resource_snapshot_invalid_status", snapshot=snapshot.model_copy(update={
            "template": draft.model_copy(update={"status": "published"}),
        }))
        first = self.service.materialize_render_resources(snapshot, self.paths)
        self.assertFalse(first.publishable)
        published = _register(self.versions, "template", "default", "3", {
            **record.payload, "verification_job_id": "sample", "publish_reason": "approved",
        })
        self.assertEqual(self.service.materialize_render_resources(snapshot, self.paths), first)
        self.assertNotEqual(published.snapshot_hash, draft.snapshot_hash)
        self.versions.disable("template", "default", "3")
        self.assert_error("resource_snapshot_invalid_status", snapshot=snapshot)


class JobRenderResourceExecutionTests(TestCase):
    _runtime = stages.DocumentJobExecutionStageTests._runtime
    _upload_source_pdf = stages.DocumentJobExecutionStageTests._upload_source_pdf
    _pause_after_ir = stages.DocumentJobExecutionStageTests._pause_after_ir
    _create = stages.DocumentJobExecutionStageTests._create
    _files = stages.DocumentJobExecutionStageTests._files

    def _bind_resources(
        self, runtime, execution, job, *, status=ResourceVersionStatus.PUBLISHED, configure_layout=None,
    ):
        docx, layout = _copy_bundled_inputs(runtime.settings.data_path)
        if configure_layout is not None:
            configure_layout(layout)
        template_id, version = job.template_version_id.split("@")
        self.assertEqual(template_id, "default")
        service = ResourceVersionService(_MemoryResourceVersionRepository())
        _register_template(service, version, docx, layout, status=status)
        _register_rules(service, "1", "VONE")
        snapshot = JobResourceSnapshot(
            template=service.resolve_version("template", "default", version, allow_draft=status == ResourceVersionStatus.DRAFT),
            term_rule_set=service.resolve_version("term_rule_set", DEFAULT_TERM_RULE_SET_ID, "1"),
        )
        execution.rendering.job_resource_snapshot_service = JobResourceSnapshotService(runtime.settings, service)
        job = runtime.document_job_repository.update_document_job(
            job.id, request_snapshot={**job.request_snapshot, "resources": snapshot.model_dump(mode="json")},
        )
        return job, docx, layout

    def _fixture_with_term(self):
        source = BytesIO(fixtures.make_english_mineru_zip_bytes())
        result = BytesIO()
        with ZipFile(source) as old, ZipFile(result, "w") as new:
            for name in old.namelist():
                value = old.read(name)
                if name == "content_list_v2.json":
                    blocks = json.loads(value)
                    blocks[1]["text"] += " VONE"
                    value = json.dumps(blocks).encode()
                new.writestr(name, value)
        return result.getvalue()

    def test_snapshot_inputs_are_consumed_in_both_modes_and_frozen_in_provenance(self):
        for mode in ("direct", "en2zh"):
            with self.subTest(mode=mode), self._runtime() as (runtime, execution, _provider, client, headers):
                execution.fake_mineru_client.result_zip_bytes = self._fixture_with_term()
                job = self._pause_after_ir(runtime, execution, client, headers, mode=mode)
                job, docx, layout = self._bind_resources(runtime, execution, job)
                expected_docx, expected_layout = docx.read_bytes(), layout.read_bytes()
                global_rules = runtime.settings.data_path / "global.yaml"
                global_rules.write_text(TermRuleYamlCodec().dump_legacy_runtime_yaml(fixtures.build_test_term_rules_store("VTWO")), encoding="utf-8")
                runtime.settings.term_rules_runtime_yaml_path = str(global_rules)
                renderer = execution.rendering.word_renderer
                original = renderer.render_to_result

                def render(document, **kwargs):
                    for path in (kwargs["template_path"], kwargs["config_path"], kwargs["options"].subscript_config_path):
                        self.assertTrue(path.is_relative_to(build_job_paths(runtime.settings.data_path, job.id).resources_dir))
                    # 物化后改写共享源，发布证明仍须使用本次认证实物。
                    docx.write_bytes(b"changed")
                    layout.write_bytes(b"changed")
                    return original(document, **kwargs)

                with patch.object(execution.rendering.template_read_service, "resolve_template_version", side_effect=AssertionError), patch.object(
                    renderer, "render_to_result", side_effect=render,
                ):
                    finished = execution.execute_job(job.id)
                self.assertEqual(finished.status, "succeeded", finished.error_message)
                word = runtime.document_file_repository.get_document_file(finished.result_file_id)
                rendered = Document(BytesIO(runtime.file_upload_service.read_file_content(word)))
                self.assertTrue(any(
                    run.text == "ONE" and run.font.subscript
                    for paragraph in rendered.paragraphs for run in paragraph.runs
                ))
                evidence_file = runtime.document_file_repository.get_document_file(word.metadata["publication_provenance_file_id"])
                evidence = json.loads(runtime.file_upload_service.read_file_content(evidence_file))
                self.assertEqual(evidence["status"], "complete")
                self.assertEqual(base64.b64decode(evidence["resources"]["template_docx"]), expected_docx)
                self.assertEqual(base64.b64decode(evidence["resources"]["template_config"]), expected_layout)
                self.assertIn(b"VONE", base64.b64decode(evidence["resources"]["symbol_rules"]))

    def test_failed_hash_records_stable_code_before_renderer_without_path_leak(self):
        with self._runtime() as (runtime, execution, _provider, client, headers):
            job = self._pause_after_ir(runtime, execution, client, headers)
            job, docx, _layout = self._bind_resources(runtime, execution, job)
            docx.write_bytes(b"changed")
            with patch.object(execution.rendering.word_renderer, "render_to_result") as renderer:
                failed = execution.execute_job(job.id)
            renderer.assert_not_called()
            self.assertEqual((failed.status, failed.failed_stage, failed.error_code), ("failed", "rendering", "render_failed"))
            self.assertNotIn(str(docx), failed.error_message)
            event = runtime.document_job_event_repository.list_document_job_events(job.id)[-1]
            self.assertEqual(event.payload["blocking_quality_flags"], ["template_docx_hash_mismatch"])
            self.assertNotIn(str(docx), json.dumps(event.payload))

    def test_bound_template_renders_without_catalog_or_manifest(self):
        with self._runtime() as (runtime, execution, _provider, client, headers):
            job = self._pause_after_ir(runtime, execution, client, headers)
            job, _docx, _layout = self._bind_resources(runtime, execution, job)
            with patch.object(execution.rendering, "template_read_service", None):
                finished = execution.execute_job(job.id)
            self.assertEqual(finished.status, "succeeded", finished.error_message)
            self.assertTrue(self._files(runtime, job.id, "generated_word"))

    def test_bound_template_rejects_disabled_database_version_before_rendering(self):
        with self._runtime() as (runtime, execution, _provider, client, headers):
            job = self._pause_after_ir(runtime, execution, client, headers)
            job, _docx, _layout = self._bind_resources(runtime, execution, job)
            service = execution.rendering.job_resource_snapshot_service.resource_version_service
            template_id, version = job.template_version_id.split("@")
            service.disable("template", template_id, version)
            with patch.object(
                execution.rendering.word_renderer, "render_to_result",
            ) as renderer:
                failed = execution.execute_job(job.id)
            renderer.assert_not_called()
            self.assertEqual((failed.status, failed.failed_stage), ("failed", "rendering"))
            event = runtime.document_job_event_repository.list_document_job_events(job.id)[-1]
            self.assertEqual(event.payload["blocking_quality_flags"], ["resource_snapshot_invalid_status"])

    def test_bound_draft_renders_existing_relative_logo_override(self):
        with self._runtime() as (runtime, execution, _provider, client, headers):
            job = self._pause_after_ir(runtime, execution, client, headers)

            def configure_layout(layout):
                logo = layout.parent / "assets" / "test-logo.png"
                logo.parent.mkdir()
                logo.write_bytes(fixtures.MINIMAL_PNG_BYTES)
                config = yaml.safe_load(layout.read_bytes())
                config["header"].update(enabled=True, logo_path="assets/test-logo.png", title_text="验证页眉")
                layout.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

            job, _docx, _layout = self._bind_resources(
                runtime, execution, job, status=ResourceVersionStatus.DRAFT, configure_layout=configure_layout,
            )
            finished = execution.execute_job(job.id)
            self.assertEqual(finished.status, "succeeded", finished.error_message)
            word = runtime.document_file_repository.get_document_file(finished.result_file_id)
            rendered = Document(BytesIO(runtime.file_upload_service.read_file_content(word)))
            header = rendered.sections[0].header
            self.assertIn("验证页眉", header.paragraphs[0].text)
            pictures = [part.blob for part in header.part.related_parts.values() if part.content_type == "image/png"]
            self.assertIn(fixtures.MINIMAL_PNG_BYTES, pictures)
            provenance_file = runtime.document_file_repository.get_document_file(word.metadata["publication_provenance_file_id"])
            evidence = json.loads(runtime.file_upload_service.read_file_content(provenance_file))
            self.assertEqual(evidence["status"], "unavailable")
            self.assertNotIn("resources", evidence)

    def test_historical_without_snapshot_uses_existing_template_and_global_rules(self):
        with self._runtime() as (runtime, execution, _provider, client, headers):
            execution.fake_mineru_client.result_zip_bytes = self._fixture_with_term()
            job = self._pause_after_ir(runtime, execution, client, headers)
            global_rules = runtime.settings.data_path / "global.yaml"
            global_rules.write_text(TermRuleYamlCodec().dump_legacy_runtime_yaml(fixtures.build_test_term_rules_store("VONE")), encoding="utf-8")
            runtime.settings.term_rules_runtime_yaml_path = str(global_rules)
            with patch.object(execution.rendering.template_read_service, "resolve_template_version", wraps=execution.rendering.template_read_service.resolve_template_version) as resolve:
                finished = execution.execute_job(job.id)
            resolve.assert_called_once_with(job.template_version_id)
            self.assertEqual(finished.status, "succeeded", finished.error_message)
            word = runtime.document_file_repository.get_document_file(finished.result_file_id)
            rendered = Document(BytesIO(runtime.file_upload_service.read_file_content(word)))
            self.assertTrue(any(
                run.text == "ONE" and run.font.subscript for paragraph in rendered.paragraphs for run in paragraph.runs
            ))
