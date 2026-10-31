"""历史预览请求的前置观测边界；复用 main 的模型与锁内领取规则。"""

from datetime import timedelta
import json
from threading import RLock
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from app.core.errors import ApiError
from app.domains.document_jobs.models import DocumentJobPreparedResult, DocumentJobRecord
from app.domains.document_jobs.preview import DocumentJobPreviewService, _preview_storage_io
from app.domains.document_jobs.preview_state import (
    PreviewArtifactObservation, PreviewRun, WordPreviewState, claim_preview,
)
from app.domains.document_jobs.review import ReviewBinding, receipt_identity
from app.domains.files.models import DocumentFileRecord
from app.domains.files.result_registration import review_source_descriptor
from app.domains.resources.models import utc_now
from app.services.preview.models import PreviewFailure, PreviewPolicy, sha256
from app.services.preview.page_quality import PageQualityPolicy, policy_sha256
from app.services.renderer.render_plan import RenderPlanV2, content_hash


A, B, ALIAS, NEW = (f"00000000-0000-4000-8000-{index:012d}" for index in range(1, 5))
REASONS = {A: "历史失败A", B: "当前成功B", ALIAS: "复用当前B", NEW: "新请求C"}


class MemoryPreviewRepository:
    """仅替换存储，领取判定仍在同一锁内调用产品规则。"""

    def __init__(self, job):
        self.job = job
        self.claims = []
        self.lock = RLock()

    def get_document_job(self, job_id):
        return self.job if job_id == self.job.id else None

    def claim_document_job_preview(self, job_id, *, request, observation=None):
        with self.lock:
            if job_id != self.job.id:
                raise AssertionError("测试领取了其他任务。")
            self.claims.append((request, observation))
            claim = claim_preview(self.job, request, observation=observation, now=utc_now())
            self.job = claim.job
            return claim


