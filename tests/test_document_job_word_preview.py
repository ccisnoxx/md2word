"""正式 renderer→预览→Artifact/下载，以及单独重试的应用合同。"""

from collections import Counter
from contextlib import contextmanager
import io
from datetime import timedelta
import json
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.parse import urlsplit
from uuid import uuid4

from app.core.errors import ApiError
from app.domains.document_jobs.router import _build_download_token
from app.domains.resources.models import utc_now
from app.services.auth.models import AuthenticatedUser
from app.services.preview.models import PreviewFailure, PreviewPolicy, png_dimensions, sha256, validate_result
from tests import test_fastapi_jobs_backend as fixtures
from tests import test_document_job_result_persistence as result_fixtures
from tests import test_document_job_execution_stages as stage_fixtures
from tests.test_word_preview_provider import preview_result


class RecordingPreviewProvider:
    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)
        self.inputs = []
        self.before_return = None

    def render(self, docx, *, policy):
        self.inputs.append(docx)
        if self.before_return: self.before_return()
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if isinstance(outcome, Exception): raise outcome
        return outcome or preview_result(policy)


def multi_page_preview_result(policy, page_count):
    """生成有完整xref和连续页面的中性PDF及PNG，不代表真实Word分页验收。"""
    result = preview_result(policy)
    stream_id = page_count + 3
    kids = " ".join(f"{index + 3} 0 R" for index in range(page_count))
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode()]
    objects.extend(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] /Resources << >> /Contents {stream_id} 0 R >>".encode()
                   for _ in range(page_count))
    objects.append(b"<< /Length 0 >>\nstream\n\nendstream")
    content, offsets = b"%PDF-1.4\n", []
    for index, body in enumerate(objects, 1):
        offsets.append(len(content))
        content += str(index).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref = len(content)
    content += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    content += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    content += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return result.model_copy(update={"pdf": content, "page_count": page_count,
        "pages": tuple(result.pages[0].model_copy(update={"page_index": index}) for index in range(page_count))})


