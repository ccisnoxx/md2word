"""覆盖任务模式输入兼容、direct 资源边界和历史快照的惰性行为。"""

from contextlib import ExitStack, contextmanager
from copy import deepcopy
import io
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch

from tests import test_fastapi_jobs_backend as fixtures

from app.domains.translation import profiles_service
from app.domains.jobs import resource_snapshots
from app.domains.translation.modes import normalize_translation_mode


TRANSLATION_SELECTIONS = {
    "term_version_id": "en2zh@v1",
    "translation_term_set_id": "translation-terms-en2zh",
    "translation_term_version": "v1",
    "translation_profile_id": "electronics-en2zh",
    "translation_profile_version": "1",
}


class DocumentJobModesTests(TestCase):
    # 只复用上传 helper，不继承大型测试类，避免 unittest 重复收集其全部用例。
    _upload_source_pdf = fixtures.FastAPIJobsBackendTests._upload_source_pdf

    @contextmanager
    def _client_runtime(self, *, versioned=False, eager=False):
        with tempfile.TemporaryDirectory() as temp_dir:
            builder = fixtures.build_mysql_test_runtime if versioned else fixtures.build_test_runtime
            runtime = builder(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_multi_operator_auth_users_json(),
                document_jobs_worker_backend="eager" if eager else "disabled",
                jobs_artifact_storage_backend="local_object",
            )
            with fixtures.TestClient(fixtures.create_app(runtime)) as client:
                operator = fixtures.build_auth_header(client)
                admin = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                yield runtime, client, operator, admin

    @contextmanager
    def _translation_spies(self, runtime):
        """在 fake runtime 初始化后观察实际术语、Profile、Prompt 和 Provider 调用。"""

        with ExitStack() as stack:
            targets = {
                "term_resolve": (runtime.term_version_service, "resolve_for_job"),
                "term_load": (runtime.term_version_service, "load_version"),
                "profile_payload": (resource_snapshots, "translation_profile_snapshot_from_record"),
                "profile_payload_service": (profiles_service, "translation_profile_snapshot_from_record"),
                "prompt": (profiles_service, "_read_seed_prompt"),
                "provider": (runtime.document_ir_translation_service.provider, "translate"),
                "translation": (runtime.document_ir_translation_service, "translate"),
            }
            spies = {
                name: stack.enter_context(patch.object(owner, attribute, wraps=getattr(owner, attribute)))
                for name, (owner, attribute) in targets.items()
            }
            yield spies

    def _assert_no_translation_calls(self, spies):
        for name, spy in spies.items():
            self.assertEqual(spy.call_count, 0, name)

    def _mutation_state(self, runtime, source_file_id):
        jobs = runtime.document_job_repository.list_document_jobs()
        return (
            [job.model_dump(mode="json") for job in jobs],
            runtime.document_file_repository.get_document_file(source_file_id).model_dump(mode="json"),
            [event.model_dump(mode="json") for event in runtime.audit_event_repository.list_audit_events()],
            [
                event.model_dump(mode="json")
                for job in jobs
                for event in runtime.document_job_event_repository.list_document_job_events(job.id)
            ],
        )

    def _assert_api_error(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code, response.json())
        payload = response.json()
        self.assertEqual(payload["error_code"], code)
        self.assertEqual(payload["error"]["code"], code)
        self.assertTrue(payload["trace_id"])
        self.assertEqual(payload["error"]["trace_id"], payload["trace_id"])

    def _create_direct(self, client, headers):
        source = self._upload_source_pdf(client, headers)
        response = client.post("/api/v1/document-jobs", headers=headers, json={"source_file_id": source["id"]})
        self.assertEqual(response.status_code, 201, response.json())
        return source, response.json()["job_id"]

    def _seed_historical_direct(self, runtime, job_id):
        """模拟已存在的惰性翻译元数据；所指资源故意不存在。"""

        job = runtime.document_job_repository.get_document_job(job_id)
        snapshot = deepcopy(job.request_snapshot)
        snapshot["term_version_id"] = "en2zh@retired"
        snapshot["term_assets"].update(
            translation_term_set_id="historical-terms", translation_term_version="retired"
        )
        snapshot["translation_profile"] = {
            "translation_profile_id": "historical-profile", "translation_profile_version": "retired"
        }
        resources = snapshot["resources"] or {}
        resources.update(
            translation_term_set={"set_id": "historical-terms", "version": "retired"},
            translation_profile={"resource_id": "historical-profile", "version": "retired"},
            translation_prompt_id="historical-prompt",
            translation_prompt_content_hash="sha256:historical",
        )
        snapshot["resources"] = resources
        return runtime.document_job_repository.update_document_job(
            job_id,
            term_version_id="en2zh@retired",
            request_snapshot=snapshot,
            status="failed",
            stage="failed",
            failed_stage="parsing",
            error_code="mineru_failed",
            error_message="可重试的合成失败",
        )

    def test_http_historical_aliases_create_canonical_direct(self):
        with self._client_runtime() as (runtime, client, operator, _admin):
            for alias in ("zh2zh", "zh_to_zh", " ZH_TO_ZH "):
                for mode in (None, "direct_pdf_to_word"):
                    with self.subTest(alias=alias, mode=mode):
                        source = self._upload_source_pdf(client, operator)
                        request = {"source_file_id": source["id"], "translation_mode": alias}
                        if mode is not None:
                            request["mode"] = mode
                        response = client.post("/api/v1/document-jobs", headers=operator, json=request)
                        self.assertEqual(response.status_code, 201, response.json())
                        job = response.json()["job"]
                        self.assertEqual(job["mode"], "direct_pdf_to_word")
                        self.assertEqual(job["translation_mode"], "direct")
                        self.assertEqual(job["request_snapshot"]["translation_mode"], "direct")
                        created = runtime.document_job_event_repository.list_document_job_events(job["id"])[0]
                        self.assertEqual(created.payload["mode"], "direct_pdf_to_word")
                        self.assertEqual(created.payload["translation_mode"], "direct")
            for alias in ("zh2zh", "zh_to_zh"):
                self.assertEqual(
                    runtime.document_job_service._resolve_document_job_mode(
                        mode="direct_pdf_to_word", translation_mode=alias
                    ),
                    "direct_pdf_to_word",
                )

    def test_http_conflicting_alias_and_invalid_modes_keep_errors_without_mutation(self):
        with self._client_runtime() as (runtime, client, operator, _admin):
            source = self._upload_source_pdf(client, operator)
            queue = runtime.document_job_service.task_queue = Mock()
            before = self._mutation_state(runtime, source["id"])
            for alias in ("zh2zh", "zh_to_zh"):
                response = client.post(
                    "/api/v1/document-jobs",
                    headers=operator,
                    json={"source_file_id": source["id"], "mode": "en2zh_pdf_to_word", "translation_mode": alias},
                )
                self._assert_api_error(response, 400, "invalid_request")
            for field in ("mode", "translation_mode"):
                for invalid in ("", " ", "unknown", 0, False, [], {}):
                    with self.subTest(field=field, invalid=invalid):
                        response = client.post(
                            "/api/v1/document-jobs", headers=operator,
                            json={"source_file_id": source["id"], field: invalid},
                        )
                        self._assert_api_error(response, 422, "validation_error")
            self.assertEqual(self._mutation_state(runtime, source["id"]), before)
            queue.enqueue.assert_not_called()

    def test_direct_create_rejects_each_translation_selection_before_loading(self):
        for versioned in (False, True):
            with self.subTest(versioned=versioned), self._client_runtime(versioned=versioned) as (
                runtime, client, operator, admin
            ):
                queue = runtime.document_job_service.task_queue = Mock()
                with self._translation_spies(runtime) as spies:
                    for headers in (operator, admin):
                        for field, value in TRANSLATION_SELECTIONS.items():
                            with self.subTest(field=field, headers=headers is admin):
                                source = self._upload_source_pdf(client, headers)
                                before = self._mutation_state(runtime, source["id"])
                                response = client.post(
                                    "/api/v1/document-jobs", headers=headers,
                                    json={"source_file_id": source["id"], field: value},
                                )
                                self._assert_api_error(response, 400, "invalid_request")
                                self.assertEqual(self._mutation_state(runtime, source["id"]), before)
                    self._assert_no_translation_calls(spies)
                queue.enqueue.assert_not_called()

    def test_direct_create_debug_keeps_role_priority_and_has_no_side_effects(self):
        with self._client_runtime() as (runtime, client, operator, admin):
            queue = runtime.document_job_service.task_queue = Mock()
            with self._translation_spies(runtime) as spies:
                for headers, status_code, code in ((operator, 403, "role_forbidden"), (admin, 400, "invalid_request")):
                    source = self._upload_source_pdf(client, headers)
                    before = self._mutation_state(runtime, source["id"])
                    response = client.post(
                        "/api/v1/document-jobs", headers=headers,
                        json={"source_file_id": source["id"], "debug_full_text": True, "term_version_id": "en2zh@v1"},
                    )
                    self._assert_api_error(response, status_code, code)
                    self.assertEqual(self._mutation_state(runtime, source["id"]), before)
                self._assert_no_translation_calls(spies)
            queue.enqueue.assert_not_called()

    def test_direct_without_translation_configuration_executes_one_docx_without_translation_calls(self):
        for versioned in (False, True):
            with self.subTest(versioned=versioned), self._client_runtime(versioned=versioned, eager=True) as (
                runtime, client, operator, _admin
            ):
                self.assertEqual(runtime.settings.translation_provider_backend, "disabled")
                if not versioned:
                    self.assertIsNone(runtime.translation_profile_service)
                with self._translation_spies(runtime) as spies:
                    _source, job_id = self._create_direct(client, operator)
                    job = runtime.document_job_repository.get_document_job(job_id)
                    self.assertEqual((job.status, job.stage), ("succeeded", "completed"))
                    files = runtime.document_job_service.list_files(
                        job_id, user=runtime.auth_service.authenticate("operator", "operator-pass")
                    )
                    words = [file for file in files if file.file_type == "generated_word"]
                    self.assertEqual(len(words), 1)
                    self.assertEqual(words[0].id, job.result_file_id)
                    document = fixtures.Document(io.BytesIO(runtime.file_upload_service.read_file_content(words[0])))
                    self.assertTrue(document.paragraphs)
                    self.assertFalse({"ai_call_log", "ai_debug_archive"} & {file.file_type for file in files})
                    self.assertEqual(runtime.document_job_translation_batch_repository.list_translation_batches(job_id), [])
                    self._assert_no_translation_calls(spies)
                    self.assertEqual(len(runtime.document_job_execution_service.fake_mineru_client.calls), 1)

    def test_direct_retry_and_clone_reject_new_translation_selections_after_permissions(self):
        for versioned in (False, True):
            with self.subTest(versioned=versioned), self._client_runtime(versioned=versioned) as (
                runtime, client, operator, admin
            ):
                source, job_id = self._create_direct(client, operator)
                runtime.document_job_repository.update_document_job(
                    job_id, status="failed", stage="failed", failed_stage="parsing", error_code="mineru_failed"
                )
                queue = runtime.document_job_service.task_queue = Mock()
                before = self._mutation_state(runtime, source["id"])
                with self._translation_spies(runtime) as spies:
                    for headers, status_code, code in ((operator, 403, "forbidden"), (admin, 400, "invalid_request")):
                        for action, fields in (
                            ("retry", {key: value for key, value in TRANSLATION_SELECTIONS.items() if key in {
                                "translation_term_set_id", "translation_term_version"
                            }}),
                            ("clone", TRANSLATION_SELECTIONS),
                        ):
                            for field, value in fields.items():
                                with self.subTest(action=action, field=field, admin=headers is admin):
                                    request = {field: value}
                                    if action == "clone":
                                        request["config_strategy"] = "select_published_versions"
                                    response = client.post(
                                        f"/api/v1/document-jobs/{job_id}/{action}", headers=headers, json=request
                                    )
                                    self._assert_api_error(response, status_code, code)
                                    self.assertEqual(self._mutation_state(runtime, source["id"]), before)
                    for headers, status_code, code in ((operator, 403, "role_forbidden"), (admin, 400, "invalid_request")):
                        response = client.post(
                            f"/api/v1/document-jobs/{job_id}/clone", headers=headers,
                            json={"debug_full_text": True},
                        )
                        self._assert_api_error(response, status_code, code)
                        self.assertEqual(self._mutation_state(runtime, source["id"]), before)
                    self._assert_no_translation_calls(spies)
                queue.enqueue.assert_not_called()

    def test_direct_rejection_preserves_source_access_and_retry_state_priority(self):
        with self._client_runtime() as (runtime, client, operator, admin):
            source = self._upload_source_pdf(client, admin)
            response = client.post(
                "/api/v1/document-jobs", headers=operator,
                json={"source_file_id": source["id"], "term_version_id": "en2zh@v1"},
            )
            self._assert_api_error(response, 403, "forbidden")
            source, job_id = self._create_direct(client, operator)
            before = self._mutation_state(runtime, source["id"])
            response = client.post(
                f"/api/v1/document-jobs/{job_id}/retry", headers=admin,
                json={"translation_term_version": "v1"},
            )
            self._assert_api_error(response, 409, "conflict")
            self.assertEqual(self._mutation_state(runtime, source["id"]), before)
            other = fixtures.build_auth_header(client, username="operator2", password="operator2-pass")
            # 登录本身会产生审计，因此在登录后重新记录 mutation 边界。
            before = self._mutation_state(runtime, source["id"])
            response = client.post(
                f"/api/v1/document-jobs/{job_id}/clone", headers=other,
                json={"config_strategy": "select_published_versions", "term_version_id": "en2zh@v1"},
            )
            self._assert_api_error(response, 403, "forbidden")
            self.assertEqual(self._mutation_state(runtime, source["id"]), before)

    def test_direct_create_boundary_does_not_depend_on_translation_services(self):
        with self._client_runtime() as (runtime, client, operator, _admin):
            runtime.document_job_service.term_version_service = None
            runtime.document_job_service.job_resource_snapshot_service = None
            source = self._upload_source_pdf(client, operator)
            queue = runtime.document_job_service.task_queue = Mock()
            before = self._mutation_state(runtime, source["id"])
            for field, value in TRANSLATION_SELECTIONS.items():
                with self.subTest(field=field):
                    response = client.post(
                        "/api/v1/document-jobs", headers=operator,
                        json={"source_file_id": source["id"], field: value},
                    )
                    self._assert_api_error(response, 400, "invalid_request")
                    self.assertEqual(self._mutation_state(runtime, source["id"]), before)
            queue.enqueue.assert_not_called()

    def test_historical_direct_read_clone_and_default_retry_keep_lazy_snapshot(self):
        with self._client_runtime(versioned=True) as (runtime, client, operator, admin):
            source, job_id = self._create_direct(client, operator)
            historical = self._seed_historical_direct(runtime, job_id)
            source_record = historical.model_dump(mode="json")
            source_events = deepcopy(runtime.document_job_event_repository.list_document_job_events(job_id))
            audits = deepcopy(runtime.audit_event_repository.list_audit_events())
            queue = runtime.document_job_service.task_queue = Mock()
            with self._translation_spies(runtime) as spies:
                detail = client.get(f"/api/v1/document-jobs/{job_id}", headers=operator)
                self.assertEqual(detail.status_code, 200)
                self.assertEqual(detail.json()["request_snapshot"], historical.request_snapshot)
                self.assertEqual(runtime.audit_event_repository.list_audit_events(), audits)
                clone = client.post(f"/api/v1/document-jobs/{job_id}/clone", headers=operator, json={})
                self.assertEqual(clone.status_code, 201, clone.json())
                kept = clone.json()["job"]["request_snapshot"]
                for key in ("term_version_id", "term_assets", "translation_profile", "resources"):
                    self.assertEqual(kept[key], historical.request_snapshot[key])
                self.assertEqual(runtime.document_job_repository.get_document_job(job_id).model_dump(mode="json"), source_record)
                self.assertEqual(runtime.document_job_event_repository.list_document_job_events(job_id), source_events)
                current = client.post(
                    f"/api/v1/document-jobs/{job_id}/clone", headers=admin,
                    json={"config_strategy": "use_current_defaults"},
                )
                self.assertEqual(current.status_code, 201, current.json())
                current_job = current.json()["job"]
                self.assertIsNone(current_job["term_version_id"])
                self.assertIsNone(current_job["request_snapshot"]["resources"]["translation_term_set"])
                self.assertIsNone(current_job["request_snapshot"]["resources"]["translation_profile"])
                self.assertEqual(runtime.document_job_repository.get_document_job(job_id).model_dump(mode="json"), source_record)
                retry = client.post(f"/api/v1/document-jobs/{job_id}/retry", headers=operator, json={})
                self.assertEqual(retry.status_code, 200, retry.json())
                self.assertEqual(retry.json()["job"]["request_snapshot"], historical.request_snapshot)
                self.assertEqual(retry.json()["job"]["term_version_id"], "en2zh@retired")
                self.assertEqual(runtime.document_file_repository.get_document_file(source["id"]).job_id, job_id)
                self.assertEqual(runtime.document_job_event_repository.list_document_job_events(job_id)[:-1], source_events)
                self.assertEqual(runtime.audit_event_repository.list_audit_events()[:len(audits)], audits)
                self._assert_no_translation_calls(spies)
            self.assertEqual(queue.enqueue.call_count, 3)

    def test_direct_symbol_rules_stay_available_for_create_retry_and_clone(self):
        with self._client_runtime(versioned=True) as (runtime, client, _operator, admin):
            with self._translation_spies(runtime) as spies:
                source = self._upload_source_pdf(client, admin)
                create = client.post(
                    "/api/v1/document-jobs", headers=admin,
                    json={"source_file_id": source["id"], "term_rule_set_id": "electronics-default", "term_rule_set_version": "seed"},
                )
                self.assertEqual(create.status_code, 201, create.json())
                job_id = create.json()["job_id"]
                self._seed_historical_direct(runtime, job_id)
                for request in ({"term_rule_set_version": "seed"}, {"use_latest_term_assets": True}):
                    runtime.document_job_repository.update_document_job(
                        job_id, status="failed", stage="failed", failed_stage="parsing", error_code="mineru_failed"
                    )
                    retry = client.post(f"/api/v1/document-jobs/{job_id}/retry", headers=admin, json=request)
                    self.assertEqual(retry.status_code, 200, retry.json())
                    self.assertEqual(retry.json()["job"]["request_snapshot"]["resources"]["term_rule_set"]["resource_id"], "electronics-default")
                clone = client.post(
                    f"/api/v1/document-jobs/{job_id}/clone", headers=admin,
                    json={"config_strategy": "select_published_versions", "term_rule_set_version": "seed"},
                )
                self.assertEqual(clone.status_code, 201, clone.json())
                self._assert_no_translation_calls(spies)

    def test_internal_aliases_remain_supported_and_schema_enum_remains_canonical(self):
        for alias, expected in {
            "none": "direct", "zh2zh": "direct", "zh_to_zh": "direct",
            "llm_en_to_zh": "en2zh", "en_to_zh": "en2zh",
            "llm_ru_to_zh": "ru2zh", "ru_to_zh": "ru2zh",
        }.items():
            self.assertEqual(normalize_translation_mode(alias), expected)
        from app.domains.document_jobs.schemas import DocumentJobCreateRequest

        alternatives = DocumentJobCreateRequest.model_json_schema()["properties"]["translation_mode"]["anyOf"]
        self.assertEqual(alternatives[0]["enum"], ["direct", "en2zh", "ru2zh", "zh2en", "zh2ru"])


if __name__ == "__main__":
    import unittest

    unittest.main()