class WordPreviewHistoricalReplayTests(TestCase):
    def scenario(self, *, page_quality=False):
        now = utc_now()
        policy = PreviewPolicy(backend="sandboxed", profile_id="test-profile", max_runs_per_result=4)
        page_policy = PageQualityPolicy(enabled=True, profile_id=policy.profile_id,
                                        profile_sha256=policy.profile_sha256)
        snapshot = {"word_preview": policy.model_dump(mode="json")}
        metadata, page_hash, context_hash = {}, None, None
        if page_quality:
            snapshot["page_quality"] = page_policy.model_dump(mode="json")
            plan_body = dict(schema_version="render-plan/v2", renderer_policy_version="word-renderer-policy/v2",
                input_ir_sha256="a" * 64, resource_identity=dict(template_sha256=None,
                    effective_config_sha256="b" * 64, symbol_rules_sha256=None, logo_sha256=None,
                    document_language="auto"), layout_mode="layout_v2", styles={}, sections=[],
                decisions=[], operations=[], table_units=[])
            plan = RenderPlanV2.model_validate({**plan_body, "plan_sha256": content_hash(plan_body)})
            metadata = dict(render_trace_status="complete", renderer_content_contract_version="renderer-content/v2",
                            render_plan=plan.model_dump(mode="json"))
            page_hash = policy_sha256(page_policy)
            context_hash = content_hash(dict(schema_version="page-quality-context/v2",
                renderer_content_contract_version="renderer-content/v2", renderer_policy_version="word-renderer-policy/v2",
                template_version_id="default@2", mode="direct_pdf_to_word", document_language="auto",
                resource_identity=plan_body["resource_identity"]))
        source = DocumentFileRecord(id="word", tenant_id="T", company_id="C", job_id="job",
            file_type="generated_word", storage_provider="local_file", bucket="local", object_key="word",
            original_filename="synthetic.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=len(b"selected-docx"), checksum_sha256=sha256(b"selected-docx"), status="uploaded",
            expires_at=now + timedelta(days=1), metadata=metadata, created_at=now, updated_at=now)
        receipt = DocumentJobPreparedResult(generation=0, document_ir_file_id="ir", file=source)
        job = DocumentJobRecord(id="job", tenant_id="T", company_id="C", created_by="U", source_file_id="pdf",
            template_version_id="default@2", status="succeeded", stage="completed", result_file_id=source.id,
            prepared_result=receipt, document_ir_file_id="ir", request_snapshot=snapshot, quality_status="passed",
            review_status="approved", delivery_status="ready_to_publish", current_review_record_id="review",
            review_sequence=1, current_review_binding=ReviewBinding(generation=0, result_file_id=source.id,
                binding_state="verified", result_sha256=source.checksum_sha256, file_review_source_revision=0,
                descriptor=review_source_descriptor(source), receipt_sha256=receipt_identity(SimpleNamespace(prepared_result=receipt))),
            quality_summary={"checks_v1": {"word_preview": {"quality_status": "passed"},
                "word_page_quality": {"quality_status": "passed", "run_sha256": "c" * 64}}},
            created_at=now, updated_at=now)

        def fingerprint(reason):
            # 固定请求身份域，确保 v2 的页面策略和实际上下文继续参与指纹。
            payload = dict(tenant="T", company="C", job="job", generation=0, result="word",
                sha256=source.checksum_sha256, profile=policy.profile_sha256, action="retry", actor="U",
                reason_sha256=sha256(reason.encode()))
            if page_quality:
                payload.update(page_quality_policy_sha256=page_hash, page_quality_context_sha256=context_hash)
            return sha256(json.dumps(payload, sort_keys=True).encode())

        runs = {key: PreviewRun(run_id=f"run-{label}", request_fingerprint=fingerprint(REASONS[key]),
            requested_by="U", reason_sha256=sha256(REASONS[key].encode()), status=status, attempt_count=1,
            max_attempts=policy.max_attempts, run_deadline_at=now + timedelta(seconds=125), started_at=now,
            completed_at=now, artifact_stage="confirmed", confirmed_attempt=1, manifest_file_id=f"manifest-{label}",
            error_code="preview_input_invalid" if key == A else None)
            for key, label, status in ((A, "a", "failed"), (B, "b", "succeeded"))}
        runs[ALIAS] = runs[B].model_copy(update={"request_fingerprint": fingerprint(REASONS[ALIAS]),
            "reason_sha256": sha256(REASONS[ALIAS].encode())})
        job.word_preview_state = WordPreviewState(source_generation=0, source_result_file_id=source.id,
            source_docx_sha256=source.checksum_sha256, profile_id=policy.profile_id, profile_sha256=policy.profile_sha256,
            revision=7, current_request_key=B, max_runs_per_result=policy.max_runs_per_result, runs_by_request_key=runs)
        files = {source.id: source}
        for file_id, file_type in (("manifest-a", "word_preview_manifest"),
                                   ("manifest-b", "word_preview_manifest"), ("pdf-b", "word_preview_pdf")):
            files[file_id] = source.model_copy(update={"id": file_id, "object_key": file_id, "file_type": file_type})
        repository = MemoryPreviewRepository(job)
        provider, event_repository = Mock(), Mock()
        file_repository = Mock(spec=["get_document_file"])
        file_repository.get_document_file.side_effect = files.get
        file_service = Mock(spec=["read_file_content", "register_generated_content"])
        service = DocumentJobPreviewService(None, repository, event_repository, file_repository, file_service, provider)
        # 主件读取与本次门控无关；保留真实 _run、retry 和共享 claim 路径。
        self.enterContext(patch.object(service, "_source", return_value=(source, b"selected-docx")))
        return SimpleNamespace(job=job, repository=repository, service=service, source=source, files=files,
            provider=provider, event_repository=event_repository, file_repository=file_repository,
            file_service=file_service, user=SimpleNamespace(id="U"), page_hash=page_hash,
            context_hash=context_hash, fingerprint=fingerprint)

    def retry(self, case, key, *, reason=None):
        return case.service.retry(case.repository.job, user=case.user,
                                  reason=REASONS[key] if reason is None else reason, request_id=key)

    def assert_no_effects(self, case, before, files_before):
        self.assertEqual(case.repository.job, before)
        self.assertEqual(case.files, files_before)
        case.provider.render.assert_not_called()
        case.file_service.register_generated_content.assert_not_called()
        case.event_repository.append_document_job_event.assert_not_called()

    def test_historical_failure_replays_while_current_manifest_or_pdf_times_out(self):
        for target in ("manifest-b", "pdf-b"):
            with self.subTest(target=target):
                case = self.scenario()
                before = case.job.model_copy(deep=True)
                files_before = {key: file.model_copy(deep=True) for key, file in case.files.items()}
                case.file_service.read_file_content.side_effect = TimeoutError("当前预览对象存储状态未知。")

                def observe(job, file_repository, file_service, *, check_page_quality=False):
                    with _preview_storage_io():
                        file_service.read_file_content(file_repository.get_document_file(target))

                with patch("app.domains.document_jobs.preview.observe_current_preview", side_effect=observe) as observer:
                    replay = self.retry(case, A)
                    self.assertEqual(replay.run, before.word_preview_state.runs_by_request_key[A])
                    self.assertFalse(replay.available)
                    self.assertEqual(replay.job, before)
                    with self.assertRaises(ApiError) as conflict:
                        self.retry(case, A, reason="历史A改参")
                    self.assertEqual((conflict.exception.status_code, conflict.exception.code), (409, "conflict"))
                    observer.assert_not_called()
                    self.assertEqual(len(case.repository.claims), 2)
                    self.assertTrue(all(observation is None for _, observation in case.repository.claims))

                    for key in (B, NEW, ALIAS):
                        with self.subTest(key=key):
                            claims_before = len(case.repository.claims)
                            observations_before = observer.call_count
                            with self.assertRaises(OSError) as failure:
                                self.retry(case, key)
                            self.assertEqual(failure.exception.code, "preview_storage_failed")
                            self.assertEqual(str(failure.exception), "Word 预览存储失败，请稍后重试。")
                            self.assertEqual(observer.call_count, observations_before + 1)
                            self.assertEqual(len(case.repository.claims), claims_before + int(key == ALIAS))
                    self.assertEqual(case.file_service.read_file_content.call_count, 3)
                    self.assertTrue(all(call.args[0].id == target for call in case.file_service.read_file_content.call_args_list))
                self.assert_no_effects(case, before, files_before)

    def test_unconfirmed_historical_run_is_not_treated_as_completed(self):
        for artifact_stage, confirmed_attempt in ((None, None), ("registering", None), ("confirmed", 2)):
            with self.subTest(artifact_stage=artifact_stage, confirmed_attempt=confirmed_attempt):
                case = self.scenario()
                run = case.job.word_preview_state.runs_by_request_key[A]
                run.artifact_stage, run.confirmed_attempt = artifact_stage, confirmed_attempt
                before = case.job.model_copy(deep=True)
                files_before = {key: file.model_copy(deep=True) for key, file in case.files.items()}
                with patch("app.domains.document_jobs.preview.observe_current_preview") as observer:
                    with self.assertRaises(PreviewFailure) as failure:
                        self.retry(case, A)
                    self.assertEqual(failure.exception.code, "preview_storage_failed")
                    observer.assert_not_called()
                self.assertEqual(len(case.repository.claims), 1)
                self.assert_no_effects(case, before, files_before)

    def test_new_key_keeps_page_quality_check_and_v2_request_identity(self):
        case = self.scenario(page_quality=True)
        before = case.job.model_copy(deep=True)

        def observe(job, file_repository, file_service, *, check_page_quality=False):
            state, run = job.word_preview_state, job.word_preview_state.current_run
            return PreviewArtifactObservation(source_generation=state.source_generation,
                source_result_file_id=state.source_result_file_id, source_docx_sha256=state.source_docx_sha256,
                profile_id=state.profile_id, profile_sha256=state.profile_sha256, revision=state.revision,
                current_request_key=state.current_request_key, run_id=run.run_id, attempt=run.attempt_count,
                manifest_file_id=run.manifest_file_id, files=tuple(case.files.values()),
                earliest_expires_at=case.source.expires_at, available=True,
                page_quality_policy_sha256=case.page_hash, page_quality_run_sha256="c" * 64,
                page_quality_reusable=True if check_page_quality else None)

        with patch("app.domains.document_jobs.preview.observe_current_preview", side_effect=observe) as observer:
            result = self.retry(case, NEW)
        self.assertTrue(result.available)
        self.assertEqual([call.kwargs.get("check_page_quality", False) for call in observer.call_args_list], [True, False])
        self.assertEqual(len(case.repository.claims), 1)
        request, observation = case.repository.claims[0]
        self.assertTrue(observation.page_quality_reusable)
        self.assertEqual(request.page_quality_policy_sha256, case.page_hash)
        self.assertEqual(request.page_quality_context_sha256, case.context_hash)
        self.assertEqual(request.request_fingerprint, case.fingerprint(REASONS[NEW]))
        self.assertEqual(result.run.run_id, before.word_preview_state.current_run.run_id)
        state = result.job.word_preview_state
        self.assertEqual(state.current_request_key, B)
        self.assertEqual(state.current_run, before.word_preview_state.current_run)
        self.assertEqual(set(state.runs_by_request_key), {A, B, ALIAS, NEW})
        self.assertEqual(state.revision, before.word_preview_state.revision + 1)
        self.assertEqual(result.job.model_dump(exclude={"word_preview_state", "updated_at"}),
                         before.model_dump(exclude={"word_preview_state", "updated_at"}))
        case.provider.render.assert_not_called()
        case.file_service.register_generated_content.assert_not_called()
        case.event_repository.append_document_job_event.assert_not_called()