class DocumentJobWordPreviewTests(TestCase):
    _upload_source_pdf = fixtures.FastAPIJobsBackendTests._upload_source_pdf
    _create = stage_fixtures.DocumentJobExecutionStageTests._create
    _files = stage_fixtures.DocumentJobExecutionStageTests._files
    _pause_after_ir = stage_fixtures.DocumentJobExecutionStageTests._pause_after_ir
    _build_runtime = result_fixtures.DocumentJobResultPersistenceTests._build_runtime

    @contextmanager
    def runtime(self, *, pages=False, outcomes=(), quality="pending", backend="sandboxed", required=True, kind="file"):
        with tempfile.TemporaryDirectory(prefix="rnd504-app-") as directory:
            runtime = self._build_runtime(Path(directory), kind)
            execution = runtime.document_job_execution_service
            provider = RecordingPreviewProvider(outcomes)
            execution.word_preview_service.provider = provider
            execution.word_preview_service.audit_service = runtime.audit_service
            runtime.document_job_service.word_preview_service = execution.word_preview_service
            with fixtures.TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                job = self._pause_after_ir(runtime, execution, client, headers)
                policy = PreviewPolicy(backend=backend, required=required, render_pages=pages)
                job = runtime.document_job_repository.update_document_job(job.id, quality_status=quality,
                    request_snapshot={**job.request_snapshot, "word_preview": policy.model_dump(mode="json")})
                user = AuthenticatedUser(id=job.created_by, username="operator", role="operator",
                                         tenant_id=job.tenant_id, company_id=job.company_id)
                yield runtime, execution, provider, job, user, client, headers

    def test_formal_docx_success_registers_pdf_manifest_pages_and_downloads(self):
        for pages in (False, True):
            with self.subTest(pages=pages), self.runtime(pages=pages) as (runtime, execution, provider, job, user, client, headers):
                result = execution.execute_job(job.id)
                self.assertEqual(result.status, "succeeded", result.error_message)
                self.assertEqual(result.quality_status, "pending")
                main = runtime.document_file_repository.get_document_file(result.result_file_id)
                docx = runtime.file_upload_service.read_file_content(main)
                self.assertEqual(provider.inputs, [docx])
                succeeded_event = next(event for event in runtime.document_job_event_repository.list_document_job_events(job.id) if event.event_type == "preview_succeeded")
                self.assertEqual(succeeded_event.payload["page_count"], 1)
                self.assertEqual(succeeded_event.payload["provider_id"], "test-executor")
                self.assertEqual(sha256(docx), main.checksum_sha256)
                state, run = result.word_preview_state, result.word_preview_state.current_run
                self.assertEqual(state.source_result_file_id, result.result_file_id)
                manifest = runtime.document_file_repository.get_document_file(run.manifest_file_id)
                body = json.loads(runtime.file_upload_service.read_file_content(manifest))
                self.assertEqual(body["schema_version"], "word-preview/v1")
                self.assertEqual(body["source_docx_sha256"], main.checksum_sha256)
                self.assertEqual(body["page_count"], 1)
                self.assertEqual(len(body["pages"]), int(pages))
                if pages:
                    self.assertEqual(tuple(body["pages"][0][key] for key in ("page_index", "width", "height")), (0, 1, 1))
                artifacts = [file for file in self._files(runtime, job.id) if file.file_type.startswith("word_preview_")]
                self.assertEqual(len(artifacts), 2 + int(pages))
                self.assertTrue(all(file.expires_at <= main.expires_at for file in artifacts))
                self.assertEqual(len({file.object_key for file in artifacts}), len(artifacts))
                listed = client.get(f"/api/v1/document-jobs/{job.id}/files", headers=headers)
                self.assertEqual(listed.status_code, 200, listed.json())
                self.assertIn(run.manifest_file_id, str(listed.json()))
                for file in [main, *artifacts]:
                    signed = client.get(f"/api/v1/document-jobs/{job.id}/download-url", params={"file_id": file.id}, headers=headers)
                    self.assertEqual(signed.status_code, 200, signed.json())
                    download = client.get(signed.json()["download_url"])
                    self.assertEqual(download.status_code, 200)
                    self.assertEqual(sha256(download.content), file.checksum_sha256)
                detail = client.get(f"/api/v1/document-jobs/{job.id}", headers=headers).json()
                serialized = json.dumps(detail)
                for private in ("word_preview_state", "lease_token", "request_fingerprint", "runs_by_request_key", "reason_sha256"):
                    self.assertNotIn(private, serialized)
                incident = runtime.document_job_incident_service._build_item(result, user=user, now=utc_now()).model_dump_json()
                self.assertNotIn("lease_token", incident)
                self.assertNotIn("runs_by_request_key", incident)
                self.assertFalse(any("word-preview" in route.path or "word_preview" in route.path for route in fixtures.create_app(runtime).routes))

    def test_failure_then_success_preserves_main_and_restores_only_known_quality(self):
        for base in ("pending", "warning", "passed", "blocked"):
            with self.subTest(base=base), self.runtime(quality=base, outcomes=[PreviewFailure("preview_input_invalid")]) as (
                runtime, execution, provider, job, user, client, headers,
            ):
                failed = execution.execute_job(job.id)
                self.assertEqual((failed.status, failed.quality_status, failed.review_status, failed.delivery_status),
                                 ("succeeded", "blocked", "unreviewed", "internal_draft"))
                self.assertIsNone(failed.error_code)
                receipt = failed.prepared_result
                main = runtime.document_file_repository.get_document_file(failed.result_file_id)
                before = runtime.file_upload_service.read_file_content(main)
                self.assertEqual(len(provider.inputs), 1)
                with patch.object(execution.word_renderer, "render_to_bytes", side_effect=AssertionError("重试不能渲染主件")), patch.object(
                    execution, "mineru_client_factory", side_effect=AssertionError("重试不能调用 MinerU")), patch.object(
                    execution, "_finalize_translation_generation", side_effect=AssertionError("重试不能进入翻译收尾")):
                    retried = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="重试预览", request_id=str(uuid4()))
                succeeded = retried.job
                self.assertEqual(succeeded.quality_status, base)
                self.assertEqual(succeeded.result_file_id, failed.result_file_id)
                self.assertEqual(succeeded.prepared_result, receipt)
                self.assertEqual(runtime.file_upload_service.read_file_content(main), before)
                self.assertEqual((succeeded.review_status, succeeded.delivery_status), ("unreviewed", "internal_draft"))
                self.assertEqual(len(provider.inputs), 2)
                signed = client.get(f"/api/v1/document-jobs/{job.id}/download-url", headers=headers)
                self.assertEqual(client.get(signed.json()["download_url"]).content, before)

    def test_timeout_auto_retry_permanent_failure_and_worker_replay_budget(self):
        for errors, expected_calls, expected_status in (
            ([PreviewFailure("preview_timeout", retryable=True)], 2, "succeeded"),
            ([PreviewFailure("preview_engine_failed", retryable=True)] * 2, 2, "failed"),
            ([PreviewFailure("preview_output_invalid")], 1, "failed"),
        ):
            with self.subTest(errors=errors), self.runtime(outcomes=errors) as (runtime, execution, provider, job, user, client, headers):
                result = execution.execute_job(job.id)
                self.assertEqual(result.status, "succeeded", result.error_message)
                self.assertEqual(result.word_preview_state.current_run.status, expected_status)
                self.assertEqual(len(provider.inputs), expected_calls)
                self.assertEqual(execution.execute_job(job.id), result)
                self.assertEqual(len(provider.inputs), expected_calls)

    def test_historical_application_request_returns_a_while_current_remains_b(self):
        with self.runtime(outcomes=[PreviewFailure("preview_input_invalid")] * 3) as (runtime, execution, provider, job, user, client, headers):
            result = execution.execute_job(job.id)
            a, b = str(uuid4()), str(uuid4())
            first = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="A", request_id=a)
            second = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="B", request_id=b)
            before_calls = len(provider.inputs)
            restarted = self._build_runtime(runtime.settings.data_path, "file")
            restarted.document_job_execution_service.word_preview_service.provider = provider
            replay = restarted.document_job_service.retry_word_preview(job.id, user=user, reason="A", request_id=a)
            self.assertEqual(replay.run.run_id, first.run.run_id)
            self.assertEqual(replay.job.word_preview_state.current_run.run_id, second.run.run_id)
            self.assertEqual(len(provider.inputs), before_calls)
            with self.assertRaises(ApiError):
                runtime.document_job_service.retry_word_preview(job.id, user=user, reason="different", request_id=a)

    def test_concurrent_explicit_block_survives_success_and_approval_never_revives(self):
        with self.runtime(quality="passed", outcomes=[PreviewFailure("preview_input_invalid")]) as (runtime, execution, provider, job, user, client, headers):
            failed = execution.execute_job(job.id)
            provider.before_return = lambda: runtime.document_job_repository.update_document_job(job.id, quality_status="blocked")
            succeeded = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="复查", request_id=str(uuid4())).job
            self.assertEqual(succeeded.quality_status, "blocked")
            self.assertEqual(succeeded.quality_summary["checks_v1"]["__unattributed__"]["quality_status"], "blocked")
            self.assertEqual(succeeded.review_status, "unreviewed")

    def test_disabled_required_and_optional_are_distinct_and_legacy_is_not_backfilled(self):
        for required in (False, True):
            with self.subTest(required=required), self.runtime(backend="disabled", required=required) as (runtime, execution, provider, job, user, client, headers):
                result = execution.execute_job(job.id)
                self.assertEqual(result.status, "succeeded")
                self.assertEqual(result.word_preview_state.current_run.status, "unavailable")
                self.assertEqual(result.quality_status, "blocked" if required else "pending")
                self.assertFalse(provider.inputs)
        with self.runtime() as (runtime, execution, provider, job, user, client, headers):
            snapshot = {key: value for key, value in job.request_snapshot.items() if key != "word_preview"}
            runtime.document_job_repository.update_document_job(job.id, request_snapshot=snapshot)
            result = execution.execute_job(job.id)
            self.assertIsNone(result.word_preview_state)
            self.assertNotIn("word_preview", result.request_snapshot)
            self.assertFalse(provider.inputs)
            with self.assertRaises(ApiError): runtime.document_job_service.retry_word_preview(job.id, user=user, reason="legacy", request_id=str(uuid4()))

    def test_legacy_explicit_main_without_receipt_required_blocks_but_download_stays_available(self):
        for required in (False, True):
            with self.subTest(required=required), self.runtime(required=required) as (runtime, execution, provider, job, user, client, headers):
                original_render = execution.word_renderer.render_to_bytes
                # 显式旧主件使用无新图片标记的真实历史格式，不绕过当前报告认证。
                with patch.object(execution.word_renderer, "render_to_bytes", side_effect=lambda *args, **kwargs: result_fixtures.legacy_image_docx(original_render(*args, **kwargs))):
                    file = stage_fixtures.DocumentJobExecutionStageTests._register_word(self, runtime, job, metadata={"retry_count": 0, "document_ir_file_id": job.document_ir_file_id})
                runtime.document_job_repository.update_document_job(job.id, result_file_id=file.id)
                result = execution.execute_job(job.id)
                self.assertEqual(result.status, "succeeded", result.error_message)
                self.assertIsNone(result.prepared_result)
                self.assertIsNone(result.word_preview_state)
                self.assertEqual(result.quality_status, "blocked" if required else "pending")
                self.assertEqual(result.quality_summary["checks_v1"]["word_preview"]["status"], "unavailable")
                self.assertFalse(provider.inputs)
                signed = client.get(f"/api/v1/document-jobs/{job.id}/download-url", headers=headers)
                self.assertEqual(signed.status_code, 200, signed.json())
                self.assertEqual(client.get(signed.json()["download_url"]).content, runtime.file_upload_service.read_file_content(file))
                with self.assertRaises(ApiError): runtime.document_job_service.retry_word_preview(job.id, user=user, reason="legacy", request_id=str(uuid4()))

    def test_claim_before_event_crash_resumes_same_run_with_consumed_budget(self):
        with self.runtime() as (runtime, execution, provider, job, user, client, headers):
            with patch.object(execution.word_preview_service, "_event", side_effect=result_fixtures.SimulatedProcessExit), self.assertRaises(result_fixtures.SimulatedProcessExit):
                execution.execute_job(job.id)
            interrupted = runtime.document_job_repository.get_document_job(job.id)
            run = interrupted.word_preview_state.current_run
            self.assertEqual(run.attempt_count, 1)
            self.assertFalse(provider.inputs)
            future = run.lease_expires_at + timedelta(milliseconds=1)
            with patch("app.infrastructure.persistence.file.document_jobs.utc_now", return_value=future), patch("app.domains.document_jobs.preview.utc_now", return_value=future):
                completed = execution.execute_job(job.id)
            self.assertEqual(completed.status, "succeeded", completed.error_message)
            self.assertEqual(completed.word_preview_state.current_run.run_id, run.run_id)
            self.assertEqual(completed.word_preview_state.current_run.attempt_count, 2)
            self.assertEqual(len(provider.inputs), 1)

    def test_download_rejects_partial_old_manifest_token_tampering_and_scope(self):
        with self.runtime(outcomes=[PreviewFailure("preview_input_invalid")]) as (runtime, execution, provider, job, user, client, headers):
            result = execution.execute_job(job.id)
            old_manifest = result.word_preview_state.current_run.manifest_file_id
            signed = client.get(f"/api/v1/document-jobs/{job.id}/download-url", params={"file_id": old_manifest}, headers=headers)
            self.assertEqual(signed.status_code, 200)
            old_url = signed.json()["download_url"]
            self.assertEqual(client.get(old_url).status_code, 200)
            current = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="恢复预览", request_id=str(uuid4())).job
            self.assertEqual(client.get(old_url).status_code, 409)
            self.assertEqual(client.get(f"/api/v1/document-jobs/{job.id}/download-url", params={"file_id": old_manifest}, headers=headers).status_code, 409)
            source = runtime.document_file_repository.get_document_file(current.result_file_id)
            partial = execution.word_preview_service._register(current, source, "word_preview_pdf", "partial.pdf", b"partial", "application/pdf")
            self.assertEqual(client.get(f"/api/v1/document-jobs/{job.id}/download-url", params={"file_id": partial.id}, headers=headers).status_code, 409)
            pdf_id = current.quality_summary["checks_v1"]["word_preview"]["pdf_file_id"]
            url = client.get(f"/api/v1/document-jobs/{job.id}/download-url", params={"file_id": pdf_id}, headers=headers).json()["download_url"]
            self.assertIn(client.get(url + "bad").status_code, (401, 403))
            token = _build_download_token(runtime, job_id=job.id, file_id=pdf_id, expires_at=utc_now() - timedelta(seconds=1))
            self.assertIn(client.get(f"/api/v1/document-jobs/{job.id}/download", params={"token": token}).status_code, (401, 403))
            for stranger in (user.model_copy(update={"id": "other"}), user.model_copy(update={"tenant_id": "other"}), user.model_copy(update={"company_id": "other"})):
                with self.assertRaises(ApiError): runtime.document_job_service.get_file_for_download(job.id, user=stranger, file_id=pdf_id)
                with self.assertRaises(ApiError): runtime.document_job_service.retry_word_preview(job.id, user=stranger, reason="other", request_id=str(uuid4()))
            admin = user.model_copy(update={"id": "admin", "role": "admin"})
            self.assertEqual(runtime.document_job_service.get_file_for_download(job.id, user=admin, file_id=pdf_id)[1].id, pdf_id)
            runtime.document_file_repository.update_document_file(pdf_id, checksum_sha256=sha256(b"tampered"))
            self.assertEqual(client.get(url).status_code, 409)

    def test_s3_signing_has_finite_ttl_and_rejects_old_reference(self):
        with self.runtime(outcomes=[PreviewFailure("preview_input_invalid")]) as (runtime, execution, provider, job, user, client, headers):
            failed = execution.execute_job(job.id)
            old = runtime.document_file_repository.get_document_file(failed.word_preview_state.current_run.manifest_file_id)
            manifest_bytes = runtime.file_upload_service.read_file_content(old)
            old = runtime.document_file_repository.update_document_file(old.id, storage_provider="s3", bucket="test-bucket")
            fake_s3 = Mock()
            fake_s3.get_object.side_effect = lambda **kwargs: {"Body": io.BytesIO(manifest_bytes)}
            fake_s3.generate_presigned_url.return_value = "https://s3.example.invalid/finite-url"
            source = runtime.document_file_repository.get_document_file(failed.result_file_id)
            runtime.document_file_repository.update_document_file(source.id, expires_at=utc_now() + timedelta(seconds=100))
            # 授权时先核当前引用；直连 URL 不经过本地 Token，因此不宣称即时撤销。
            with patch.object(runtime.file_upload_service, "_s3_client", return_value=fake_s3):
                runtime.document_job_service.get_file_for_download(job.id, user=user, file_id=old.id)
                runtime.file_upload_service.create_presigned_download_url(old, expires_seconds=99999)
                self.assertLessEqual(fake_s3.generate_presigned_url.call_args.kwargs["ExpiresIn"], 100)
                runtime.document_job_repository.update_document_job(job.id, word_preview_state=None)
                with self.assertRaises(ApiError): runtime.document_job_service.get_file_for_download(job.id, user=user, file_id=old.id)
                self.assertEqual(fake_s3.generate_presigned_url.call_count, 1)

    def test_storage_and_source_failures_keep_original_execution_failure_contract(self):
        for point in ("source", "hash", "manifest"):
            with self.subTest(point=point), self.runtime() as (runtime, execution, provider, job, user, client, headers):
                service = execution.word_preview_service
                original = service._register
                if point == "source": target = patch.object(service, "_source", side_effect=OSError("主件读取失败"))
                elif point == "hash": target = patch.object(runtime.file_upload_service, "read_file_content", side_effect=lambda file: b"bad" if file.file_type == "generated_word" else original_read(file))
                else: target = patch.object(service, "_register", side_effect=lambda *args: (_ for _ in ()).throw(OSError("metadata 失败")) if args[2] == "word_preview_manifest" else original(*args))
                original_read = runtime.file_upload_service.read_file_content
                with target: result = execution.execute_job(job.id)
                self.assertEqual((result.status, result.failed_stage, result.error_code), ("failed", "uploading", "oss_failed"))
                self.assertIsNotNone(result.prepared_result)
                self.assertIsNone(result.result_file_id)

    def test_preview_metadata_and_object_failures_never_complete_and_are_traceable(self):
        for kind in ("file", "sqlite"):
            for file_type in ("word_preview_pdf", "word_preview_page", "word_preview_manifest"):
                for point in ("insert", "object", "uploaded"):
                    with self.subTest(kind=kind, file_type=file_type, point=point), self.runtime(pages=True, kind=kind) as (runtime, execution, provider, job, user, client, headers):
                        repo, service = runtime.document_file_repository, runtime.file_upload_service
                        create, write, update = repo.create_document_file, service._write_object, repo.update_document_file
                        attempted, observed = [], []

                        def create_metadata(record):
                            if record.file_type == file_type and point == "insert":
                                attempted.append(record)
                                raise OSError("预览 metadata 插入失败")
                            return create(record)

                        def write_object(record, content):
                            if record.file_type.startswith("word_preview_"):
                                observed.append((record.id, repo.get_document_file(record.id)))
                            if record.file_type == file_type:
                                attempted.append(record)
                                if point == "object":
                                    write(record, content)
                                    raise OSError("预览对象响应丢失")
                            return write(record, content)

                        def confirm_uploaded(file_id, **changes):
                            record = repo.get_document_file(file_id)
                            if record.file_type == file_type and changes.get("status") == "uploaded" and point == "uploaded":
                                raise OSError("预览 metadata 确认失败")
                            return update(file_id, **changes)

                        with patch.object(repo, "create_document_file", side_effect=create_metadata), patch.object(service, "_write_object", side_effect=write_object), patch.object(repo, "update_document_file", side_effect=confirm_uploaded):
                            result = execution.execute_job(job.id)
                        self.assertEqual((result.status, result.failed_stage, result.error_code), ("failed", "uploading", "oss_failed"))
                        self.assertIsNotNone(result.prepared_result)
                        self.assertIsNone(result.result_file_id)
                        main = repo.get_document_file(result.prepared_result.file.id)
                        self.assertEqual(sha256(service.read_file_content(main)), result.prepared_result.file.checksum_sha256)
                        self.assertTrue(all(record is not None and record.status == "pending_upload" for _, record in observed))
                        target = attempted[-1]
                        persisted = repo.get_document_file(target.id)
                        path = service.resolve_local_object_path(target.object_key)
                        if point == "insert":
                            self.assertIsNone(persisted)
                            self.assertFalse(path.exists())
                        else:
                            self.assertEqual(persisted.status, "pending_upload")
                            self.assertTrue(path.exists())
                        self.assertIsNone(result.word_preview_state.current_run.manifest_file_id)

    def test_partial_output_registration_failure_keeps_main_and_hides_uncommitted_files(self):
        with self.runtime(pages=True) as (runtime, execution, provider, job, user, client, headers):
            service = execution.word_preview_service
            original = service._register

            def fail_page(*args):
                if args[2] == "word_preview_page": raise OSError("页面存储不可用")
                return original(*args)

            with patch.object(service, "_register", side_effect=fail_page):
                failed = execution.execute_job(job.id)
            self.assertEqual((failed.status, failed.error_code), ("failed", "oss_failed"))
            self.assertIsNotNone(failed.prepared_result)
            self.assertIsNone(failed.word_preview_state.current_run.manifest_file_id)
            main = runtime.document_file_repository.get_document_file(failed.prepared_result.file.id)
            self.assertEqual(sha256(runtime.file_upload_service.read_file_content(main)), failed.prepared_result.file.checksum_sha256)
            partial = self._files(runtime, job.id, "word_preview_pdf")[0]
            self.assertEqual(partial.status, "uploaded")
            self.assertEqual(client.get(f"/api/v1/document-jobs/{job.id}/download-url", params={"file_id": partial.id}, headers=headers).status_code, 409)
            with self.assertRaises(ApiError):
                runtime.document_job_service.retry_word_preview(job.id, user=user, reason="尚未完成", request_id=str(uuid4()))
            listed = client.get(f"/api/v1/document-jobs/{job.id}/files", headers=headers)
            self.assertNotIn(partial.id, str(listed.json()))

    def test_independent_retry_registration_failure_cannot_commit_success(self):
        for file_type in ("word_preview_pdf", "word_preview_page", "word_preview_manifest"):
            for point in ("insert", "object", "uploaded"):
                with self.subTest(file_type=file_type, point=point), self.runtime(pages=True, outcomes=[PreviewFailure("preview_input_invalid")]) as (runtime, execution, provider, job, user, client, headers):
                    original = execution.execute_job(job.id)
                    repo, service = runtime.document_file_repository, runtime.file_upload_service
                    main = repo.get_document_file(original.result_file_id)
                    main_bytes = service.read_file_content(main)
                    create, write, update = repo.create_document_file, service._write_object, repo.update_document_file

                    def create_metadata(record):
                        if record.file_type == file_type and point == "insert": raise OSError("预览 metadata 不可用")
                        return create(record)

                    def write_object(record, content):
                        if record.file_type == file_type and point == "object": raise OSError("预览对象不可用")
                        return write(record, content)

                    def confirm_uploaded(file_id, **changes):
                        if repo.get_document_file(file_id).file_type == file_type and point == "uploaded": raise OSError("预览 metadata 不可用")
                        return update(file_id, **changes)

                    with patch.object(repo, "create_document_file", side_effect=create_metadata), patch.object(service, "_write_object", side_effect=write_object), patch.object(repo, "update_document_file", side_effect=confirm_uploaded), self.assertRaises(OSError):
                        runtime.document_job_service.retry_word_preview(job.id, user=user, reason="独立预览重试", request_id=str(uuid4()))
                    current = runtime.document_job_repository.get_document_job(job.id)
                    self.assertEqual((current.status, current.quality_status), ("succeeded", "blocked"))
                    self.assertEqual(current.prepared_result, original.prepared_result)
                    self.assertEqual(current.result_file_id, original.result_file_id)
                    self.assertEqual(service.read_file_content(main), main_bytes)
                    self.assertEqual(current.word_preview_state.current_run.status, "running")
                    self.assertIsNone(current.word_preview_state.current_run.manifest_file_id)
                    self.assertEqual(len(provider.inputs), 2)

    def test_success_reuse_key_is_durable_and_conflicting_reason_is_rejected_without_provider(self):
        with self.runtime() as (runtime, execution, provider, job, user, client, headers):
            selected = execution.execute_job(job.id)
            request_id = str(uuid4())
            reused = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="复用成功预览", request_id=request_id)
            self.assertEqual(reused.run.run_id, selected.word_preview_state.current_run.run_id)
            self.assertEqual(reused.job.word_preview_state.current_request_key, "initial")
            self.assertIn(request_id, reused.job.word_preview_state.runs_by_request_key)
            restarted = self._build_runtime(runtime.settings.data_path, "file")
            restarted.document_job_execution_service.word_preview_service.provider = provider
            replay = restarted.document_job_service.retry_word_preview(job.id, user=user, reason="复用成功预览", request_id=request_id)
            self.assertEqual(replay.run, reused.run)
            with self.assertRaises(ApiError) as error:
                restarted.document_job_service.retry_word_preview(job.id, user=user, reason="不同原因", request_id=request_id)
            self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(len(provider.inputs), 1)

    def test_snapshot_clone_strategy_and_retry_do_not_take_current_profile(self):
        with self.runtime() as (runtime, execution, provider, job, user, client, headers):
            original = job.request_snapshot["word_preview"]
            runtime.settings.word_preview_profile_id = "new-profile"
            runtime.document_job_service.task_queue = None
            kept = runtime.document_job_service.clone_job(job.id, user=user, reason="保留策略", config_strategy="keep_source_snapshot")
            self.assertEqual(kept.request_snapshot["word_preview"], original)
            self.assertIsNone(kept.word_preview_state)
            fresh = runtime.document_job_service.clone_job(job.id, user=user, reason="当前配置", config_strategy="use_current_defaults")
            self.assertEqual(fresh.request_snapshot["word_preview"]["profile_id"], "new-profile")
            runtime.document_job_repository.update_document_job(job.id, status="failed", stage="failed", error_code="render_failed", failed_stage="rendering")
            runtime.document_job_service.task_queue = None
            runtime.document_job_service.retry_job(job.id, user=user, reason="原任务重试", trace_id="preview-test")
            self.assertEqual(runtime.document_job_repository.get_document_job(job.id).request_snapshot["word_preview"], original)

    def test_final_attempt_registration_crash_is_storage_failure_after_restart(self):
        for kind in ("file", "sqlite"):
            for file_type in ("word_preview_pdf", "word_preview_page", "word_preview_manifest"):
                for point in ("insert_before", "insert_after", "object_after", "confirm_before", "confirm_after"):
                    with self.subTest(kind=kind, file_type=file_type, point=point), self.runtime(pages=True, kind=kind) as (
                        runtime, execution, provider, job, user, client, headers,
                    ):
                        policy = PreviewPolicy(backend="sandboxed", required=True, render_pages=True, max_attempts=1)
                        runtime.document_job_repository.update_document_job(job.id,
                            request_snapshot={**job.request_snapshot, "word_preview": policy.model_dump(mode="json")})
                        files, service = runtime.document_file_repository, runtime.file_upload_service
                        create, write, update = files.create_document_file, service._write_object, files.update_document_file

                        def insert(record):
                            if record.file_type == file_type and point == "insert_before":
                                raise result_fixtures.SimulatedProcessExit()
                            result = create(record)
                            if record.file_type == file_type and point == "insert_after":
                                raise result_fixtures.SimulatedProcessExit()
                            return result

                        def object_write(record, content):
                            result = write(record, content)
                            if record.file_type == file_type and point == "object_after":
                                raise result_fixtures.SimulatedProcessExit()
                            return result

                        def confirm(file_id, **changes):
                            target = files.get_document_file(file_id).file_type == file_type and changes.get("status") == "uploaded"
                            if target and point == "confirm_before":
                                raise result_fixtures.SimulatedProcessExit()
                            result = update(file_id, **changes)
                            if target and point == "confirm_after":
                                raise result_fixtures.SimulatedProcessExit()
                            return result

                        with patch.object(files, "create_document_file", side_effect=insert), patch.object(service, "_write_object", side_effect=object_write), patch.object(files, "update_document_file", side_effect=confirm), self.assertRaises(result_fixtures.SimulatedProcessExit):
                            execution.execute_job(job.id)
                        interrupted = runtime.document_job_repository.get_document_job(job.id)
                        run = interrupted.word_preview_state.current_run
                        self.assertEqual((interrupted.status, run.attempt_count, run.artifact_stage, run.confirmed_attempt),
                                         ("running", 1, "registering", None))
                        self.assertIsNone(run.manifest_file_id)
                        receipt = interrupted.prepared_result
                        main = files.get_document_file(receipt.file.id)
                        before = service.read_file_content(main)
                        restarted = self._build_runtime(runtime.settings.data_path, kind)
                        restarted.document_job_execution_service.word_preview_service.provider = provider
                        future = run.lease_expires_at + timedelta(milliseconds=1)
                        with patch(f"app.infrastructure.persistence.{kind}.document_jobs.utc_now", return_value=future), patch("app.domains.document_jobs.preview.utc_now", return_value=future):
                            failed = restarted.document_job_execution_service.execute_job(job.id)
                            repeated = restarted.document_job_execution_service.execute_job(job.id)
                        self.assertEqual((failed.status, failed.failed_stage, failed.error_code), ("failed", "uploading", "oss_failed"))
                        self.assertEqual(failed.word_preview_state.current_run.error_code, "preview_storage_failed")
                        self.assertEqual(failed.prepared_result, receipt)
                        self.assertIsNone(failed.result_file_id)
                        self.assertEqual(repeated, failed)
                        self.assertEqual(len(provider.inputs), 1)
                        self.assertEqual(service.read_file_content(main), before)

    def test_previous_failure_manifest_does_not_confirm_next_interrupted_attempt(self):
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), self.runtime(kind=kind, outcomes=[PreviewFailure("preview_timeout", retryable=True)]) as (
                runtime, execution, provider, job, user, client, headers,
            ):
                register = execution.word_preview_service._register

                def interrupt_second(*args):
                    if args[0].word_preview_state.current_run.attempt_count == 2:
                        raise result_fixtures.SimulatedProcessExit()
                    return register(*args)

                with patch.object(execution.word_preview_service, "_register", side_effect=interrupt_second), self.assertRaises(result_fixtures.SimulatedProcessExit):
                    execution.execute_job(job.id)
                interrupted = runtime.document_job_repository.get_document_job(job.id)
                run = interrupted.word_preview_state.current_run
                self.assertEqual((run.attempt_count, run.artifact_stage, run.confirmed_attempt), (2, "registering", None))
                self.assertIsNone(run.manifest_file_id)
                self.assertEqual(len(self._files(runtime, job.id, "word_preview_manifest")), 1)
                restarted = self._build_runtime(runtime.settings.data_path, kind)
                restarted.document_job_execution_service.word_preview_service.provider = provider
                future = run.lease_expires_at + timedelta(milliseconds=1)
                with patch(f"app.infrastructure.persistence.{kind}.document_jobs.utc_now", return_value=future), patch("app.domains.document_jobs.preview.utc_now", return_value=future):
                    failed = restarted.document_job_execution_service.execute_job(job.id)
                self.assertEqual((failed.status, failed.error_code), ("failed", "oss_failed"))
                self.assertEqual(len(provider.inputs), 2)

    def test_unstarted_exhaustion_registers_failure_without_provider_or_deadline_extension(self):
        for kind in ("file", "sqlite"):
            for expired in (False, True):
                with self.subTest(kind=kind, expired=expired), self.runtime(kind=kind) as (runtime, execution, provider, job, user, client, headers):
                    policy = PreviewPolicy(backend="sandboxed", required=True, max_attempts=1)
                    runtime.document_job_repository.update_document_job(job.id,
                        request_snapshot={**job.request_snapshot, "word_preview": policy.model_dump(mode="json")})
                    with patch.object(execution.word_preview_service, "_event", side_effect=result_fixtures.SimulatedProcessExit), self.assertRaises(result_fixtures.SimulatedProcessExit):
                        execution.execute_job(job.id)
                    run = runtime.document_job_repository.get_document_job(job.id).word_preview_state.current_run
                    self.assertEqual(run.artifact_stage, "not_started")
                    future = (run.run_deadline_at if expired else run.lease_expires_at) + timedelta(milliseconds=1)
                    restarted = self._build_runtime(runtime.settings.data_path, kind)
                    restarted.document_job_execution_service.word_preview_service.provider = provider
                    with patch(f"app.infrastructure.persistence.{kind}.document_jobs.utc_now", return_value=future), patch("app.domains.document_jobs.preview.utc_now", return_value=future):
                        result = restarted.document_job_execution_service.execute_job(job.id)
                    current = result.word_preview_state.current_run
                    self.assertEqual((current.attempt_count, current.run_deadline_at), (1, run.run_deadline_at))
                    self.assertFalse(provider.inputs)
                    if expired:
                        self.assertEqual((result.status, result.error_code), ("failed", "oss_failed"))
                        self.assertIsNone(current.manifest_file_id)
                    else:
                        self.assertEqual((result.status, result.quality_status, current.status), ("succeeded", "blocked", "failed"))
                        self.assertEqual((current.artifact_stage, current.confirmed_attempt), ("confirmed", 1))
                        self.assertIsNotNone(current.manifest_file_id)

    def test_independent_unknown_registration_replay_fails_without_changing_execution(self):
        with self.runtime(outcomes=[PreviewFailure("preview_input_invalid")]) as (runtime, execution, provider, job, user, client, headers):
            original = execution.execute_job(job.id)
            key = str(uuid4())
            with patch.object(execution.word_preview_service, "_register", side_effect=result_fixtures.SimulatedProcessExit), self.assertRaises(result_fixtures.SimulatedProcessExit):
                runtime.document_job_service.retry_word_preview(job.id, user=user, reason="未知登记", request_id=key)
            run = runtime.document_job_repository.get_document_job(job.id).word_preview_state.current_run
            future = run.lease_expires_at + timedelta(milliseconds=1)
            restarted = self._build_runtime(runtime.settings.data_path, "file")
            restarted.document_job_execution_service.word_preview_service.provider = provider
            with patch("app.infrastructure.persistence.file.document_jobs.utc_now", return_value=future), patch("app.domains.document_jobs.preview.utc_now", return_value=future):
                for _ in range(2):
                    with self.assertRaises(PreviewFailure) as error:
                        restarted.document_job_service.retry_word_preview(job.id, user=user, reason="未知登记", request_id=key)
                    self.assertEqual(error.exception.code, "preview_storage_failed")
            current = runtime.document_job_repository.get_document_job(job.id)
            self.assertEqual((current.status, current.stage, current.result_file_id, current.prepared_result),
                             (original.status, original.stage, original.result_file_id, original.prepared_result))
            self.assertEqual(current.quality_status, "blocked")
            self.assertEqual(len(provider.inputs), 2)

    def test_formula_fallback_warning_survives_preview_failure_and_success(self):
        for base, expected in (("passed", "warning"), ("pending", "pending"), ("warning", "warning")):
            with self.subTest(base=base), self.runtime(quality=base, outcomes=[PreviewFailure("preview_input_invalid")]) as (
                runtime, execution, provider, job, user, client, headers,
            ):
                result_fixtures.DocumentJobResultPersistenceTests._install_formula_ir(self, runtime, execution, job)
                failed = execution.execute_job(job.id)
                self.assertEqual((failed.status, failed.quality_status), ("succeeded", "blocked"), failed.error_message)
                self.assertEqual(failed.quality_summary["formula"]["fallback_count"], 1)
                retried = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="公式与预览复核", request_id=str(uuid4())).job
                self.assertEqual(retried.quality_status, expected)
                self.assertEqual(retried.quality_summary["formula"], failed.quality_summary["formula"])
                self.assertEqual(retried.prepared_result, failed.prepared_result)

    def test_preview_lifecycle_loss_gets_new_bounded_run_and_keeps_old_key_historical(self):
        for file_type in ("word_preview_manifest", "word_preview_pdf", "word_preview_page"):
            for loss in ("expired", "deleted", "missing"):
                with self.subTest(file_type=file_type, loss=loss), self.runtime(pages=True, quality="passed") as (
                    runtime, execution, provider, job, user, client, headers,
                ):
                    original = execution.execute_job(job.id)
                    first_key = str(uuid4())
                    alias = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="原有效预览", request_id=first_key)
                    self.assertTrue(alias.available)
                    old = self._files(runtime, job.id, file_type)[0]
                    old_token = _build_download_token(runtime, job_id=job.id, file_id=old.id, expires_at=utc_now() + timedelta(hours=1))
                    old_url = f"/api/v1/document-jobs/{job.id}/download?token={old_token}"
                    self.assertEqual(client.get(old_url).status_code, 200)
                    runtime.document_job_repository.update_document_job(job.id, review_status="approved", delivery_status="ready_to_publish")
                    if loss == "expired":
                        runtime.document_file_repository.update_document_file(old.id, expires_at=utc_now() - timedelta(seconds=1))
                    elif loss == "deleted":
                        runtime.document_file_repository.update_document_file(old.id, status="deleted")
                    else:
                        runtime.file_upload_service.resolve_local_object_path(old.object_key).unlink()
                    self.assertEqual(client.get(old_url).status_code, 409)
                    observed = []
                    provider.before_return = lambda: observed.append(runtime.document_job_repository.get_document_job(job.id))
                    with patch.object(execution.word_renderer, "render_to_result", side_effect=AssertionError("不能重渲染DOCX")):
                        recovered = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="生命周期恢复", request_id=str(uuid4()))
                    self.assertTrue(recovered.available)
                    self.assertEqual((observed[0].quality_status, observed[0].review_status), ("blocked", "unreviewed"))
                    self.assertNotEqual(recovered.run.run_id, original.word_preview_state.current_run.run_id)
                    self.assertEqual(recovered.job.prepared_result, original.prepared_result)
                    self.assertEqual((recovered.job.retry_count, recovered.job.result_file_id), (original.retry_count, original.result_file_id))
                    replay = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="原有效预览", request_id=first_key)
                    self.assertEqual(replay.run, alias.run)
                    self.assertFalse(replay.available)
                    self.assertEqual(replay.job.word_preview_state.current_run.run_id, recovered.run.run_id)
                    self.assertEqual(len(provider.inputs), 2)
                    self.assertEqual(len(recovered.job.word_preview_state.runs_by_request_key), 3)
                    self.assertEqual(client.get(old_url).status_code, 409)

    def test_manifest_type_retention_expiry_restores_without_touching_primary(self):
        with self.runtime(quality="passed") as (runtime, execution, provider, job, user, client, headers):
            runtime.file_upload_service.retention_days_resolver = lambda kind: 1 if kind == "word_preview_manifest" else 90
            original = execution.execute_job(job.id)
            source = runtime.document_file_repository.get_document_file(original.result_file_id)
            manifest = runtime.document_file_repository.get_document_file(original.word_preview_state.current_run.manifest_file_id)
            self.assertGreater((source.expires_at - manifest.expires_at).days, 80)
            future = manifest.expires_at + timedelta(seconds=1)
            with patch("app.domains.document_jobs.preview.utc_now", return_value=future), patch("app.infrastructure.persistence.file.document_jobs.utc_now", return_value=future), patch("app.domains.files.service.utc_now", return_value=future):
                result = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="按类型期限恢复", request_id=str(uuid4()))
            self.assertTrue(result.available)
            self.assertNotEqual(result.run.manifest_file_id, manifest.id)
            self.assertEqual(result.job.prepared_result, original.prepared_result)
            self.assertEqual(len(provider.inputs), 2)

    def test_unknown_storage_and_integrity_failure_do_not_consume_recovery_key(self):
        for failure in ("timeout", "metadata", "hash"):
            with self.subTest(failure=failure), self.runtime(pages=True) as (runtime, execution, provider, job, user, client, headers):
                original = execution.execute_job(job.id)
                target = self._files(runtime, job.id, "word_preview_pdf")[0]
                read = runtime.file_upload_service.read_file_content
                get = runtime.document_file_repository.get_document_file

                def read_output(file):
                    if file.id == target.id:
                        if failure == "timeout":
                            raise TimeoutError("对象存储状态未知")
                        if failure == "hash":
                            return "损坏的预览".encode()
                    return read(file)

                def get_output(file_id):
                    if file_id == target.id and failure == "metadata":
                        raise OSError("metadata读取状态未知")
                    return get(file_id)

                with patch.object(runtime.file_upload_service, "read_file_content", side_effect=read_output), patch.object(runtime.document_file_repository, "get_document_file", side_effect=get_output), self.assertRaises((ApiError, OSError)):
                    runtime.document_job_service.retry_word_preview(job.id, user=user, reason="未知不可再生成", request_id=str(uuid4()))
                current = runtime.document_job_repository.get_document_job(job.id)
                self.assertEqual(current.word_preview_state, original.word_preview_state)
                self.assertEqual(len(provider.inputs), 1)

    def test_lifecycle_change_after_observation_cannot_report_available_alias(self):
        with self.runtime() as (runtime, execution, provider, job, user, client, headers):
            original = execution.execute_job(job.id)
            pdf = self._files(runtime, job.id, "word_preview_pdf")[0]
            claim = runtime.document_job_repository.claim_document_job_preview
            consumed = str(uuid4())

            def delete_then_claim(*args, **kwargs):
                runtime.document_file_repository.update_document_file(pdf.id, status="deleted")
                return claim(*args, **kwargs)

            with patch.object(runtime.document_job_repository, "claim_document_job_preview", side_effect=delete_then_claim):
                result = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="观测后删除", request_id=consumed)
            self.assertEqual(result.run.run_id, original.word_preview_state.current_run.run_id)
            self.assertFalse(result.available)
            replay = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="观测后删除", request_id=consumed)
            self.assertFalse(replay.available)
            self.assertEqual(len(provider.inputs), 1)
            recovered = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="后续新key恢复", request_id=str(uuid4()))
            self.assertTrue(recovered.available)
            self.assertEqual(len(provider.inputs), 2)

    def test_new_disabled_snapshot_keeps_unchecked_quality_and_con104_download_policy(self):
        with self.runtime(quality="passed", backend="disabled", required=False) as (runtime, execution, provider, job, user, client, headers):
            result = execution.execute_job(job.id)
            self.assertEqual(runtime.settings.word_preview_backend, "disabled")
            self.assertEqual((result.status, result.quality_status), ("succeeded", "pending"))
            checks = result.quality_summary["checks_v1"]
            self.assertEqual(checks["__unattributed__"]["quality_status"], "passed")
            self.assertEqual((checks["word_preview"]["quality_status"], checks["word_preview"]["error_code"]),
                             ("pending", "preview_disabled"))
            self.assertFalse(provider.inputs)
            signed = client.get(f"/api/v1/document-jobs/{job.id}/download-url", headers=headers)
            self.assertEqual(signed.status_code, 200, signed.json())
            self.assertEqual((signed.json()["classification"], signed.json()["warning_code"]),
                             ("internal_only", "document_unreviewed_not_deliverable"))
            self.assertEqual(client.get(signed.json()["download_url"]).status_code, 200)
            admin = user.model_copy(update={"role": "admin"})
            actions = runtime.document_job_service.build_available_actions(result, user=admin)
            self.assertFalse(actions["publish"].eligible)
            self.assertFalse(actions["publish"].enabled)
            self.assertEqual([entry.code for entry in actions["publish"].disabled_reasons][-2:],
                             ["preview_unavailable", "publication_unavailable"])

    def test_successful_preview_keeps_publish_eligible_separate_from_enabled(self):
        with self.runtime(quality="passed") as (runtime, execution, provider, job, user, client, headers):
            result = execution.execute_job(job.id)
            result = runtime.document_job_repository.update_document_job(job.id, review_status="approved")
            actions = runtime.document_job_service.build_available_actions(result, user=user.model_copy(update={"role": "admin"}))
            self.assertTrue(actions["publish"].eligible)
            self.assertFalse(actions["publish"].enabled)
            self.assertEqual([entry.code for entry in actions["publish"].disabled_reasons],
                             ["preview_unavailable", "publication_unavailable"])
            signed = client.get(f"/api/v1/document-jobs/{job.id}/download-url", headers=headers)
            self.assertEqual((signed.json()["classification"], signed.json()["warning_code"]), ("internal_only", None))

    def test_s3_pdf_url_ttl_is_bounded_by_manifest_and_required_page(self):
        for shortest in ("word_preview_manifest", "word_preview_page"):
            with self.subTest(shortest=shortest), self.runtime(pages=True) as (runtime, execution, provider, job, user, client, headers):
                result = execution.execute_job(job.id)
                pdf = self._files(runtime, job.id, "word_preview_pdf")[0]
                pdf_bytes = runtime.file_upload_service.read_file_content(pdf)
                deadline = utc_now() + timedelta(seconds=60)
                target = self._files(runtime, job.id, shortest)[0]
                runtime.document_file_repository.update_document_file(target.id, expires_at=deadline)
                runtime.document_file_repository.update_document_file(pdf.id, storage_provider="s3", bucket="test-bucket")
                fake = Mock()
                fake.get_object.side_effect = lambda **kwargs: {"Body": io.BytesIO(pdf_bytes)}
                fake.generate_presigned_url.return_value = "https://s3.example.invalid/bounded"
                with patch.object(runtime.file_upload_service, "_s3_client", return_value=fake):
                    signed = client.get(f"/api/v1/document-jobs/{job.id}/download-url", params={"file_id": pdf.id}, headers=headers)
                self.assertEqual(signed.status_code, 200, signed.json())
                self.assertGreater(fake.generate_presigned_url.call_args.kwargs["ExpiresIn"], 0)
                self.assertLessEqual(fake.generate_presigned_url.call_args.kwargs["ExpiresIn"], 60)
                from datetime import datetime
                self.assertLessEqual(datetime.fromisoformat(signed.json()["expires_at"]), deadline)

    def test_multi_page_file_list_observes_once_with_linear_reads_and_decodes(self):
        for page_count in (3, 10):
            with self.subTest(page_count=page_count), self.runtime(pages=True) as (runtime, execution, provider, job, user, client, headers):
                policy = PreviewPolicy.model_validate(job.request_snapshot["word_preview"])
                provider.outcomes.append(multi_page_preview_result(policy, page_count))
                result = execution.execute_job(job.id)
                self.assertEqual(result.status, "succeeded", result.error_message)
                current = {file.id for file in self._files(runtime, job.id) if file.file_type.startswith("word_preview_")}
                source = runtime.document_file_repository.get_document_file(result.result_file_id)
                excluded = []
                page_content = preview_result(policy).pages[0].content
                for variant in ("partial", "old-run", "cross-scope"):
                    record = execution.word_preview_service._register(result, source, "word_preview_page",
                        variant + ".png", page_content, "image/png")
                    if variant == "old-run":
                        runtime.document_file_repository.update_document_file(record.id, metadata={**record.metadata, "run_id": "old-run"})
                    elif variant == "cross-scope":
                        runtime.document_file_repository.update_document_file(record.id, tenant_id="other-tenant")
                    excluded.append(record.id)
                from app.domains.document_jobs.preview import observe_current_preview
                with patch.object(runtime.file_upload_service, "read_file_content", wraps=runtime.file_upload_service.read_file_content) as read, patch(
                    "app.domains.document_jobs.preview.observe_current_preview", wraps=observe_current_preview,
                ) as observe, patch("app.domains.document_jobs.preview.validate_result", wraps=validate_result) as validate, patch(
                    "app.services.preview.models.png_dimensions", wraps=png_dimensions,
                ) as decode:
                    response = client.get(f"/api/v1/document-jobs/{job.id}/files", headers=headers)
                self.assertEqual(response.status_code, 200, response.json())
                listed = {file["id"] for file in response.json()["files"]}
                self.assertTrue(current <= listed)
                self.assertFalse(set(excluded) & listed)
                self.assertIn(result.result_file_id, listed)
                self.assertEqual(observe.call_count, 1)
                self.assertEqual((read.call_count, validate.call_count, decode.call_count), (page_count + 3, 1, page_count))
                self.assertEqual(set(Counter(call.args[0].id for call in read.call_args_list).values()), {1})

    def test_multi_page_file_list_hides_whole_preview_on_expiry_corruption_or_unknown_storage(self):
        for page_count in (3, 10):
            for failure in ("expired", "corrupt", "unknown"):
                with self.subTest(page_count=page_count, failure=failure), self.runtime(pages=True) as (
                    runtime, execution, provider, job, user, client, headers,
                ):
                    policy = PreviewPolicy.model_validate(job.request_snapshot["word_preview"])
                    provider.outcomes.append(multi_page_preview_result(policy, page_count))
                    result = execution.execute_job(job.id)
                    pages = sorted(self._files(runtime, job.id, "word_preview_page"), key=lambda file: file.original_filename)
                    target = pages[-1]
                    if failure == "expired":
                        runtime.document_file_repository.update_document_file(target.id, expires_at=utc_now() - timedelta(seconds=1))
                    elif failure == "corrupt":
                        runtime.file_upload_service.resolve_local_object_path(target.object_key).write_bytes(b"broken")
                    original_read = runtime.file_upload_service.read_file_content

                    def read_record(record):
                        if failure == "unknown" and record.id == target.id:
                            raise PermissionError(13, "PRIVATE_STORAGE_CANARY", "/private/preview/internal.png")
                        return original_read(record)

                    from app.domains.document_jobs.preview import observe_current_preview
                    with patch.object(runtime.file_upload_service, "read_file_content", side_effect=read_record) as read, patch(
                        "app.domains.document_jobs.preview.observe_current_preview", wraps=observe_current_preview,
                    ) as observe, patch("app.services.preview.models.png_dimensions", wraps=png_dimensions) as decode:
                        response = client.get(f"/api/v1/document-jobs/{job.id}/files", headers=headers)
                    self.assertEqual(response.status_code, 200, response.json())
                    self.assertFalse(any(file["file_type"].startswith("word_preview_") for file in response.json()["files"]))
                    self.assertIn(result.result_file_id, {file["id"] for file in response.json()["files"]})
                    self.assertEqual(observe.call_count, 1)
                    self.assertLessEqual(read.call_count, page_count + 3)
                    self.assertEqual(decode.call_count, 0)
                    self.assertNotIn("PRIVATE_STORAGE_CANARY", response.text)
                    self.assertNotIn("/private/preview", response.text)

    def test_file_list_compares_full_verified_record_with_list_snapshot(self):
        with self.runtime(pages=True) as (runtime, execution, provider, job, user, client, headers):
            result = execution.execute_job(job.id)
            files = runtime.document_file_repository.list_document_files()
            target = next(file for file in files if file.job_id == job.id and file.file_type == "word_preview_pdf")
            snapshot = [file.model_copy(update={"updated_at": file.updated_at + timedelta(seconds=1)}) if file.id == target.id else file for file in files]
            with patch.object(runtime.document_file_repository, "list_document_files", return_value=snapshot):
                response = client.get(f"/api/v1/document-jobs/{job.id}/files", headers=headers)
            self.assertEqual(response.status_code, 200, response.json())
            listed = {file["id"] for file in response.json()["files"]}
            self.assertNotIn(target.id, listed)
            self.assertIn(result.result_file_id, listed)
            # 单件入口重新观测真实Record，不能沿用前次列表快照。
            self.assertEqual(runtime.document_job_service.get_file_for_download(job.id, user=user, file_id=target.id)[1], target)

    def test_preview_storage_errors_are_safe_in_public_job_and_evidence_projections(self):
        cases = [("generated_word", "source_metadata"), ("generated_word", "source_read")]
        cases.extend((file_type, point) for file_type in ("word_preview_pdf", "word_preview_page", "word_preview_manifest")
                     for point in ("insert", "object", "confirm", "metadata_read", "object_read"))
        canary, private_path = "STORAGE_PRIVATE_CANARY_504", "/private/rnd504/internal-preview.pdf"
        for file_type, point in cases:
            with self.subTest(file_type=file_type, point=point), self.runtime(pages=True) as (
                runtime, execution, provider, job, user, client, headers,
            ):
                files, service = runtime.document_file_repository, runtime.file_upload_service
                get, create, write, update, read = files.get_document_file, files.create_document_file, service._write_object, files.update_document_file, service.read_file_content
                source = execution.word_preview_service._source

                def storage_error():
                    return PermissionError(13, "Permission denied " + canary, private_path)

                def source_failure(*args):
                    target = "get_document_file" if point == "source_metadata" else "read_file_content"
                    owner = files if point == "source_metadata" else service
                    with patch.object(owner, target, side_effect=storage_error()):
                        return source(*args)

                def get_record(file_id):
                    record = get(file_id)
                    if point == "metadata_read" and record is not None and record.file_type == file_type:
                        raise storage_error()
                    return record

                def insert(record):
                    if point == "insert" and record.file_type == file_type:
                        raise storage_error()
                    return create(record)

                def write_record(record, content):
                    if point == "object" and record.file_type == file_type:
                        raise storage_error()
                    return write(record, content)

                def confirm(file_id, **changes):
                    if point == "confirm" and get(file_id).file_type == file_type and changes.get("status") == "uploaded":
                        raise storage_error()
                    return update(file_id, **changes)

                def read_record(record):
                    if point == "object_read" and record.file_type == file_type:
                        raise storage_error()
                    return read(record)

                with patch.object(execution.word_preview_service, "_source", side_effect=source_failure if point.startswith("source_") else source), patch.object(
                    files, "get_document_file", side_effect=get_record,
                ), patch.object(files, "create_document_file", side_effect=insert), patch.object(service, "_write_object", side_effect=write_record), patch.object(
                    files, "update_document_file", side_effect=confirm,
                ), patch.object(service, "read_file_content", side_effect=read_record):
                    failed = execution.execute_job(job.id)
                self.assertEqual((failed.status, failed.failed_stage, failed.error_code), ("failed", "uploading", "oss_failed"))
                self.assertEqual(failed.error_message, "Word 预览存储失败，请稍后重试。")
                self.assertIsNotNone(failed.prepared_result)
                self.assertIsNone(failed.result_file_id)
                main = get(failed.prepared_result.file.id)
                self.assertEqual(sha256(read(main)), failed.prepared_result.file.checksum_sha256)
                if point in {"object", "confirm"}:
                    self.assertEqual(self._files(runtime, job.id, file_type)[-1].status, "pending_upload")
                    self.assertEqual(failed.word_preview_state.current_run.artifact_stage, "registering")
                detail = client.get(f"/api/v1/document-jobs/{job.id}", headers=headers)
                self.assertEqual(detail.status_code, 200, detail.json())
                projections = [detail.text, json.dumps(failed.quality_summary, ensure_ascii=False)]
                projections.extend(event.model_dump_json() for event in runtime.document_job_event_repository.list_document_job_events(job.id))
                projections.extend(event.model_dump_json() for event in runtime.audit_event_repository.list_audit_events())
                for manifest in self._files(runtime, job.id, "word_preview_manifest"):
                    projections.append(manifest.model_dump_json())
                    if service.resolve_local_object_path(manifest.object_key).exists():
                        projections.append(read(manifest).decode())
                    else:
                        self.assertEqual(manifest.status, "pending_upload")
                for serialized in projections:
                    self.assertNotIn(canary, serialized)
                    self.assertNotIn(private_path, serialized)

    def test_independent_preview_storage_errors_are_safe_and_leave_execution_unchanged(self):
        canary, private_path = "INDEPENDENT_PRIVATE_CANARY_504", "/private/rnd504/retry-preview.pdf"
        for point in ("source", "object", "confirm", "read"):
            with self.subTest(point=point), self.runtime(outcomes=[PreviewFailure("preview_input_invalid")]) as (
                runtime, execution, provider, job, user, client, headers,
            ):
                original = execution.execute_job(job.id)
                files, service = runtime.document_file_repository, runtime.file_upload_service
                source, write, update, read = execution.word_preview_service._source, service._write_object, files.update_document_file, service.read_file_content

                def error():
                    return PermissionError(13, "Permission denied " + canary, private_path)

                def source_failure(*args):
                    with patch.object(service, "read_file_content", side_effect=error()):
                        return source(*args)

                def write_record(record, content):
                    if point == "object" and record.file_type == "word_preview_pdf":
                        raise error()
                    return write(record, content)

                def confirm(file_id, **changes):
                    if point == "confirm" and files.get_document_file(file_id).file_type == "word_preview_pdf":
                        raise error()
                    return update(file_id, **changes)

                def read_record(record):
                    if point == "read" and record.file_type == "word_preview_manifest":
                        raise error()
                    return read(record)

                with patch.object(execution.word_preview_service, "_source", side_effect=source_failure if point == "source" else source), patch.object(
                    service, "_write_object", side_effect=write_record,
                ), patch.object(files, "update_document_file", side_effect=confirm), patch.object(service, "read_file_content", side_effect=read_record), self.assertRaises(OSError) as raised:
                    runtime.document_job_service.retry_word_preview(job.id, user=user, reason="安全失败", request_id=str(uuid4()))
                self.assertEqual(str(raised.exception), "Word 预览存储失败，请稍后重试。")
                self.assertEqual(raised.exception.code, "preview_storage_failed")
                current = runtime.document_job_repository.get_document_job(job.id)
                self.assertEqual((current.status, current.stage, current.result_file_id, current.prepared_result, current.timeout_at),
                                 (original.status, original.stage, original.result_file_id, original.prepared_result, original.timeout_at))
                serialized = client.get(f"/api/v1/document-jobs/{job.id}", headers=headers).text
                self.assertNotIn(canary, serialized)
                self.assertNotIn(private_path, serialized)

    def test_legacy_terminal_initial_is_confirmed_before_new_uuid_alias_or_run(self):
        for kind in ("file", "sqlite"):
            for status, outcome in (("succeeded", ()), ("failed", (PreviewFailure("preview_input_invalid"),)),
                                    ("unavailable", (PreviewFailure("preview_provider_unavailable"),))):
                with self.subTest(kind=kind, status=status), self.runtime(kind=kind, quality="passed", outcomes=outcome) as (
                    runtime, execution, provider, job, user, client, headers,
                ):
                    original = execution.execute_job(job.id)
                    self.assertEqual(original.word_preview_state.current_run.status, status)
                    legacy = original.word_preview_state.model_copy(deep=True)
                    legacy.current_run.artifact_stage, legacy.current_run.confirmed_attempt = None, None
                    runtime.document_job_repository.update_document_job(job.id, word_preview_state=legacy)
                    key = str(uuid4())
                    result = runtime.document_job_service.retry_word_preview(job.id, user=user, reason="旧终态核验", request_id=key)
                    state = result.job.word_preview_state
                    self.assertTrue(result.available)
                    self.assertEqual(result.job.prepared_result, original.prepared_result)
                    self.assertEqual(len(state.runs_by_request_key), 2)
                    initial = state.runs_by_request_key["initial"]
                    self.assertEqual((initial.run_id, initial.status, initial.attempt_count, initial.run_deadline_at),
                        (legacy.current_run.run_id, status, legacy.current_run.attempt_count, legacy.current_run.run_deadline_at))
                    self.assertEqual((initial.artifact_stage, initial.confirmed_attempt), ("confirmed", initial.attempt_count))
                    if status == "succeeded":
                        self.assertEqual(len(provider.inputs), 1)
                        self.assertEqual(result.run.run_id, initial.run_id)
                        self.assertEqual(state.current_request_key, "initial")
                        self.assertEqual(state.revision, legacy.revision + 1)
                    else:
                        self.assertEqual(len(provider.inputs), 2)
                        self.assertNotEqual(result.run.run_id, initial.run_id)
                        self.assertEqual(state.current_request_key, key)
                        self.assertEqual(state.revision, legacy.revision + 3)

    def test_legacy_running_without_stage_still_fails_closed_for_new_uuid(self):
        with self.runtime(outcomes=[PreviewFailure("preview_input_invalid")]) as (runtime, execution, provider, job, user, client, headers):
            original = execution.execute_job(job.id)
            with patch.object(execution.word_preview_service, "_event", side_effect=result_fixtures.SimulatedProcessExit), self.assertRaises(result_fixtures.SimulatedProcessExit):
                runtime.document_job_service.retry_word_preview(job.id, user=user, reason="在途旧记录", request_id=str(uuid4()))
            legacy = runtime.document_job_repository.get_document_job(job.id).word_preview_state.model_copy(deep=True)
            legacy.current_run.artifact_stage, legacy.current_run.confirmed_attempt = None, None
            runtime.document_job_repository.update_document_job(job.id, word_preview_state=legacy)
            future = legacy.current_run.lease_expires_at + timedelta(milliseconds=1)
            with patch("app.infrastructure.persistence.file.document_jobs.utc_now", return_value=future), patch("app.domains.document_jobs.preview.utc_now", return_value=future), self.assertRaises(PreviewFailure) as error:
                runtime.document_job_service.retry_word_preview(job.id, user=user, reason="不能升级在途", request_id=str(uuid4()))
            self.assertEqual(error.exception.code, "preview_storage_failed")
            current = runtime.document_job_repository.get_document_job(job.id)
            self.assertEqual((current.status, current.stage, current.result_file_id, current.prepared_result),
                             (original.status, original.stage, original.result_file_id, original.prepared_result))
            self.assertEqual(current.word_preview_state.current_run.run_deadline_at, legacy.current_run.run_deadline_at)
            self.assertEqual(len(provider.inputs), 1)
