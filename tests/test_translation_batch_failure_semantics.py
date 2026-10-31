"""验证终态失败优先于同代活动批次，并保持 API 结论与执行器一致。"""

import io
import json
import sqlite3
from pathlib import Path
import tempfile
import threading
from datetime import timedelta
from unittest import TestCase
from unittest.mock import Mock, patch
import zipfile

from fastapi.testclient import TestClient

from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.domains.document_jobs.repository import TranslationBatchTreeInvalidError
from app.domains.resources.models import utc_now
from tests import test_fastapi_jobs_backend as fixtures


def _make_public_opa228_mineru_zip_bytes() -> bytes:
    """将仓库版本化的 OPA228 最小 MinerU 包交给同一真实转换入口。"""

    source = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "component_pdf_samples"
        / "samples"
        / "texas-instruments"
        / "op-amp"
        / "ti-opamp-opa228-p1-smoke"
        / "mineru"
        / "component_content_list_v2.json"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content_list_v2.json", source.read_bytes())
    return buffer.getvalue()


class _FailOnSecondProvider:
    """首个批次成功，第二个真实调用失败，用于构造部分失败窗口。"""

    def __init__(self) -> None:
        self.delegate = fixtures.FakeDocumentJobTranslationProvider()
        self.calls = 0

    def translate(self, request):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("provider unavailable")
        return self.delegate.translate(request)


class _RunningSiblingProvider:
    """首个批次保持真实外调，第二个批次失败，用于验证终态不等待兄弟。"""

    def __init__(self) -> None:
        self.delegate = fixtures.FakeDocumentJobTranslationProvider()
        self.calls = 0
        self.first_started = threading.Event()
        self.release_first = threading.Event()

    def translate(self, request):
        self.calls += 1
        if self.calls == 1:
            self.first_started.set()
            self.release_first.wait(timeout=5)
            return self.delegate.translate(request)
        raise RuntimeError("provider unavailable")


