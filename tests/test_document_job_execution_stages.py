"""验证任务执行阶段、重投恢复和当前 generation 的产物边界。"""

from contextlib import contextmanager
from datetime import timedelta
import io
import json
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch
import zipfile

from pydantic import ValidationError

from app.domains.document_jobs.models import DocumentJobEventRecord, DocumentJobRecord
from app.domains.resources.models import utc_now
from app.domains.jobs.models import JobResourceSnapshot
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.renderer.evidence import build_renderer_evidence, ensure_renderer_integrity
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from tests import test_database_job_repository as persistence
from tests import test_fastapi_jobs_backend as fixtures


NEW_STAGES = ("translating", "translation_validating", "quality_checking")


class DocumentJobExecutionStageTests(TestCase):
    _upload_source_pdf = fixtures.FastAPIJobsBackendTests._upload_source_pdf

    @contextmanager
    def _runtime(self, *, provider=None, batch_items=3):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir), jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret", auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            execution = runtime.document_job_execution_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            provider = provider or fixtures.FakeDocumentJobTranslationProvider()
            execution.document_ir_translation_service = DocumentIRTranslationService(
                provider, max_items_per_request=batch_items, max_chars_per_request=10_000,
            )
            with fixtures.TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                yield runtime, execution, provider, client, headers

    def _create(self, client, headers, *, mode="direct", language="auto"):
        source = self._upload_source_pdf(client, headers)
        response = client.post(
            "/api/v1/document-jobs", headers={**headers, "X-Trace-Id": "trace_stages"},
            json={"source_file_id": source["id"], "translation_mode": mode, "document_language": language},
        )
        self.assertEqual(response.status_code, 201, response.json())
        return response.json()["job_id"]

    def _files(self, runtime, job_id, file_type=None):
        return [
            file for file in runtime.document_file_repository.list_document_files()
            if file.job_id == job_id and (file_type is None or file.file_type == file_type)
        ]

    def _pause_after_ir(self, runtime, execution, client, headers, *, mode="direct"):
        with patch.object(execution, "_render_and_save_word", side_effect=lambda job, **kwargs: job):
            job_id = self._create(client, headers, mode=mode)
        job = runtime.document_job_repository.get_document_job(job_id)
        self.assertEqual(job.stage, "rendering")
        self.assertIsNotNone(job.document_ir_file_id)
        self.assertFalse(self._files(runtime, job.id, "generated_word"))
        return job

    def _completed_batches(self, runtime, execution, client, headers):
        """模拟批次已落成功结果、最后一次 fan-in 回调丢失的进程中断。"""

        execution.translation_batch_task_queue = Mock()
        job_id = self._create(client, headers, mode="en2zh", language="en")
        job = runtime.document_job_repository.get_document_job(job_id)
        self.assertEqual(job.stage, "translating")
        batches = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)
        with patch.object(execution, "_finalize_translation_generation", return_value=job):
            for batch in batches:
                execution.execute_translation_batch(batch.id, trace_id="trace_batches")
        batches = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)
        self.assertTrue(all(batch.status == "succeeded" for batch in batches))
        return job, batches

    def _register_word(self, runtime, job, *, metadata, job_id=None, file_type="generated_word"):
        execution = runtime.document_job_execution_service
        ir = DocumentIR.model_validate_json(runtime.file_upload_service.read_file_content(execution._get_document_ir_file(job)))
        template = execution.template_read_service.resolve_template_version(job.template_version_id)
        content = execution.word_renderer.render_to_bytes(
            ir, template_path=template.template_path, config_path=template.layout_config_path,
            image_loader=execution._build_image_loader(job),
        )
        metadata = {**build_renderer_evidence(ir, content), **metadata}
        return runtime.file_upload_service.register_generated_content(
            tenant_id=job.tenant_id, company_id=job.company_id, job_id=job_id or job.id,
            created_by=job.created_by, file_type=file_type, filename="recovery.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content=content, metadata=metadata,
        )

    def test_new_and_legacy_stages_round_trip_all_metadata_backends(self):
        builders = (
            ("file", lambda path: persistence.build_file_persistence_adapters(path)),
            ("sqlite", lambda path: persistence.build_sqlite_persistence_adapters(path / "metadata.sqlite3")),
            ("mysql", lambda path: persistence.build_mysql_persistence_adapters(
                persistence._mysql_config(), connect_factory=persistence._FakeMysqlDatabase().connect,
            )),
        )
        for backend, builder in builders:
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as temp_dir:
                adapters = builder(Path(temp_dir))
                for stage in (*NEW_STAGES, "ir_converting", "rendering"):
                    job = DocumentJobRecord(
                        id=f"job_{stage}", tenant_id="tenant", company_id="company", created_by="operator",
                        source_file_id="source", template_version_id="default", status="running", stage=stage,
                    )
                    repository = adapters.document_job_repository
                    repository.create_document_job(job)
                    self.assertEqual(repository.get_document_job(job.id).stage, stage)
                    self.assertIsNone(repository.update_document_job_if_current(
                        job.id, allowed_statuses={"running"}, allowed_stages={stage}, expected_retry_count=1,
                        stage="rendering",
                    ))
                    failed = repository.update_document_job_if_current(
                        job.id, allowed_statuses={"running"}, allowed_stages={stage}, expected_retry_count=0,
                        status="failed", stage="failed", failed_stage=stage,
                    )
                    self.assertEqual(failed.failed_stage, stage)
                    self.assertEqual(repository.get_document_job(job.id).failed_stage, stage)
                    event = DocumentJobEventRecord(
                        id=f"event_{stage}", tenant_id=job.tenant_id, company_id=job.company_id,
                        job_id=job.id, created_by=job.created_by, stage=stage, event_type="stage_failed",
                        message="阶段失败测试", duration_ms=17, trace_id="trace_persistence",
                    )
                    adapters.document_job_event_repository.append_document_job_event(job.id, event)
                    self.assertEqual(adapters.document_job_event_repository.list_document_job_events(job.id), [event])
                    for status in ("pending", "queued", "succeeded", "failed", "canceled"):
                        with self.assertRaises(ValidationError):
                            DocumentJobRecord.model_validate({**job.model_dump(), "status": status})

    def test_four_directions_share_real_stage_boundaries_before_eager_delivery(self):
        for mode, language in (("en2zh", "en"), ("ru2zh", "ru"), ("zh2en", "zh"), ("zh2ru", "zh")):
            with self.subTest(mode=mode), self._runtime() as (runtime, execution, provider, client, headers):
                original = provider.translate
                observed_stages = []

                def translate(request):
                    job = runtime.document_job_repository.list_document_jobs()[0]
                    observed_stages.append(job.stage)
                    return original(request)

                with patch.object(provider, "translate", side_effect=translate):
                    job_id = self._create(client, headers, mode=mode, language=language)
                job = runtime.document_job_repository.get_document_job(job_id)
                self.assertEqual(job.status, "succeeded")
                self.assertEqual(observed_stages, ["translating"] * 3)
                events = runtime.document_job_event_repository.list_document_job_events(job_id)
                starts = [event.stage for event in events if event.event_type == "stage_started"]
                self.assertEqual(starts[-5:], [
                    "translating", "translation_validating", "rendering", "quality_checking", "uploading",
                ])
                for stage in ("translation_validating", "quality_checking"):
                    succeeded = [event for event in events if event.stage == stage and event.event_type == "stage_succeeded"]
                    self.assertEqual(len(succeeded), 1)
                    self.assertGreaterEqual(succeeded[0].duration_ms, 0)
                    self.assertEqual(succeeded[0].trace_id, "trace_stages")
                    self.assertEqual(succeeded[0].payload["generation"], 0)
                self.assertTrue(all(event.stage == "translating" for event in events if (
                    event.event_type.startswith("translation_batch_") or event.event_type == "ai_call_logged"
                )))
                self.assertEqual(len(self._files(runtime, job_id, "generated_word")), 1)

    def test_direct_quality_checks_precede_main_word_registration(self):
        with self._runtime() as (runtime, execution, provider, client, headers):
            observed = []

            def ensure(evidence):
                job = runtime.document_job_repository.list_document_jobs()[0]
                observed.append(job.stage)
                if job.stage == "quality_checking":
                    self.assertFalse(self._files(runtime, job.id, "generated_word"))
                else:
                    self.assertEqual(job.stage, "uploading")
                    self.assertIsNotNone(job.prepared_result)
                ensure_renderer_integrity(evidence)

            with patch("app.domains.document_jobs.execution.ensure_renderer_integrity", side_effect=ensure):
                job_id = self._create(client, headers)
            events = runtime.document_job_event_repository.list_document_job_events(job_id)
            self.assertEqual(observed, ["quality_checking", "uploading"])
            self.assertEqual(runtime.document_job_repository.get_document_job(job_id).status, "succeeded")
            self.assertFalse({"translating", "translation_validating"} & {event.stage for event in events})
            self.assertFalse(provider.requests)
            self.assertEqual(len(self._files(runtime, job_id, "generated_word")), 1)

    def test_zero_translation_units_complete_without_provider_calls(self):
        with self._runtime() as (runtime, execution, provider, client, headers):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("content_list_v2.json", "[]")
            execution.fake_mineru_client.result_zip_bytes = buffer.getvalue()
            job_id = self._create(client, headers, mode="en2zh", language="en")
            job = runtime.document_job_repository.get_document_job(job_id)
            self.assertEqual(job.status, "succeeded", job.error_message)
            self.assertEqual(provider.requests, [])
            self.assertEqual(runtime.document_job_translation_batch_repository.list_translation_batches(job_id), [])
            stages = [event.stage for event in runtime.document_job_event_repository.list_document_job_events(job_id)]
            self.assertIn("translation_validating", stages)

    def test_completed_batches_resume_from_new_and_legacy_inflight_stages(self):
        for stage in ("ir_converting", "translating", "translation_validating"):
            with self.subTest(stage=stage), self._runtime() as (runtime, execution, provider, client, headers):
                job, batches = self._completed_batches(runtime, execution, client, headers)
                runtime.document_job_repository.update_document_job(job.id, stage=stage)
                provider_count = len(provider.requests)
                result = execution.execute_job(job.id, trace_id="trace_resume")
                self.assertEqual(result.status, "succeeded", result.error_message)
                self.assertEqual(len(provider.requests), provider_count)
                self.assertEqual(len(execution.fake_mineru_client.calls), 1)
                files_before = self._files(runtime, job.id)
                events_before = runtime.document_job_event_repository.list_document_job_events(job.id)
                execution.execute_job(job.id)
                execution.execute_translation_batch(batches[0].id)
                self.assertEqual(self._files(runtime, job.id), files_before)
                self.assertEqual(runtime.document_job_event_repository.list_document_job_events(job.id), events_before)

    def test_single_batch_completion_does_not_advance_the_main_translation_stage(self):
        with self._runtime() as (runtime, execution, provider, client, headers):
            execution.translation_batch_task_queue = Mock()
            job_id = self._create(client, headers, mode="en2zh", language="en")
            batches = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)
            self.assertGreater(len(batches), 1)
            execution.execute_translation_batch(batches[0].id)
            job = runtime.document_job_repository.get_document_job(job_id)
            self.assertEqual((job.status, job.stage, job.document_ir_file_id), ("running", "translating", None))
            self.assertFalse(self._files(runtime, job_id, "generated_word"))

    def test_final_provider_failure_keeps_batch_duration_and_translating_failure_stage(self):
        with self._runtime(provider=fixtures.FakeDocumentJobTranslationProvider(raise_error=True), batch_items=100) as (
            runtime, execution, provider, client, headers,
        ):
            job_id = self._create(client, headers, mode="en2zh")
            job = runtime.document_job_repository.get_document_job(job_id)
            self.assertEqual((job.status, job.failed_stage, job.error_code), ("failed", "translating", "translation_failed"))
            events = runtime.document_job_event_repository.list_document_job_events(job_id)
            failed_batches = [event for event in events if event.event_type == "translation_batch_failed"]
            self.assertEqual(len(failed_batches), 2)
            self.assertTrue(all(event.stage == "translating" and event.duration_ms >= 0 for event in failed_batches))
            self.assertEqual((events[-1].event_type, events[-1].stage), ("stage_failed", "translating"))
            self.assertFalse(self._files(runtime, job_id, "generated_word"))

    def test_provider_return_after_cancel_or_generation_change_cannot_finalize(self):
        for action, fails in (("cancel", False), ("retry", False), ("cancel", True), ("retry", True)):
            with self.subTest(action=action, fails=fails), self._runtime(batch_items=100) as (runtime, execution, provider, client, headers):
                execution.translation_batch_task_queue = Mock()
                job_id = self._create(client, headers, mode="en2zh", language="en")
                batch = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)[0]
                original = provider.translate

                def translate(request):
                    if action == "cancel":
                        response = client.post(f"/api/v1/document-jobs/{job_id}/cancel", headers=headers)
                        self.assertEqual(response.status_code, 200, response.json())
                    else:
                        runtime.document_job_repository.update_document_job(job_id, retry_count=1)
                    if fails:
                        raise RuntimeError("旧代 Provider 返回失败")
                    return original(request)

                with patch.object(provider, "translate", side_effect=translate):
                    execution.execute_translation_batch(batch.id)
                job = runtime.document_job_repository.get_document_job(job_id)
                self.assertEqual(job.status, "canceled" if action == "cancel" else "running")
                self.assertIsNone(job.document_ir_file_id)
                self.assertFalse(self._files(runtime, job_id, "translation_batch_result"))
                self.assertFalse(self._files(runtime, job_id, "generated_word"))

    def test_api_filters_saved_views_and_incident_projection_accept_new_stages(self):
        with self._runtime() as (runtime, execution, provider, client, headers):
            for stage in NEW_STAGES:
                with self.subTest(stage=stage):
                    with patch.object(execution, "execute_job"):
                        job_id = self._create(client, headers, mode="en2zh")
                    runtime.document_job_repository.update_document_job(
                        job_id, status="running", stage=stage,
                    )
                    execution.mark_job_timed_out(job_id, trace_id="trace_query")
                    runtime.document_job_repository.update_document_job(
                        job_id, error_code="stage_failure", error_message="阶段执行失败",
                    )
                    detail = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers)
                    self.assertEqual(detail.json()["failed_stage"], stage)
                    events = client.get(f"/api/v1/document-jobs/{job_id}/events", headers=headers, params={"stage": stage})
                    self.assertEqual(events.status_code, 200, events.json())
                    self.assertIn(stage, [event["stage"] for event in events.json()["items"]])
                    incidents = client.get("/api/v1/document-job-incidents", headers=headers, params={"stage": stage})
                    self.assertEqual(incidents.status_code, 200, incidents.json())
                    item = next(item for item in incidents.json()["items"] if item["job"]["id"] == job_id)
                    self.assertEqual(item["failure_type"], "conversion_failed" if stage == "quality_checking" else "translation_failed")
                    saved = client.post("/api/v1/saved-views", headers=headers, json={
                        "page_key": "incidents", "name": f"阶段 {stage}", "filters": {"stage": stage}, "sort": "priority",
                    })
                    self.assertEqual(saved.status_code, 201, saved.json())
                    self.assertEqual(saved.json()["filters"]["stage"], stage)
            invalid = client.get("/api/v1/document-job-incidents", headers=headers, params={"stage": "future_stage"})
            self.assertEqual(invalid.status_code, 400)
            invalid_view = client.post("/api/v1/saved-views", headers=headers, json={
                "page_key": "incidents", "name": "非法阶段", "filters": {"stage": "future_stage"}, "sort": "priority",
            })
            self.assertEqual(invalid_view.status_code, 400)

    def test_fan_in_failures_are_persisted_at_validation_boundary(self):
        for failure, code in (
            ("missing", "translation_fan_in_mismatch"), ("extra", "translation_fan_in_mismatch"),
            ("duplicate", "translation_failed"), ("bad_json", "translation_failed"),
            ("read", "oss_failed"), ("save", "oss_failed"),
        ):
            with self.subTest(failure=failure), self._runtime() as (runtime, execution, provider, client, headers):
                job, batches = self._completed_batches(runtime, execution, client, headers)
                batch = batches[0]
                file = runtime.document_file_repository.get_document_file(batch.result_file_id)
                payload = json.loads(runtime.file_upload_service.read_file_content(file))
                if failure in {"missing", "extra", "duplicate", "bad_json"}:
                    if failure == "missing":
                        payload["items"].pop()
                    elif failure == "extra":
                        payload["items"].append({"id": "extra", "text": "多余结果"})
                    elif failure == "duplicate":
                        payload["items"].append(payload["items"][0])
                    replacement = runtime.file_upload_service.register_generated_content(
                        tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id,
                        created_by=job.created_by, file_type="translation_batch_result", filename="bad-result.json",
                        mime_type="application/json", content=(b"{" if failure == "bad_json" else json.dumps(payload).encode()),
                    )
                    runtime.document_job_translation_batch_repository.update_translation_batch(
                        batch.id, result_file_id=replacement.id,
                    )
                original_read = runtime.file_upload_service.read_file_content
                original_register = runtime.file_upload_service.register_generated_content

                def read(record):
                    if failure == "read" and record.file_type == "translation_batch_result":
                        raise OSError("批次结果存储读取失败")
                    return original_read(record)

                def register(**kwargs):
                    if failure == "save" and kwargs["file_type"] == "document_ir":
                        raise RuntimeError("最终 IR 存储失败")
                    return original_register(**kwargs)

                with patch.object(runtime.file_upload_service, "read_file_content", side_effect=read), patch.object(
                    runtime.file_upload_service, "register_generated_content", side_effect=register,
                ):
                    result = execution.execute_job(job.id, trace_id="trace_fan_in")
                self.assertEqual((result.status, result.failed_stage, result.error_code), (
                    "failed", "translation_validating", code,
                ))
                event = runtime.document_job_event_repository.list_document_job_events(job.id)[-1]
                self.assertEqual((event.event_type, event.stage), ("stage_failed", "translation_validating"))
                self.assertGreaterEqual(event.duration_ms, 0)
                self.assertFalse(self._files(runtime, job.id, "generated_word"))

    def test_quality_replay_and_upload_without_result_rerender_and_recheck(self):
        for mode in ("direct", "en2zh"):
            for stage in ("quality_checking", "uploading"):
                with self.subTest(mode=mode, stage=stage), self._runtime() as (runtime, execution, provider, client, headers):
                    job = self._pause_after_ir(runtime, execution, client, headers, mode=mode)
                    runtime.document_job_repository.update_document_job(job.id, stage=stage, progress=94)
                    provider_count = len(provider.requests)
                    progress = []
                    original_update = runtime.document_job_repository.update_document_job_if_current

                    def update(*args, **kwargs):
                        result = original_update(*args, **kwargs)
                        if result is not None:
                            progress.append(result.progress)
                        return result

                    with patch.object(execution.word_renderer, "render_to_result", wraps=execution.word_renderer.render_to_result) as render, patch(
                        "app.domains.document_jobs.execution.build_renderer_evidence", wraps=build_renderer_evidence,
                    ) as evidence, patch.object(runtime.document_job_repository, "update_document_job_if_current", side_effect=update):
                        result = execution.execute_job(job.id, trace_id="trace_quality_replay")
                    self.assertEqual(result.status, "succeeded", result.error_message)
                    self.assertEqual((render.call_count, evidence.call_count), (1, 2))
                    self.assertEqual(progress, sorted(progress))
                    self.assertGreaterEqual(min(progress), 94)
                    self.assertEqual(len(provider.requests), provider_count)
                    self.assertEqual(len(execution.fake_mineru_client.calls), 1)
                    recovery = [event for event in runtime.document_job_event_repository.list_document_job_events(job.id)
                                if event.payload.get("recovery_from") == stage]
                    self.assertEqual(len(recovery), 1)
                    self.assertEqual(recovery[0].stage, "rendering")

    def test_automatic_word_discovery_requires_current_generation_and_final_ir(self):
        with self._runtime() as (runtime, execution, provider, client, headers):
            job = self._pause_after_ir(runtime, execution, client, headers)
            job = runtime.document_job_repository.update_document_job(job.id, stage="uploading", retry_count=1)
            old_files = [self._register_word(runtime, job, metadata=metadata) for metadata in (
                {"retry_count": 0, "document_ir_file_id": job.document_ir_file_id},
                {"document_ir_file_id": job.document_ir_file_id},
                {"retry_count": 1, "document_ir_file_id": "different-ir"},
            )]
            result = execution.execute_job(job.id)
            self.assertEqual(result.status, "succeeded")
            self.assertNotIn(result.result_file_id, {file.id for file in old_files})
            self.assertTrue(all(runtime.document_file_repository.get_document_file(file.id) is not None for file in old_files))
        with self._runtime() as (runtime, execution, provider, client, headers):
            job = self._pause_after_ir(runtime, execution, client, headers)
            word = self._register_word(runtime, job, metadata={
                "retry_count": job.retry_count, "document_ir_file_id": job.document_ir_file_id,
            })
            runtime.document_job_repository.update_document_job(job.id, stage="uploading")
            with patch.object(execution.word_renderer, "render_to_result") as render:
                result = execution.execute_job(job.id)
            self.assertEqual((result.status, result.result_file_id), ("succeeded", word.id))
            render.assert_not_called()

    def test_explicit_result_reuses_old_generation_but_checks_file_identity(self):
        for invalid in (None, "job", "type", "status"):
            with self.subTest(invalid=invalid), self._runtime() as (runtime, execution, provider, client, headers):
                job = self._pause_after_ir(runtime, execution, client, headers)
                word = self._register_word(
                    runtime, job, metadata={"retry_count": 0}, job_id="another_job" if invalid == "job" else None,
                    file_type="document_ir" if invalid == "type" else "generated_word",
                )
                if invalid == "status":
                    runtime.document_file_repository.update_document_file(word.id, status="expired")
                runtime.document_job_repository.update_document_job(
                    job.id, stage="uploading", result_file_id=word.id, retry_count=1,
                )
                result = execution.execute_job(job.id)
                self.assertEqual(result.status, "succeeded" if invalid is None else "failed")
                if invalid:
                    self.assertEqual((result.failed_stage, result.error_code), ("uploading", "oss_failed"))
                else:
                    self.assertEqual(result.result_file_id, word.id)

    def test_new_stages_cancel_timeout_and_old_generation_do_not_advance(self):
        for stage in NEW_STAGES:
            for action in ("cancel", "timeout"):
                with self.subTest(stage=stage, action=action), self._runtime() as (runtime, execution, provider, client, headers):
                    with patch.object(execution, "execute_job"):
                        job_id = self._create(client, headers)
                    runtime.document_job_repository.update_document_job(job_id, status="running", stage=stage)
                    if action == "cancel":
                        response = client.post(f"/api/v1/document-jobs/{job_id}/cancel", headers=headers)
                        self.assertEqual(response.status_code, 200, response.json())
                        result = execution.execute_job(job_id)
                        self.assertEqual(result.status, "canceled")
                    else:
                        runtime.document_job_repository.update_document_job(job_id, timeout_at=utc_now() - timedelta(seconds=1))
                        result = execution.execute_job(job_id)
                        self.assertEqual((result.status, result.failed_stage, result.error_code), (
                            "failed", stage, "document_job_timeout",
                        ))
                    before = runtime.document_job_event_repository.list_document_job_events(job_id)
                    execution.execute_job(job_id)
                    execution._finalize_translation_generation(job_id, generation=0, trace_id=None)
                    self.assertEqual(runtime.document_job_event_repository.list_document_job_events(job_id), before)
        with self._runtime() as (runtime, execution, provider, client, headers):
            job, batches = self._completed_batches(runtime, execution, client, headers)
            runtime.document_job_repository.update_document_job(job.id, retry_count=1)
            before = runtime.document_job_repository.get_document_job(job.id)
            events = runtime.document_job_event_repository.list_document_job_events(job.id)
            execution._finalize_translation_generation(job.id, generation=0, trace_id=None)
            execution.execute_translation_batch(batches[0].id)
            self.assertEqual(runtime.document_job_repository.get_document_job(job.id), before)
            self.assertEqual(runtime.document_job_event_repository.list_document_job_events(job.id), events)

    def test_render_failure_from_an_older_generation_cannot_fail_the_current_job(self):
        with self._runtime() as (runtime, execution, provider, client, headers):
            job = self._pause_after_ir(runtime, execution, client, headers)

            def render(*args, **kwargs):
                runtime.document_job_repository.update_document_job(job.id, retry_count=1)
                raise RuntimeError("旧代渲染调用返回失败")

            with patch.object(execution.word_renderer, "render_to_result", side_effect=render):
                result = execution.execute_job(job.id)
            self.assertEqual((result.status, result.stage, result.retry_count), ("running", "rendering", 1))
            self.assertIsNone(result.error_code)

    def test_quality_failure_keeps_render_error_contract_before_publication(self):
        for target in ("build_renderer_evidence", "ensure_renderer_integrity"):
            with self.subTest(target=target), self._runtime() as (runtime, execution, provider, client, headers):
                error = DocumentIntegrityError("DocumentIR→DOCX", {"blocking_quality_flags": ["ir_docx_integrity:missing"]})
                with patch(f"app.domains.document_jobs.execution.{target}", side_effect=error):
                    job_id = self._create(client, headers)
                job = runtime.document_job_repository.get_document_job(job_id)
                self.assertEqual((job.status, job.failed_stage, job.error_code), ("failed", "quality_checking", "render_failed"))
                self.assertFalse(self._files(runtime, job_id, "generated_word"))
                event = runtime.document_job_event_repository.list_document_job_events(job_id)[-1]
                self.assertEqual((event.event_type, event.stage), ("stage_failed", "quality_checking"))
                self.assertGreaterEqual(event.duration_ms, 0)

    def test_legacy_source_ir_preparation_failure_is_persisted_on_first_delivery(self):
        for failure in ("missing_translator", "missing_profile"):
            with self.subTest(failure=failure), self._runtime() as (runtime, execution, provider, client, headers):
                with patch.object(execution, "_ensure_translation_batches_and_enqueue", side_effect=lambda job, *args, **kwargs: job):
                    job_id = self._create(client, headers, mode="en2zh", language="en")
                job = runtime.document_job_repository.get_document_job(job_id)
                self.assertEqual(job.stage, "ir_converting")
                self.assertIsNotNone(job.source_document_ir_file_id)
                if failure == "missing_translator":
                    execution.document_ir_translation_service = None
                else:
                    snapshot = {**job.request_snapshot, "resources": JobResourceSnapshot().model_dump(mode="json")}
                    runtime.document_job_repository.update_document_job(job.id, request_snapshot=snapshot)
                with patch.object(execution.word_renderer, "render_to_result", wraps=execution.word_renderer.render_to_result) as render:
                    failed = execution.execute_job(job.id, trace_id="trace_stage_owner")
                self.assertEqual((failed.status, failed.failed_stage, failed.error_code), ("failed", "translating", "translation_failed"))
                self.assertTrue(failed.error_message)
                failures = [event for event in runtime.document_job_event_repository.list_document_job_events(job.id)
                            if event.event_type == "stage_failed"]
                self.assertEqual([(event.stage, event.payload["error_code"]) for event in failures], [("translating", "translation_failed")])
                self.assertEqual(failures[0].trace_id, "trace_stage_owner")
                self.assertEqual(provider.requests, [])
                render.assert_not_called()
                self.assertEqual(runtime.document_job_translation_batch_repository.list_translation_batches(job.id), [])
                self.assertFalse(self._files(runtime, job.id, "generated_word"))

    def test_post_transition_event_failure_uses_committed_stage_on_first_delivery(self):
        cases = (("parsing", "job"), ("ir_converting", "job"), ("translation_validating", "job"),
                 ("translating", "batch"), ("translation_validating", "batch"))
        for stage, entry in cases:
            with self.subTest(stage=stage, entry=entry), self._runtime(batch_items=100) as (runtime, execution, provider, client, headers):
                batch = None
                if stage == "parsing":
                    with patch.object(execution, "_mark_parsing_started", side_effect=lambda job, **kwargs: job):
                        job_id = self._create(client, headers)
                elif stage == "ir_converting":
                    with patch.object(execution, "_mark_ir_converting_started", side_effect=lambda job, **kwargs: job):
                        job_id = self._create(client, headers)
                elif entry == "job":
                    job, _batches = self._completed_batches(runtime, execution, client, headers)
                    job_id = job.id
                else:
                    execution.translation_batch_task_queue = Mock()
                    job_id = self._create(client, headers, mode="en2zh", language="en")
                    batch = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)[0]
                    if stage == "translating":
                        runtime.document_job_repository.update_document_job(job_id, stage="ir_converting")
                provider_count = len(provider.requests)
                mineru_count = len(execution.fake_mineru_client.calls)
                original_append = runtime.document_job_event_repository.append_document_job_event
                interrupted = []
                def append(job_id, event):
                    if not interrupted and event.event_type == "stage_started" and event.stage == stage:
                        interrupted.append(event.stage)
                        raise OSError("阶段已推进后的事件追加失败")
                    return original_append(job_id, event)
                with patch.object(runtime.document_job_event_repository, "append_document_job_event", side_effect=append), patch.object(
                    execution.word_renderer, "render_to_result", wraps=execution.word_renderer.render_to_result,
                ) as render:
                    if entry == "batch":
                        execution.execute_translation_batch(batch.id, trace_id="trace_stage_owner")
                        failed = runtime.document_job_repository.get_document_job(job_id)
                    else:
                        failed = execution.execute_job(job_id, trace_id="trace_stage_owner")
                self.assertEqual(interrupted, [stage])
                code = {"parsing": "mineru_failed", "ir_converting": "document_ir_failed"}.get(stage, "oss_failed")
                self.assertEqual((failed.status, failed.failed_stage, failed.error_code), ("failed", stage, code))
                failures = [event for event in runtime.document_job_event_repository.list_document_job_events(job_id)
                            if event.event_type == "stage_failed"]
                self.assertEqual([(event.stage, event.payload["error_code"]) for event in failures], [(stage, code)])
                render.assert_not_called()
                self.assertEqual(len(execution.fake_mineru_client.calls), mineru_count)
                self.assertEqual(len(provider.requests), provider_count + (1 if entry == "batch" and stage == "translation_validating" else 0))
                self.assertFalse(self._files(runtime, job_id, "generated_word"))
                if batch is not None and stage == "translating":
                    self.assertEqual(runtime.document_job_translation_batch_repository.get_translation_batch(batch.id).status, "queued")

    def test_legacy_batch_cannot_claim_new_generation_returned_after_stage_event_failure(self):
        with self._runtime(batch_items=100) as (runtime, execution, provider, client, headers):
            execution.translation_batch_task_queue = Mock()
            job_id = self._create(client, headers, mode="en2zh", language="en")
            batch_repository = runtime.document_job_translation_batch_repository
            batch = batch_repository.list_translation_batches(job_id)[0]
            self.assertEqual((batch.generation, batch.job_retry_count, batch.status, batch.attempt_count), (0, 0, "queued", 0))
            runtime.document_job_repository.update_document_job(job_id, stage="ir_converting")
            append = runtime.document_job_event_repository.append_document_job_event
            resumed = []
            def append_after_retry(event_job_id, event):
                if (not resumed and event.event_type == "stage_started" and event.stage == "translating"
                        and event.payload["generation"] == 0):
                    # 旧 helper 的 CAS 已提交；在它尚未返回时，另一 API 调用完成失败和显式换代。
                    current = runtime.document_job_repository.get_document_job(job_id)
                    self.assertEqual((current.retry_count, current.stage), (0, "translating"))
                    execution._mark_failed(current, failed_stage="translating", error_code="translation_failed",
                        error_message="交错中的另一调用确认本代失败", trace_id="trace_new_attempt")
                    response = client.post(f"/api/v1/document-jobs/{job_id}/retry", headers=headers, json={"reason": "显式重试下一代"})
                    self.assertEqual(response.status_code, 200, response.json())
                    next_job = runtime.document_job_repository.get_document_job(job_id)
                    self.assertEqual((next_job.retry_count, next_job.status, next_job.stage), (1, "running", "translating"))
                    resumed.append(next_job)
                    raise OSError("旧代阶段事件在换代后返回失败")
                return append(event_job_id, event)
            with patch.object(runtime.document_job_event_repository, "append_document_job_event", side_effect=append_after_retry), patch.object(
                execution, "_claim_translation_batch", wraps=execution._claim_translation_batch,
            ) as claim, patch.object(
                execution.translation_audit_service, "build_recorder", wraps=execution.translation_audit_service.build_recorder,
            ) as recorder:
                returned = execution.execute_translation_batch(batch.id, trace_id="trace_old_attempt")
            self.assertEqual(len(resumed), 1)
            with self.subTest(boundary="claim"):
                claim.assert_not_called()
                self.assertEqual(returned, batch)
                self.assertEqual(batch_repository.get_translation_batch(batch.id), batch)
            with self.subTest(boundary="provider"):
                self.assertEqual(provider.requests, [])
            with self.subTest(boundary="audit"):
                recorder.assert_not_called()
                self.assertFalse(self._files(runtime, job_id, "ai_call_log"))
            self.assertEqual(runtime.document_job_repository.get_document_job(job_id), resumed[0])