class TranslationBatchFailureSemanticsTests(TestCase):
    def test_budget_preflight_failure_does_not_return_failed_batch_as_claim(self) -> None:
        """已安装批次的预算预检失败必须停在批次终态，不能把失败记录送入 Provider。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = fixtures.FakeDocumentJobTranslationProvider()
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.translation_batch_task_queue = Mock()
            source_file = runtime.file_upload_service.register_generated_content(
                tenant_id="tenant",
                company_id="company",
                job_id="job_budget_preflight",
                created_by="operator",
                file_type="source_pdf",
                filename="source.pdf",
                mime_type="application/pdf",
                content=b"source-pdf",
            )
            job = runtime.document_job_repository.create_document_job(DocumentJobRecord(
                id="job_budget_preflight",
                tenant_id="tenant",
                company_id="company",
                created_by="operator",
                source_file_id=source_file.id,
                mode="en2zh_pdf_to_word",
                document_language="en",
                status="running",
                stage="ir_converting",
                template_version_id=execution.template_read_service.resolve_template_version(None).template_version_id,
            ))
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(
                    "content_list_v2.json",
                    json.dumps([
                        {"type": "text", "text": "A" * 49, "page_idx": 0},
                        {"type": "text", "text": "B" * 26, "page_idx": 0},
                    ]),
                )
            raw = runtime.file_upload_service.register_generated_content(
                tenant_id=job.tenant_id,
                company_id=job.company_id,
                job_id=job.id,
                created_by=job.created_by,
                file_type="mineru_raw_result",
                filename="mineru.zip",
                mime_type="application/zip",
                content=buffer.getvalue(),
            )
            zip_path = Path(temp_dir) / "source.zip"
            zip_path.write_bytes(buffer.getvalue())
            document = execution.document_ir_service.convert_zip(
                zip_path,
                job_id=job.id,
                source_file_id=job.source_file_id,
                document_language="en",
            ).document
            job = execution._register_source_ir_and_enqueue_translation(
                job,
                raw_file=raw,
                document_ir=document,
                image_file_ids=[],
                image_archive_file=None,
                trace_id="trace_budget_preflight",
            )
            batch = runtime.document_job_translation_batch_repository.list_translation_batches(job.id)[0]
            execution.settings.translation_max_chars = 26

            claimed = execution._claim_translation_batch(batch, trace_id="trace_budget_preflight")

            current_job = runtime.document_job_repository.get_document_job(job.id)
            current_batch = runtime.document_job_translation_batch_repository.get_translation_batch(batch.id)
            self.assertIsNone(claimed)
            self.assertEqual(
                (current_job.status, current_job.stage, current_job.error_code),
                ("failed", "failed", "translation_failed"),
            )
            self.assertEqual(
                (current_batch.status, current_batch.attempt_count, current_batch.lease_owner),
                ("failed", 0, None),
            )
            self.assertEqual(provider.requests, [])

    def test_old_generation_tree_error_cannot_fail_new_generation(self) -> None:
        """旧代树校验异常与换代交错时，只观察旧消息，不能击穿新代。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = fixtures.FakeDocumentJobTranslationProvider()
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"], "mode": "en2zh_pdf_to_word", "document_language": "en"},
                )
            job_id = created.json()["job_id"]
            batch = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)[0]
            repository = runtime.document_job_translation_batch_repository

            def stale_claim(*_args, **_kwargs):
                runtime.document_job_repository.update_document_job(
                    job_id, retry_count=1, status="running", stage="ir_converting",
                )
                raise TranslationBatchTreeInvalidError("旧代计划已失效")

            with patch.object(repository, "claim_translation_batch", side_effect=stale_claim):
                execution.execute_translation_batch(batch.id, trace_id="trace_old_tree_error")

            current = runtime.document_job_repository.get_document_job(job_id)
            self.assertEqual((current.retry_count, current.status, current.stage), (1, "running", "ir_converting"))
            self.assertIsNone(current.error_code)

    def test_direct_translation_batch_projection_has_null_execution(self) -> None:
        """direct 任务不读取翻译资源，也不伪造批次执行摘要。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            execution = runtime.document_job_execution_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={"source_file_id": source_file["id"], "document_language": "en"},
                )
                self.assertEqual(created.status_code, 201, created.json())
                response = client.get(
                    f"/api/v1/document-jobs/{created.json()['job_id']}/translation-batches",
                    headers=headers,
                )

            self.assertEqual(response.status_code, 200, response.json())
            self.assertEqual(response.json()["items"], [])
            self.assertIsNone(response.json()["execution"])

    def test_translation_batch_api_snapshot_does_not_mix_old_generation_after_retry(self) -> None:
        """鉴权读取与锁内 snapshot 之间换代时，响应必须只投影返回 job 的当前代。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            runtime.settings.translation_provider_batch_max_attempts = 1
            provider = _FailOnSecondProvider()
            runtime.document_ir_translation_service = DocumentIRTranslationService(
                provider,
                max_items_per_request=3,
                max_chars_per_request=10_000,
            )
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )
                self.assertEqual(created.status_code, 201, created.json())
                job_id = created.json()["job_id"]
                initial_batches = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)
                execution.execute_translation_batch(initial_batches[0].id, trace_id="trace_retry_snapshot")
                execution.execute_translation_batch(initial_batches[1].id, trace_id="trace_retry_snapshot")
                old_job = runtime.document_job_repository.get_document_job(job_id)
                old_batches = runtime.document_job_translation_batch_repository.list_translation_batches(
                    job_id, generation=old_job.retry_count,
                )
                self.assertTrue(old_batches)

                runtime.document_job_service.task_queue = Mock()
                retried = client.post(
                    f"/api/v1/document-jobs/{job_id}/retry",
                    headers=headers,
                    json={"reason": "重建当前代测试"},
                )
                self.assertEqual(retried.status_code, 200, retried.json())
                execution.execute_job(job_id, trace_id="trace_retry_snapshot")
                new_job = runtime.document_job_repository.get_document_job(job_id)
                self.assertEqual(new_job.retry_count, old_job.retry_count + 1)
                new_batches = runtime.document_job_translation_batch_repository.list_translation_batches(
                    job_id, generation=new_job.retry_count,
                )
                self.assertTrue(new_batches)
                self.assertEqual(
                    {batch.source_document_ir_file_id for batch in new_batches},
                    {batch.source_document_ir_file_id for batch in old_batches},
                )
                self.assertTrue(
                    {batch.id for batch in new_batches}.isdisjoint({batch.id for batch in old_batches})
                )
                self.assertTrue(all(batch.result_file_id is None for batch in new_batches))
                execution.execute_translation_batch(old_batches[0].id, trace_id="trace_old_generation_replay")
                self.assertEqual(provider.calls, 2)
                self.assertEqual(
                    runtime.document_job_translation_batch_repository.list_translation_batches(
                        job_id, generation=new_job.retry_count,
                    ),
                    new_batches,
                )

                # 模拟鉴权读取发生在 retry 前，随后 snapshot 在锁内读到新代。
                with patch.object(runtime.document_job_service, "get_job", return_value=old_job):
                    response = client.get(
                        f"/api/v1/document-jobs/{job_id}/translation-batches",
                        headers=headers,
                    )

            self.assertEqual(response.status_code, 200, response.json())
            payload = response.json()
            self.assertEqual(payload["generation"], new_job.retry_count)
            self.assertTrue(payload["items"])
            self.assertTrue(all(item["generation"] == new_job.retry_count for item in payload["items"]))
            self.assertIsNotNone(payload["execution"])
            self.assertNotEqual(payload["execution"]["outcome"], "failed")

    def test_all_translation_directions_fail_before_target_ir_or_docx(self) -> None:
        """四个跨语言方向的真实执行失败都停在 translating，并不晋升目标件。"""

        for mode, language in (("en2zh", "en"), ("ru2zh", "ru"), ("zh2en", "zh"), ("zh2ru", "zh")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp_dir:
                runtime = fixtures.build_test_runtime(
                    Path(temp_dir),
                    jobs_artifact_storage_backend="local_object",
                    auth_jwt_secret_key="test-jwt-secret",
                    auth_internal_users_json=fixtures.build_auth_users_json(),
                    document_jobs_worker_backend="eager",
                )
                provider = fixtures.FakeDocumentJobTranslationProvider(raise_error=True)
                runtime.settings.translation_provider_batch_max_attempts = 1
                runtime.document_ir_translation_service = DocumentIRTranslationService(
                    provider, max_items_per_request=100, max_chars_per_request=10_000,
                )
                execution = runtime.document_job_execution_service
                execution.document_ir_translation_service = runtime.document_ir_translation_service
                execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()

                with TestClient(fixtures.create_app(runtime)) as client:
                    headers = fixtures.build_auth_header(client)
                    source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                    created = client.post(
                        "/api/v1/document-jobs",
                        headers=headers,
                        json={
                            "source_file_id": source_file["id"],
                            "translation_mode": mode,
                            "document_language": language,
                        },
                    )
                self.assertEqual(created.status_code, 201, created.json())
                job = runtime.document_job_repository.get_document_job(created.json()["job_id"])
                self.assertEqual((job.status, job.stage, job.failed_stage), ("failed", "failed", "translating"))
                self.assertIsNone(job.document_ir_file_id)
                self.assertIsNone(job.result_file_id)
                self.assertTrue(provider.requests)
                self.assertFalse(
                    any(
                        file.file_type == "generated_word"
                        for file in runtime.document_file_repository.list_document_files()
                        if file.job_id == job.id
                    )
                )

    def test_public_opa228_fixture_runs_converter_batch_fanin_and_renderer(self) -> None:
        """公开 OPA228 最小包必须经过真实转换、批次汇聚和 Word 渲染。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = fixtures.FakeDocumentJobTranslationProvider()
            runtime.document_ir_translation_service = DocumentIRTranslationService(
                provider, max_items_per_request=2, max_chars_per_request=10_000,
            )
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = _make_public_opa228_mineru_zip_bytes()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(
                    client, headers, filename="OPA228_P1.pdf",
                )
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )

            job = runtime.document_job_repository.get_document_job(created.json()["job_id"])
            self.assertEqual(created.status_code, 201, created.json())
            self.assertEqual((job.status, job.stage), ("succeeded", "completed"))
            ir_file = runtime.document_file_repository.get_document_file(job.document_ir_file_id)
            word_file = runtime.document_file_repository.get_document_file(job.result_file_id)
            ir_payload = json.loads(runtime.file_upload_service.read_file_content(ir_file).decode("utf-8"))
            word_bytes = runtime.file_upload_service.read_file_content(word_file)

        self.assertIn("OPA228", json.dumps(ir_payload, ensure_ascii=False))
        self.assertIn("10 V/us", json.dumps(ir_payload, ensure_ascii=False))
        with zipfile.ZipFile(io.BytesIO(word_bytes)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("OPA228", document_xml)
        self.assertIn("10 V/us", document_xml)

    def test_synthetic_table_units_fanin_success_and_failure_never_publish_partial_target(self) -> None:
        """表格、单位和多 item 批次成功可渲染；任一真实 Provider 失败则不发布目标件。"""

        for raise_error in (False, True):
            with self.subTest(raise_error=raise_error), tempfile.TemporaryDirectory() as temp_dir:
                runtime = fixtures.build_test_runtime(
                    Path(temp_dir),
                    jobs_artifact_storage_backend="local_object",
                    auth_jwt_secret_key="test-jwt-secret",
                    auth_internal_users_json=fixtures.build_auth_users_json(),
                    document_jobs_worker_backend="eager",
                )
                provider = fixtures.FakeDocumentJobTranslationProvider(raise_error=raise_error)
                runtime.settings.translation_provider_batch_max_attempts = 1
                runtime.document_ir_translation_service = DocumentIRTranslationService(
                    provider, max_items_per_request=2, max_chars_per_request=10_000,
                )
                execution = runtime.document_job_execution_service
                execution.document_ir_translation_service = runtime.document_ir_translation_service
                source = io.BytesIO(fixtures.make_semantic_mineru_zip_bytes())
                protected = io.BytesIO()
                # 此用例验证批次成功/失败；为源表格公式给出原 Codec 已支持的完整边界。
                with zipfile.ZipFile(source) as archive, zipfile.ZipFile(protected, "w") as output:
                    for name in archive.namelist():
                        content = archive.read(name)
                        if name == "content_list_v2.json":
                            blocks = json.loads(content)
                            for block in blocks:
                                if block["type"] == "table":
                                    block["table_body"] = block["table_body"].replace(r"nV/ \sqrt{Hz}", r"\(nV/ \sqrt{Hz}\)")
                            content = json.dumps(blocks, ensure_ascii=False).encode("utf-8")
                        output.writestr(name, content)
                execution.fake_mineru_client.result_zip_bytes = protected.getvalue()

                with TestClient(fixtures.create_app(runtime)) as client:
                    headers = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                    source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(
                        client, headers, filename="synthetic-table.pdf",
                    )
                    created = client.post(
                        "/api/v1/document-jobs",
                        headers=headers,
                        json={
                            "source_file_id": source_file["id"],
                            "mode": "en2zh_pdf_to_word",
                            "document_language": "en",
                        },
                    )

                job = runtime.document_job_repository.get_document_job(created.json()["job_id"])
                self.assertEqual(created.status_code, 201, created.json())
                self.assertTrue(provider.requests)
                if raise_error:
                    self.assertEqual((job.status, job.stage), ("failed", "failed"))
                    self.assertIsNone(job.document_ir_file_id)
                    self.assertIsNone(job.result_file_id)
                    self.assertFalse(
                        any(
                            file.file_type == "generated_word" and file.job_id == job.id
                            for file in runtime.document_file_repository.list_document_files()
                        )
                    )
                    continue

                self.assertEqual((job.status, job.stage), ("succeeded", "completed"))
                ir_file = runtime.document_file_repository.get_document_file(job.document_ir_file_id)
                word_file = runtime.document_file_repository.get_document_file(job.result_file_id)
                ir_payload = json.loads(runtime.file_upload_service.read_file_content(ir_file).decode("utf-8"))
                word_bytes = runtime.file_upload_service.read_file_content(word_file)
                self.assertIn("table", [block["type"] for block in ir_payload["blocks"]])
                self.assertIn("R", json.dumps(ir_payload, ensure_ascii=False))
                self.assertIn("nV", json.dumps(ir_payload, ensure_ascii=False))
                with zipfile.ZipFile(io.BytesIO(word_bytes)) as archive:
                    document_xml = archive.read("word/document.xml").decode("utf-8")
                self.assertIn("<w:tbl>", document_xml)
                self.assertIn("nV", document_xml)

    def test_terminal_failure_marks_job_before_running_sibling_returns(self) -> None:
        """活动兄弟尚未返回时，终态失败已生效且不生成目标 IR/DOCX。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = _RunningSiblingProvider()
            runtime.settings.translation_provider_batch_max_attempts = 1
            runtime.document_ir_translation_service = DocumentIRTranslationService(
                provider, max_items_per_request=3, max_chars_per_request=10_000,
            )
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "translation_mode": "en2zh",
                        "document_language": "en",
                    },
                )
                self.assertEqual(created.status_code, 201, created.json())
                job_id = created.json()["job_id"]
                batches = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)
                first, second = batches[:2]

                worker = threading.Thread(
                    target=execution.execute_translation_batch,
                    args=(first.id,),
                    kwargs={"trace_id": "trace_running_sibling"},
                )
                worker.start()
                self.assertTrue(provider.first_started.wait(timeout=5))
                execution.execute_translation_batch(second.id, trace_id="trace_running_sibling")
                failed_while_first_running = runtime.document_job_repository.get_document_job(job_id)
                self.assertEqual(
                    (failed_while_first_running.status, failed_while_first_running.stage),
                    ("failed", "failed"),
                )
                self.assertIsNone(failed_while_first_running.document_ir_file_id)
                provider.release_first.set()
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive())

            final_job = runtime.document_job_repository.get_document_job(job_id)
            self.assertEqual(final_job.status, "failed")
            self.assertEqual(provider.calls, 2)
            self.assertFalse(
                any(
                    file.file_type == "generated_word" and file.job_id == job_id
                    for file in runtime.document_file_repository.list_document_files()
                )
            )

    def test_partial_root_installation_fails_closed_without_repair_or_provider_call(self) -> None:
        """部分根安装被消费时立即失败，不能补根、调用 Provider 或晋升目标件。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = fixtures.FakeDocumentJobTranslationProvider()
            runtime.document_ir_translation_service = DocumentIRTranslationService(
                provider, max_items_per_request=3, max_chars_per_request=10_000,
            )
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "translation_mode": "en2zh",
                        "document_language": "en",
                    },
                )
                self.assertEqual(created.status_code, 201, created.json())
                job_id = created.json()["job_id"]

            job = runtime.document_job_repository.get_document_job(job_id)
            batches_before = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)
            self.assertGreaterEqual(len(batches_before), 2)
            repository = runtime.document_job_translation_batch_repository
            missing_path = repository.backend.document_job_translation_batches_dir / f"{batches_before[0].id}.json"
            missing_path.unlink()
            execution.execute_job(job_id, trace_id="trace_partial_root")

            failed = runtime.document_job_repository.get_document_job(job_id)
            self.assertEqual((failed.status, failed.stage, failed.error_code), (
                "failed", "failed", "translation_batch_tree_invalid",
            ))
            batches_after = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)
            self.assertEqual({batch.id for batch in batches_after}, {batch.id for batch in batches_before[1:]})
            self.assertEqual(provider.requests, [])
            self.assertIsNone(failed.document_ir_file_id)
            self.assertIsNone(failed.result_file_id)
            execution.execute_translation_batch(batches_after[0].id, trace_id="trace_partial_root_replay")
            self.assertEqual(provider.requests, [])

    def test_same_batch_claim_competition_has_one_provider_call_without_false_failure(self) -> None:
        """同一 batch 的普通 claim 竞争只允许一个 Provider 调用，不误报任务失败。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = _RunningSiblingProvider()
            runtime.document_ir_translation_service = DocumentIRTranslationService(
                provider, max_items_per_request=3, max_chars_per_request=10_000,
            )
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "translation_mode": "en2zh",
                        "document_language": "en",
                    },
                )
                self.assertEqual(created.status_code, 201, created.json())
                job_id = created.json()["job_id"]
                batch = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)[0]
                first = threading.Thread(target=execution.execute_translation_batch, args=(batch.id,))
                first.start()
                self.assertTrue(provider.first_started.wait(timeout=5))
                second = threading.Thread(target=execution.execute_translation_batch, args=(batch.id,))
                second.start()
                second.join(timeout=5)
                self.assertFalse(second.is_alive())
                provider.release_first.set()
                first.join(timeout=5)
                self.assertFalse(first.is_alive())

            job = runtime.document_job_repository.get_document_job(job_id)
            self.assertEqual((job.status, job.stage), ("running", "translating"))
            self.assertEqual(provider.calls, 1)
            self.assertEqual(
                runtime.document_job_translation_batch_repository.get_translation_batch(batch.id).status,
                "succeeded",
            )

    def test_terminal_leaf_stops_queued_sibling_and_replay_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = _FailOnSecondProvider()
            runtime.document_ir_translation_service = DocumentIRTranslationService(
                provider,
                max_items_per_request=3,
                max_chars_per_request=10_000,
            )
            execution = runtime.document_job_execution_service
            runtime.settings.translation_provider_batch_max_attempts = 1
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )
                self.assertEqual(created.status_code, 201, created.json())
                job_id = created.json()["job_id"]
                batches = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)
                self.assertGreaterEqual(len(batches), 3)

                first = batches[0]
                second = batches[1]
                execution.execute_translation_batch(first.id, trace_id="trace_partial")
                execution.execute_translation_batch(second.id, trace_id="trace_partial")

                failed_job = runtime.document_job_repository.get_document_job(job_id)
                self.assertIsNotNone(failed_job)
                self.assertEqual(
                    (failed_job.status, failed_job.stage, failed_job.failed_stage, failed_job.error_code),
                    ("failed", "failed", "translating", "translation_failed"),
                )
                self.assertIsNone(failed_job.document_ir_file_id)
                self.assertEqual(provider.calls, 2)

                queued_sibling = runtime.document_job_translation_batch_repository.get_translation_batch(batches[2].id)
                self.assertEqual(queued_sibling.status, "queued")
                events_before = runtime.document_job_event_repository.list_document_job_events(job_id)
                failed_events_before = [event for event in events_before if event.event_type == "stage_failed"]
                execution.execute_translation_batch(queued_sibling.id, trace_id="trace_replay")
                events_after = runtime.document_job_event_repository.list_document_job_events(job_id)
                self.assertEqual(provider.calls, 2)
                self.assertEqual(
                    len([event for event in events_after if event.event_type == "stage_failed"]),
                    len(failed_events_before),
                )
                partial_result = runtime.document_job_translation_batch_repository.get_translation_batch(first.id)
                self.assertIsNotNone(partial_result.result_file_id)
                partial_download = client.get(
                    f"/api/v1/document-jobs/{job_id}/download-url",
                    headers=headers,
                    params={"file_id": partial_result.result_file_id},
                )
                qa_response = client.get(
                    f"/api/v1/document-jobs/{job_id}/translation-qa",
                    headers=headers,
                )

                response = client.get(
                    f"/api/v1/document-jobs/{job_id}/translation-batches",
                    headers=headers,
                )

            self.assertEqual(response.status_code, 200, response.json())
            payload = response.json()
            self.assertEqual(payload["execution"]["outcome"], "failed")
            self.assertEqual(partial_download.status_code, 409, partial_download.json())
            self.assertEqual(qa_response.status_code, 200, qa_response.json())
            self.assertNotIn(partial_result.result_file_id, json.dumps(qa_response.json(), ensure_ascii=False))
            rows = {item["batch_id"]: item for item in payload["items"]}
            self.assertEqual(rows[second.id]["failure_disposition"], "terminal")
            self.assertEqual(rows[batches[2].id]["failure_disposition"], "stopped")
            self.assertFalse(
                any(
                    file.file_type == "generated_word"
                    for file in runtime.document_file_repository.list_document_files()
                )
            )

    def test_expired_claim_is_released_then_reclaimed_with_new_attempt_and_lease(self) -> None:
        """真实 claim/release/reclaim 链路必须递增 attempt，并拒绝旧 lease 回流。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            runtime.settings.translation_provider_batch_max_attempts = 2
            runtime.document_ir_translation_service = DocumentIRTranslationService(
                fixtures.FakeDocumentJobTranslationProvider(),
                max_items_per_request=3,
                max_chars_per_request=10_000,
            )
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )
                self.assertEqual(created.status_code, 201, created.json())
                job_id = created.json()["job_id"]

            job = runtime.document_job_repository.get_document_job(job_id)
            self.assertIsNotNone(job)
            batch = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)[0]
            claimed = execution._claim_translation_batch(batch, trace_id="trace_lease")
            self.assertIsNotNone(claimed)
            self.assertEqual(claimed.attempt_count, 1)
            self.assertTrue(claimed.lease_owner)

            _source_file, source_ir = execution._read_translation_source(job, batch.source_document_ir_file_id)
            expected_plans = execution._build_expected_translation_plans(job, source_ir)
            expired = runtime.document_job_translation_batch_repository.release_translation_batch_lease(
                claimed.id,
                expected_generation=claimed.generation,
                expected_attempt_count=claimed.attempt_count,
                expected_lease_owner=claimed.lease_owner or "",
                now=(claimed.lease_expires_at or claimed.leased_at) + timedelta(seconds=1),
                expected_plans=expected_plans,
                error_code="translation_batch_lease_expired",
                error_message="翻译批次租约已过期，等待重新投递。",
                retryable=True,
                updated_at=(claimed.lease_expires_at or claimed.leased_at) + timedelta(seconds=1),
            )
            self.assertIsNotNone(expired)
            self.assertEqual(expired.status, "failed")
            self.assertTrue(expired.retryable)

            reclaimed = execution._claim_translation_batch(expired, trace_id="trace_reclaim")
            self.assertIsNotNone(reclaimed)
            self.assertEqual(reclaimed.attempt_count, 2)
            self.assertTrue(reclaimed.lease_owner)
            self.assertNotEqual(reclaimed.lease_owner, claimed.lease_owner)

            stale_write = runtime.document_job_translation_batch_repository.update_translation_batch_if_current(
                reclaimed.id,
                allowed_statuses={"running"},
                expected_generation=claimed.generation,
                expected_attempt_count=claimed.attempt_count,
                expected_lease_owner=claimed.lease_owner,
                expected_plans=expected_plans,
                status="succeeded",
                updated_at=reclaimed.updated_at,
            )
            self.assertIsNone(stale_write)

    def test_claim_none_after_summary_passed_reconciles_terminal_batch(self) -> None:
        """summary 通过后 claim 被并发终结时，拒绝本次 Provider 并收口任务。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = fixtures.FakeDocumentJobTranslationProvider()
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )

            job_id = created.json()["job_id"]
            repository = runtime.document_job_translation_batch_repository
            batch = repository.list_translation_batches(job_id)[0]
            real_claim = repository.claim_translation_batch
            real_update = repository.update_translation_batch_if_current
            rejected = False

            def claim_then_terminal(*args, **kwargs):
                nonlocal rejected
                current = repository.get_translation_batch(batch.id)
                if not rejected:
                    rejected = True
                    real_update(
                        current.id,
                        allowed_statuses={current.status},
                        expected_generation=current.generation,
                        expected_attempt_count=current.attempt_count,
                        expected_lease_owner=current.lease_owner,
                        expected_plans=kwargs["expected_plans"],
                        status="failed",
                        error_code="translation_failed",
                        error_message="并发终态已确认。",
                        retryable=False,
                        updated_at=utc_now(),
                    )
                    return None
                return real_claim(*args, **kwargs)

            with patch.object(repository, "claim_translation_batch", side_effect=claim_then_terminal):
                result = execution.execute_translation_batch(batch.id, trace_id="trace_claim_none_terminal")

            failed_job = runtime.document_job_repository.get_document_job(job_id)
            self.assertTrue(rejected)
            self.assertIsNone(result)
            self.assertEqual((failed_job.status, failed_job.stage), ("failed", "failed"))
            self.assertEqual(provider.requests, [])
            self.assertIsNone(failed_job.document_ir_file_id)
            self.assertIsNone(failed_job.result_file_id)

    def test_success_and_failure_none_rejections_reconcile_without_repeating_provider_or_terminal_event(self) -> None:
        """结果 CAS 被并发终结时，成功审计只保留一次，失败重放也不重复终态事件。"""

        for raise_error in (False, True):
            with self.subTest(raise_error=raise_error), tempfile.TemporaryDirectory() as temp_dir:
                runtime = fixtures.build_test_runtime(
                    Path(temp_dir),
                    jobs_artifact_storage_backend="local_object",
                    auth_jwt_secret_key="test-jwt-secret",
                    auth_internal_users_json=fixtures.build_auth_users_json(),
                    document_jobs_worker_backend="eager",
                )
                provider = fixtures.FakeDocumentJobTranslationProvider(raise_error=raise_error)
                runtime.settings.translation_provider_batch_max_attempts = 1
                runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
                execution = runtime.document_job_execution_service
                execution.document_ir_translation_service = runtime.document_ir_translation_service
                execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
                execution.translation_batch_task_queue = Mock()

                with TestClient(fixtures.create_app(runtime)) as client:
                    headers = fixtures.build_auth_header(client)
                    source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                    created = client.post(
                        "/api/v1/document-jobs",
                        headers=headers,
                        json={
                            "source_file_id": source_file["id"],
                            "mode": "en2zh_pdf_to_word",
                            "document_language": "en",
                        },
                    )

                job_id = created.json()["job_id"]
                repository = runtime.document_job_translation_batch_repository
                batch = repository.list_translation_batches(job_id)[0]
                real_update = repository.update_translation_batch_if_current
                rejected = False

                def update_then_terminal(*args, **kwargs):
                    nonlocal rejected
                    if not rejected and kwargs.get("status") in {"succeeded", "failed"}:
                        rejected = True
                        concurrent = dict(kwargs)
                        concurrent["status"] = "failed"
                        concurrent["result_file_id"] = None
                        concurrent["error_code"] = "translation_failed"
                        concurrent["error_message"] = "并发终态已确认。"
                        concurrent["retryable"] = False
                        real_update(*args, **concurrent)
                        return None
                    return real_update(*args, **kwargs)

                with patch.object(repository, "update_translation_batch_if_current", side_effect=update_then_terminal):
                    execution.execute_translation_batch(batch.id, trace_id="trace_result_none_terminal")

                failed_job = runtime.document_job_repository.get_document_job(job_id)
                events_before = runtime.document_job_event_repository.list_document_job_events(job_id)
                terminal_count_before = len([
                    event for event in events_before
                    if event.event_type in {"stage_failed", "translation_batch_failed"}
                ])
                execution.execute_translation_batch(batch.id, trace_id="trace_result_none_replay")
                events_after = runtime.document_job_event_repository.list_document_job_events(job_id)

                self.assertTrue(rejected)
                self.assertEqual((failed_job.status, failed_job.stage), ("failed", "failed"))
                self.assertEqual(len(provider.requests), 1)
                self.assertIsNone(failed_job.document_ir_file_id)
                self.assertIsNone(failed_job.result_file_id)
                self.assertEqual(
                    len([
                        event for event in events_after
                        if event.event_type in {"stage_failed", "translation_batch_failed"}
                    ]),
                    terminal_count_before,
                )
                audit_files = [
                    file for file in runtime.document_file_repository.list_document_files()
                    if file.job_id == job_id and file.file_type == "ai_call_log"
                ]
                self.assertEqual(len(audit_files), 1)

    def test_batch_result_storage_io_failure_is_oss_failed_without_provider_retry(self) -> None:
        """成功 Provider 的结果 Artifact 写入失败映射 oss_failed，不能再次调用 Provider。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = fixtures.FakeDocumentJobTranslationProvider()
            runtime.settings.translation_provider_batch_max_attempts = 1
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )

            job_id = created.json()["job_id"]
            repository = runtime.document_job_translation_batch_repository
            batch = repository.list_translation_batches(job_id)[0]
            real_register = runtime.file_upload_service.register_generated_content

            def fail_batch_result_write(**kwargs):
                if kwargs.get("file_type") == "translation_batch_result":
                    raise OSError("/private/storage/path unavailable")
                return real_register(**kwargs)

            with patch.object(
                runtime.file_upload_service,
                "register_generated_content",
                side_effect=fail_batch_result_write,
            ):
                execution.execute_translation_batch(batch.id, trace_id="trace_artifact_io")

            failed_job = runtime.document_job_repository.get_document_job(job_id)
            files = [
                file for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id
            ]
            audit_files = [file for file in files if file.file_type == "ai_call_log"]
            self.assertEqual(len(provider.requests), 1)
            self.assertEqual(len(audit_files), 1)
            self.assertEqual(
                (failed_job.status, failed_job.stage, failed_job.failed_stage, failed_job.error_code),
                ("failed", "failed", "translating", "oss_failed"),
            )
            self.assertIsNone(failed_job.document_ir_file_id)
            self.assertIsNone(failed_job.result_file_id)
            self.assertNotIn("/private/storage/path", json.dumps(files, default=str, ensure_ascii=False))

    def test_batch_result_repository_sqlite_failure_is_oss_failed_without_provider_retry(self) -> None:
        """结果 Artifact 的 SQLite 元数据写入失败必须收口为 oss_failed。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = fixtures.FakeDocumentJobTranslationProvider()
            runtime.settings.translation_provider_batch_max_attempts = 1
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )

            job_id = created.json()["job_id"]
            batch = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)[0]
            real_create = runtime.document_file_repository.create_document_file

            def fail_result_metadata_write(record):
                if record.file_type == "translation_batch_result":
                    raise sqlite3.OperationalError("database is locked")
                return real_create(record)

            with patch.object(
                runtime.document_file_repository,
                "create_document_file",
                side_effect=fail_result_metadata_write,
            ):
                execution.execute_translation_batch(batch.id, trace_id="trace_result_sqlite")

            failed_job = runtime.document_job_repository.get_document_job(job_id)
            files = [
                file for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id
            ]
            audit_files = [file for file in files if file.file_type == "ai_call_log"]
            self.assertEqual(len(provider.requests), 1)
            self.assertEqual(len(audit_files), 1)
            self.assertEqual(
                (failed_job.status, failed_job.stage, failed_job.failed_stage, failed_job.error_code),
                ("failed", "failed", "translating", "oss_failed"),
            )
            self.assertIsNone(failed_job.document_ir_file_id)
            self.assertIsNone(failed_job.result_file_id)
            self.assertFalse(any(file.file_type == "translation_batch_result" for file in files))

    def test_batch_success_cas_storage_io_failure_is_oss_failed_without_provider_retry(self) -> None:
        """批次成功 CAS 的仓储 I/O 失败也不能降级成 Provider 失败或重试。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = fixtures.FakeDocumentJobTranslationProvider()
            runtime.settings.translation_provider_batch_max_attempts = 1
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )

            job_id = created.json()["job_id"]
            repository = runtime.document_job_translation_batch_repository
            batch = repository.list_translation_batches(job_id)[0]
            real_update = repository.update_translation_batch_if_current

            def fail_success_commit(*args, **kwargs):
                if kwargs.get("status") == "succeeded":
                    raise OSError("/private/database/commit unavailable")
                return real_update(*args, **kwargs)

            with patch.object(repository, "update_translation_batch_if_current", side_effect=fail_success_commit):
                execution.execute_translation_batch(batch.id, trace_id="trace_success_commit_io")

            failed_job = runtime.document_job_repository.get_document_job(job_id)
            audit_files = [
                file for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id and file.file_type == "ai_call_log"
            ]
            self.assertEqual(len(provider.requests), 1)
            self.assertEqual(len(audit_files), 1)
            self.assertEqual(
                (failed_job.status, failed_job.stage, failed_job.failed_stage, failed_job.error_code),
                ("failed", "failed", "translating", "oss_failed"),
            )
            self.assertIsNone(failed_job.document_ir_file_id)
            self.assertIsNone(failed_job.result_file_id)

    def test_batch_success_cas_tree_error_keeps_tree_code(self) -> None:
        """成功 CAS 的树失效异常不能被 ValueError 存储兜底覆盖。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = fixtures.FakeDocumentJobTranslationProvider()
            runtime.settings.translation_provider_batch_max_attempts = 1
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )

            job_id = created.json()["job_id"]
            batch = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)[0]
            real_update = runtime.document_job_translation_batch_repository.update_translation_batch_if_current

            def fail_success_commit(*args, **kwargs):
                if kwargs.get("status") == "succeeded":
                    raise TranslationBatchTreeInvalidError("批次树与权威计划不一致")
                return real_update(*args, **kwargs)

            with patch.object(
                runtime.document_job_translation_batch_repository,
                "update_translation_batch_if_current",
                side_effect=fail_success_commit,
            ):
                execution.execute_translation_batch(batch.id, trace_id="trace_success_tree")

            failed_job = runtime.document_job_repository.get_document_job(job_id)
            audit_files = [
                file for file in runtime.document_file_repository.list_document_files()
                if file.job_id == job_id and file.file_type == "ai_call_log"
            ]
            self.assertEqual(len(provider.requests), 1)
            self.assertEqual(len(audit_files), 1)
            self.assertEqual(
                (failed_job.status, failed_job.stage, failed_job.failed_stage, failed_job.error_code),
                ("failed", "failed", "translating", "translation_batch_tree_invalid"),
            )
            self.assertNotEqual(failed_job.error_code, "oss_failed")
            self.assertIsNone(failed_job.document_ir_file_id)
            self.assertIsNone(failed_job.result_file_id)

    def test_sqlite_repository_exception_is_oss_failed_without_provider_retry(self) -> None:
        """SQLite 驱动异常属于存储失败，不能落入 Provider 可重试分支。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = fixtures.FakeDocumentJobTranslationProvider()
            runtime.settings.translation_provider_batch_max_attempts = 1
            runtime.document_ir_translation_service = DocumentIRTranslationService(provider)
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )
            job_id = created.json()["job_id"]
            repository = runtime.document_job_translation_batch_repository
            batch = repository.list_translation_batches(job_id)[0]
            real_update = repository.update_translation_batch_if_current

            def fail_success_commit(*args, **kwargs):
                if kwargs.get("status") == "succeeded":
                    raise sqlite3.OperationalError("database is locked")
                return real_update(*args, **kwargs)

            with patch.object(repository, "update_translation_batch_if_current", side_effect=fail_success_commit):
                execution.execute_translation_batch(batch.id, trace_id="trace_sqlite_storage_error")

            failed_job = runtime.document_job_repository.get_document_job(job_id)
            self.assertEqual(
                (failed_job.status, failed_job.failed_stage, failed_job.error_code),
                ("failed", "translating", "oss_failed"),
            )
            self.assertEqual(len(provider.requests), 1)

    def test_terminal_cas_job_failure_window_replays_without_provider_or_duplicate_events(self) -> None:
        """批次终态 CAS 后任务已失败时，终态自身和排队兄弟都只做幂等停止。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = fixtures.build_test_runtime(
                Path(temp_dir),
                jobs_artifact_storage_backend="local_object",
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(),
                document_jobs_worker_backend="eager",
            )
            provider = _FailOnSecondProvider()
            runtime.settings.translation_provider_batch_max_attempts = 1
            runtime.document_ir_translation_service = DocumentIRTranslationService(
                provider,
                max_items_per_request=3,
                max_chars_per_request=10_000,
            )
            execution = runtime.document_job_execution_service
            execution.document_ir_translation_service = runtime.document_ir_translation_service
            execution.fake_mineru_client.result_zip_bytes = fixtures.make_english_mineru_zip_bytes()
            execution.translation_batch_task_queue = Mock()

            with TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source_file = fixtures.FastAPIJobsBackendTests()._upload_source_pdf(client, headers)
                created = client.post(
                    "/api/v1/document-jobs",
                    headers=headers,
                    json={
                        "source_file_id": source_file["id"],
                        "mode": "en2zh_pdf_to_word",
                        "document_language": "en",
                    },
                )
                self.assertEqual(created.status_code, 201, created.json())
                job_id = created.json()["job_id"]
                batches = runtime.document_job_translation_batch_repository.list_translation_batches(job_id)
                first, second, queued = batches[:3]

                execution.execute_translation_batch(first.id, trace_id="trace_window")
                real_update = runtime.document_job_translation_batch_repository.update_translation_batch_if_current
                injected = False

                def update_and_fail_job(*args, **kwargs):
                    nonlocal injected
                    result = real_update(*args, **kwargs)
                    if result is not None and kwargs.get("status") == "failed" and not injected:
                        injected = True
                    return result

                with patch.object(
                    runtime.document_job_translation_batch_repository,
                    "update_translation_batch_if_current",
                    side_effect=update_and_fail_job,
                ), patch.object(execution, "_finalize_translation_generation", return_value=None):
                    execution.execute_translation_batch(second.id, trace_id="trace_window")

                self.assertTrue(injected)
                self.assertEqual(provider.calls, 2)
                running_job = runtime.document_job_repository.get_document_job(job_id)
                self.assertEqual((running_job.status, running_job.stage), ("running", "translating"))
                events_before = runtime.document_job_event_repository.list_document_job_events(job_id)
                terminal_events_before = [
                    event for event in events_before
                    if event.event_type in {"translation_batch_failed", "stage_failed"}
                ]
                execution.execute_translation_batch(second.id, trace_id="trace_terminal_replay")
                failed_job = runtime.document_job_repository.get_document_job(job_id)
                self.assertEqual((failed_job.status, failed_job.stage), ("failed", "failed"))
                execution.execute_translation_batch(queued.id, trace_id="trace_queued_replay")
                events_after = runtime.document_job_event_repository.list_document_job_events(job_id)

            self.assertEqual(provider.calls, 2)
            self.assertEqual(
                len([
                    event for event in events_after
                    if event.event_type in {"translation_batch_failed", "stage_failed"}
                ]),
                len(terminal_events_before) + 1,
            )
            self.assertEqual(
                len([event for event in events_after if event.event_type == "stage_failed"]),
                1,
            )

