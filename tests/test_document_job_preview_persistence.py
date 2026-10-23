"""预览专用 CAS、历史去重和质量归属的三 adapter 合同。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import multiprocessing
from unittest import TestCase
from unittest.mock import patch

from app.core.config import Settings
from app.domains.files.service import FileUploadService, RETENTION_DELETE_CONFIRMATION_PHRASE
from app.domains.files.retention import DocumentFileRetentionPlanner
from app.domains.document_jobs.preview_state import PreviewArtifactObservation, PreviewClaimRequest
from app.domains.document_jobs.delivery_state import document_job_state_columns
from app.domains.resources.models import utc_now
from app.services.preview.models import PreviewPolicy, sha256
from tests.test_document_job_delivery_state import _repository, _job
from tests.test_document_job_result_persistence import _candidate, _adapters


def prepared(repository, *, complete=True, policy=None, quality="pending", summary=None):
    policy = policy or PreviewPolicy(backend="sandboxed")
    job = _job(status="running", stage="uploading", document_ir_file_id="ir", quality_status=quality,
               quality_summary=summary or {}, request_snapshot={"word_preview": policy.model_dump(mode="json")},
               timeout_at=utc_now() + timedelta(minutes=5))
    repository.create_document_job(job)
    job = repository.prepare_document_job_result(job.id, expected_retry_count=0,
        expected_document_ir_file_id="ir", candidate=_candidate())
    if complete:
        job = repository.update_document_job(job.id, status="succeeded", stage="completed", result_file_id="candidate")
    return job


def request(job, key="initial", *, resume=False):
    return PreviewClaimRequest(generation=job.retry_count, result_file_id=job.prepared_result.file.id,
        docx_sha256=job.prepared_result.file.checksum_sha256, policy=PreviewPolicy.model_validate(job.request_snapshot["word_preview"]),
        request_key=key, request_fingerprint=sha256(key.encode()), requested_by="operator", reason_sha256=sha256(b"reason"),
        independent=job.status == "succeeded", resume=resume)


def finish(repository, claim, req, *, success=False, retryable=False):
    begun = repository.begin_document_job_preview_registration(claim.job.id, request=req,
        revision=claim.job.word_preview_state.revision, lease_token=claim.lease_token,
        attempt=claim.job.word_preview_state.current_run.attempt_count)
    if begun is None:
        return None
    return repository.finish_document_job_preview(claim.job.id, request=req,
        revision=begun.word_preview_state.revision, lease_token=claim.lease_token,
        status="succeeded" if success else "failed", manifest_file_id="manifest-" + claim.job.word_preview_state.current_run.run_id,
        error_code=None if success else "preview_engine_failed", retryable=retryable,
        evidence={"pdf_file_id": "pdf", "page_file_ids": [], "page_count": 1} if success else {})


def observation(job, *, available=True):
    """纯仓储测试注入已核验观测；真实文件链由应用测试覆盖。"""
    state = job.word_preview_state
    return PreviewArtifactObservation(source_generation=state.source_generation,
        source_result_file_id=state.source_result_file_id, source_docx_sha256=state.source_docx_sha256,
        profile_id=state.profile_id, profile_sha256=state.profile_sha256, revision=state.revision,
        current_request_key=state.current_request_key, run_id=state.current_run.run_id,
        attempt=state.current_run.attempt_count, manifest_file_id=state.current_run.manifest_file_id,
        files=(job.prepared_result.file,), earliest_expires_at=job.prepared_result.file.expires_at,
        available=available)


def process_claim(kind, root, serialized, ready, start, output):
    repository = _adapters(kind, root).document_job_repository
    ready.put(True)
    if not start.wait(15): raise RuntimeError("预览竞争屏障超时。")
    claim = repository.claim_document_job_preview("job", request=PreviewClaimRequest.model_validate(serialized))
    output.put(claim.disposition)


class DocumentJobPreviewPersistenceTests(TestCase):
    def test_three_adapters_history_replay_survives_restart_without_moving_current(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repo, build, db):
                job = prepared(repo)
                a = request(job, "A")
                first = repo.claim_document_job_preview(job.id, request=a)
                a_run = first.job.word_preview_state.current_run.run_id
                finish(repo, first, a)
                b = request(job, "B")
                second = repo.claim_document_job_preview(job.id, request=b)
                finish(repo, second, b)
                repo = build().document_job_repository
                before = repo.get_document_job(job.id)
                replay = repo.claim_document_job_preview(job.id, request=a)
                self.assertEqual(replay.disposition, "historical")
                self.assertEqual(replay.run.run_id, a_run)
                self.assertEqual(replay.job, before)
                self.assertEqual(replay.job.word_preview_state.current_request_key, "B")
                self.assertEqual(sum(run.attempt_count for run in replay.job.word_preview_state.runs_by_request_key.values()), 2)
                with self.assertRaisesRegex(ValueError, "参数不一致"):
                    repo.claim_document_job_preview(job.id, request=a.model_copy(update={"request_fingerprint": sha256(b"different")}))
                if kind == "mysql":
                    self.assertTrue(any("for update" in sql for sql in db.executed_sql))
                    record = db.document_jobs[job.id]
                    self.assertEqual(tuple(record[key] for key in ("quality_status", "review_status", "delivery_status", "quality_summary_json")), document_job_state_columns(before))

    def test_success_reuse_consumes_fingerprint_key_without_moving_current_or_attempts(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repo, build, _):
                job = prepared(repo, policy=PreviewPolicy(backend="sandboxed", max_runs_per_result=2))
                a = request(job, "A")
                selected = finish(repo, repo.claim_document_job_preview(job.id, request=a), a, success=True)
                b = request(job, "B")
                reused = repo.claim_document_job_preview(job.id, request=b, observation=observation(selected))
                self.assertEqual(reused.disposition, "reused")
                self.assertIn("B", reused.job.word_preview_state.runs_by_request_key)
                self.assertEqual(reused.run.run_id, selected.word_preview_state.current_run.run_id)
                self.assertEqual(reused.job.word_preview_state.current_request_key, "A")
                self.assertEqual(reused.job.word_preview_state.current_run.attempt_count, 1)
                self.assertEqual(reused.job.quality_summary, selected.quality_summary)
                repo = build().document_job_repository
                replay = repo.claim_document_job_preview(job.id, request=b)
                self.assertEqual(replay.disposition, "historical")
                self.assertEqual(replay.run, reused.run)
                self.assertEqual(replay.job.word_preview_state.current_request_key, "A")
                with self.assertRaisesRegex(ValueError, "参数不一致"):
                    repo.claim_document_job_preview(job.id, request=b.model_copy(update={"request_fingerprint": sha256(b"other reason")}))
                with self.assertRaisesRegex(ValueError, "上限"):
                    repo.claim_document_job_preview(job.id, request=request(job, "C"))
                self.assertEqual(repo.claim_document_job_preview(job.id, request=a).disposition, "historical")

    def test_history_limit_rejects_new_keys_without_evicting_consumed_ids(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repo, _, __):
                job = prepared(repo, policy=PreviewPolicy(backend="sandboxed", max_runs_per_result=2))
                for key in ("A", "B"):
                    req = request(job, key)
                    finish(repo, repo.claim_document_job_preview(job.id, request=req), req)
                before = repo.get_document_job(job.id)
                with self.assertRaisesRegex(ValueError, "上限"):
                    repo.claim_document_job_preview(job.id, request=request(job, "C"))
                self.assertEqual(repo.get_document_job(job.id), before)
                self.assertEqual(repo.claim_document_job_preview(job.id, request=request(job, "A")).disposition, "historical")

    def test_expired_lease_takeover_budget_old_token_and_fixed_independent_deadline(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repo, build, db):
                job = prepared(repo)
                repo.update_document_job(job.id, timeout_at=utc_now() - timedelta(days=1))
                req = request(job, "A")
                first = repo.claim_document_job_preview(job.id, request=req)
                deadline = first.job.word_preview_state.current_run.run_deadline_at
                self.assertEqual(first.disposition, "claimed")
                self.assertEqual(repo.claim_document_job_preview(job.id, request=req).disposition, "busy")
                future = first.job.word_preview_state.current_run.lease_expires_at + timedelta(milliseconds=1)
                with patch(f"app.infrastructure.persistence.{kind}.document_jobs.utc_now", return_value=future):
                    next_claim = build().document_job_repository.claim_document_job_preview(job.id, request=req)
                    self.assertEqual(next_claim.disposition, "claimed")
                    self.assertEqual(next_claim.job.word_preview_state.current_run.attempt_count, 2)
                    self.assertEqual(next_claim.job.word_preview_state.current_run.run_deadline_at, deadline)
                    self.assertIsNone(finish(repo, first, req, success=True))
                    self.assertIsNotNone(finish(repo, next_claim, req, success=True))
                    self.assertIsNone(finish(repo, next_claim, req, success=True))
                self.assertIsNone(repo.update_document_job_if_current(job.id, allowed_statuses={"succeeded"}, allowed_stages={"completed"}, progress=99))

    def test_crash_after_claim_and_exhaustion_never_resets_attempts(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repo, build, _):
                job = prepared(repo, policy=PreviewPolicy(backend="sandboxed", max_attempts=1))
                req = request(job, "A")
                claimed = repo.claim_document_job_preview(job.id, request=req)
                future = claimed.job.word_preview_state.current_run.lease_expires_at + timedelta(milliseconds=1)
                with patch(f"app.infrastructure.persistence.{kind}.document_jobs.utc_now", return_value=future):
                    recovered = build().document_job_repository.claim_document_job_preview(job.id, request=req)
                    self.assertEqual(recovered.disposition, "finalizing")
                    self.assertEqual(recovered.job.word_preview_state.current_run.artifact_stage, "not_started")
                    self.assertEqual(recovered.job.word_preview_state.current_run.attempt_count, 1)
                    self.assertIsNone(finish(repo, claimed, req, success=True))

    def test_three_adapters_stale_lifecycle_source_and_profile_cannot_finish(self):
        for kind in ("file", "sqlite", "mysql"):
            for change in ("archive", "delete", "published", "generation", "profile", "source"):
                with self.subTest(kind=kind, change=change), _repository(kind) as (repo, _, __):
                    job = prepared(repo, quality="passed")
                    req = request(job)
                    claimed = repo.claim_document_job_preview(job.id, request=req)
                    if change == "archive": repo.update_document_job(job.id, archived_at=utc_now())
                    elif change == "delete": repo.update_document_job(job.id, deleted_at=utc_now())
                    elif change == "published": repo.update_document_job(job.id, review_status="approved", delivery_status="published")
                    elif change == "generation": repo.update_document_job(job.id, retry_count=1, prepared_result=None)
                    elif change == "profile": req = req.model_copy(update={"policy": req.policy.model_copy(update={"profile_sha256": sha256(b"other")})})
                    else: req = req.model_copy(update={"result_file_id": "other"})
                    self.assertIsNone(finish(repo, claimed, req, success=True))
                    self.assertEqual(repo.claim_document_job_preview(job.id, request=req).disposition, "stale")

    def test_running_preview_rejects_cancel_and_total_timeout(self):
        for kind in ("file", "sqlite", "mysql"):
            for cancel in (False, True):
                with self.subTest(kind=kind, cancel=cancel), _repository(kind) as (repo, _, __):
                    job = prepared(repo, complete=False)
                    req = request(job)
                    claim = repo.claim_document_job_preview(job.id, request=req)
                    repo.update_document_job(job.id, **({"status": "canceled", "stage": "canceled"} if cancel else {"timeout_at": utc_now() - timedelta(seconds=1)}))
                    self.assertIsNone(finish(repo, claim, req, success=True))

    def test_quality_only_removes_owned_blocker_and_progress_does_not_capture_it(self):
        for kind in ("file", "sqlite", "mysql"):
            for base in ("pending", "warning", "passed", "blocked"):
                for explicit_block in (False, True):
                    with self.subTest(kind=kind, base=base, explicit_block=explicit_block), _repository(kind) as (repo, _, __):
                        job = prepared(repo, quality=base)
                        if base in {"passed", "warning"}:
                            repo.update_document_job(job.id, review_status="approved", delivery_status="ready_to_publish")
                        req = request(job, "A")
                        failed = finish(repo, repo.claim_document_job_preview(job.id, request=req), req)
                        self.assertEqual(failed.quality_status, "blocked")
                        repo.update_document_job(job.id, progress=99)
                        repo.update_document_job(job.id, prepared_result=job.prepared_result)
                        if explicit_block: repo.update_document_job(job.id, quality_status="blocked")
                        req_b = request(job, "B")
                        succeeded = finish(repo, repo.claim_document_job_preview(job.id, request=req_b), req_b, success=True)
                        self.assertEqual(succeeded.quality_status, "blocked" if explicit_block else base)
                        self.assertEqual(succeeded.review_status, "unreviewed")
                        self.assertEqual(succeeded.delivery_status, "internal_draft")

    def test_other_quality_contributions_and_unknown_structures_are_preserved(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repo, _, __):
                job = prepared(repo, quality="blocked", summary={"checks_v1": {"__unattributed__": {"quality_status": "passed"}, "other": {"quality_status": "blocked"}}})
                req = request(job)
                result = finish(repo, repo.claim_document_job_preview(job.id, request=req), req, success=True)
                self.assertEqual(result.quality_status, "blocked")
                self.assertEqual(result.quality_summary["checks_v1"]["other"], {"quality_status": "blocked"})
                with self.assertRaises(ValueError): repo.update_document_job(job.id, quality_summary={})
            with _repository(kind) as (repo, _, __):
                job = _job(quality_summary={"checks_v1": "unknown"})
                repo.create_document_job(job)
                with self.assertRaisesRegex(ValueError, "结构无效"):
                    repo.update_document_job(job.id, progress=1)

    def test_retry_resets_current_identity_and_quality_without_altering_old_record(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repo, _, __):
                job = prepared(repo, complete=False)
                req = request(job)
                failed = finish(repo, repo.claim_document_job_preview(job.id, request=req), req)
                repo.update_document_job(job.id, status="failed", stage="failed")
                new = repo.retry_document_job(job.id, expected_retry_count=0, max_retries=2,
                    status="running", stage="rendering", retry_count=1)
                self.assertIsNone(new.word_preview_state)
                self.assertEqual(new.quality_summary, {})
                self.assertIsNotNone(failed.word_preview_state)

    def test_three_adapters_failed_preview_pending_is_retained_expired_and_cleaned(self):
        for kind in ("file", "sqlite", "mysql"):
            for file_type in ("word_preview_pdf", "word_preview_page", "word_preview_manifest"):
                with self.subTest(kind=kind, file_type=file_type), _repository(kind) as (_, build, __), TemporaryDirectory(prefix="rnd504-retention-") as directory:
                    files = build().document_file_repository
                    service = FileUploadService(Settings(_env_file=None, data_dir=directory), files)
                    original_update = files.update_document_file
                    recorded = []
                    write = service._write_object
                    main = _candidate("main")
                    files.create_document_file(main)
                    write(main, b"payload")

                    def confirm(file_id, **changes):
                        if files.get_document_file(file_id).file_type == file_type:
                            raise OSError("预览 metadata 确认失败")
                        return original_update(file_id, **changes)

                    def observed_write(record, content):
                        persisted = files.get_document_file(record.id)
                        self.assertEqual(persisted.status, "pending_upload")
                        self.assertEqual(persisted.metadata["word_preview_artifact_protocol"], 1)
                        recorded.append(persisted)
                        return write(record, content)

                    with patch.object(files, "update_document_file", side_effect=confirm), patch.object(service, "_write_object", side_effect=observed_write), self.assertRaises(OSError):
                        service.register_generated_content(tenant_id="tenant", company_id="company", job_id="job", created_by="operator",
                            file_type=file_type, filename="preview", mime_type="application/octet-stream", content=b"preview",
                            expires_at=utc_now() + timedelta(hours=1))
                    pending = recorded[0]
                    path = service.resolve_local_object_path(pending.object_key)
                    self.assertTrue(path.exists())
                    now = pending.expires_at + timedelta(seconds=1)
                    planner = DocumentFileRetentionPlanner(files, retention_days=1)
                    planner.mark_expired(now=now)
                    self.assertEqual(files.get_document_file(pending.id).status, "expired")
                    report = service.execute_retention_physical_delete([pending.id], reason="清理失败预览", confirmation=RETENTION_DELETE_CONFIRMATION_PHRASE, now=now)
                    self.assertEqual(report.totals["deleted"], 1)
                    self.assertFalse(path.exists())
                    self.assertEqual(files.get_document_file(pending.id).status, "deleted")
                    with self.assertRaises(ValueError): files.update_document_file(pending.id, status="uploaded")
                    self.assertEqual(files.get_document_file(main.id), main)
                    self.assertEqual(service.read_file_content(main), b"payload")

    def test_three_adapters_preview_upload_confirmation_loses_to_lifecycle(self):
        for kind in ("file", "sqlite", "mysql"):
            for transition in ("expired", "deleted", "elapsed"):
                with self.subTest(kind=kind, transition=transition), _repository(kind) as (_, build, __), TemporaryDirectory(prefix="rnd504-lifecycle-") as directory:
                    files = build().document_file_repository
                    service = FileUploadService(Settings(_env_file=None, data_dir=directory), files)
                    write = service._write_object
                    recorded = []

                    def lifecycle_then_write(record, content):
                        recorded.append(record)
                        if transition == "expired": files.expire_document_file(record.id, now=record.expires_at + timedelta(seconds=1))
                        elif transition == "deleted": files.update_document_file(record.id, status="deleted")
                        else: files.update_document_file(record.id, expires_at=utc_now() - timedelta(seconds=1))
                        return write(record, content)

                    with patch.object(service, "_write_object", side_effect=lifecycle_then_write), self.assertRaises(ValueError):
                        service.register_generated_content(tenant_id="tenant", company_id="company", job_id="job", created_by="operator",
                            file_type="word_preview_pdf", filename="preview.pdf", mime_type="application/pdf", content=b"preview")
                    persisted = files.get_document_file(recorded[0].id)
                    self.assertEqual(persisted.status, "pending_upload" if transition == "elapsed" else transition)
                    self.assertTrue(service.resolve_local_object_path(persisted.object_key).exists())

    def test_real_file_and_sqlite_processes_have_one_claim_winner(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        context = multiprocessing.get_context("spawn")
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), TemporaryDirectory(prefix="rnd504-cas-") as root:
                repo = _adapters(kind, Path(root)).document_job_repository
                job = prepared(repo)
                req = request(job)
                ready, output, start = context.Queue(), context.Queue(), context.Event()
                processes = [context.Process(target=process_claim, args=(kind, root, req.model_dump(mode="json"), ready, start, output)) for _ in range(2)]
                try:
                    for process in processes: process.start()
                    for _ in processes: self.assertTrue(ready.get(timeout=15))
                    start.set()
                    self.assertEqual(sorted(output.get(timeout=15) for _ in processes), ["busy", "claimed"])
                    for process in processes:
                        process.join(15)
                        self.assertEqual(process.exitcode, 0)
                    self.assertEqual(repo.get_document_job(job.id).word_preview_state.current_run.attempt_count, 1)
                finally:
                    for process in processes:
                        if process.is_alive(): process.terminate(); process.join(5)
                    ready.close(); output.close()

    def test_registration_marker_and_confirmation_are_attempt_scoped_in_all_adapters(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repo, build, _):
                job = prepared(repo, policy=PreviewPolicy(backend="sandboxed", max_attempts=2))
                req = request(job, "A", resume=True)
                first = repo.claim_document_job_preview(job.id, request=req)
                # 没有副作用前登记标记的finish必须拒绝。
                self.assertIsNone(repo.finish_document_job_preview(job.id, request=req,
                    revision=first.job.word_preview_state.revision, lease_token=first.lease_token,
                    status="failed", manifest_file_id="invented", error_code="preview_timeout", retryable=True, evidence={}))
                failed = finish(repo, first, req, retryable=True)
                self.assertEqual((failed.word_preview_state.current_run.artifact_stage,
                                  failed.word_preview_state.current_run.confirmed_attempt), ("confirmed", 1))
                second = repo.claim_document_job_preview(job.id, request=req)
                run = second.job.word_preview_state.current_run
                self.assertEqual((run.attempt_count, run.artifact_stage, run.confirmed_attempt, run.manifest_file_id),
                                 (2, "not_started", None, None))
                begun = repo.begin_document_job_preview_registration(job.id, request=req,
                    revision=second.job.word_preview_state.revision, lease_token=second.lease_token, attempt=2)
                self.assertEqual(begun.word_preview_state.current_run.artifact_stage, "registering")
                future = run.lease_expires_at + timedelta(milliseconds=1)
                with patch(f"app.infrastructure.persistence.{kind}.document_jobs.utc_now", return_value=future):
                    recovered = build().document_job_repository.claim_document_job_preview(job.id, request=req)
                    replay = repo.claim_document_job_preview(job.id, request=req)
                for result in (recovered, replay):
                    self.assertEqual(result.disposition, "storage_failed")
                    self.assertEqual(result.job.quality_status, "blocked")
                    self.assertEqual(result.run.attempt_count, 2)
                    self.assertIsNone(result.run.confirmed_attempt)

    def test_missing_inflight_stage_is_unknown_and_not_a_provider_retry(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repo, _, __):
                job = prepared(repo)
                req = request(job, "A")
                claim = repo.claim_document_job_preview(job.id, request=req)
                state = claim.job.word_preview_state.model_copy(deep=True)
                state.current_run.artifact_stage = None
                repo.update_document_job(job.id, word_preview_state=state)
                future = state.current_run.lease_expires_at + timedelta(milliseconds=1)
                with patch(f"app.infrastructure.persistence.{kind}.document_jobs.utc_now", return_value=future):
                    result = repo.claim_document_job_preview(job.id, request=req)
                self.assertEqual((result.disposition, result.run.attempt_count), ("storage_failed", 1))

    def test_reuse_observation_cas_rejects_changed_revision_current_manifest_and_expiry(self):
        from dataclasses import replace
        for kind in ("file", "sqlite", "mysql"):
            for change in ("revision", "current", "manifest", "expiry", "absent"):
                with self.subTest(kind=kind, change=change), _repository(kind) as (repo, _, __):
                    job = prepared(repo)
                    req = request(job, "A")
                    selected = finish(repo, repo.claim_document_job_preview(job.id, request=req), req, success=True)
                    observed = observation(selected)
                    if change == "expiry":
                        observed = replace(observed, earliest_expires_at=utc_now() - timedelta(seconds=1))
                    elif change == "absent":
                        observed = None
                    else:
                        state = selected.word_preview_state.model_copy(deep=True)
                        if change == "revision":
                            state.revision += 1
                        elif change == "manifest":
                            state.current_run.manifest_file_id = "other-manifest"
                        else:
                            state.runs_by_request_key["C"] = state.current_run.model_copy(deep=True)
                            state.current_request_key = "C"
                        repo.update_document_job(job.id, word_preview_state=state)
                    before = repo.get_document_job(job.id)
                    result = repo.claim_document_job_preview(job.id, request=request(job, "B"), observation=observed)
                    self.assertEqual(result.disposition, "stale")
                    self.assertEqual(repo.get_document_job(job.id), before)
                    self.assertNotIn("B", result.job.word_preview_state.runs_by_request_key)

    def test_invalid_lifecycle_observation_creates_blocked_new_run_without_resetting_cap(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repo, _, __):
                job = prepared(repo, quality="passed", policy=PreviewPolicy(backend="sandboxed", max_runs_per_result=2))
                a = request(job, "A")
                selected = finish(repo, repo.claim_document_job_preview(job.id, request=a), a, success=True)
                repo.update_document_job(job.id, review_status="approved", delivery_status="ready_to_publish")
                b = request(job, "B")
                claimed = repo.claim_document_job_preview(job.id, request=b, observation=observation(selected, available=False))
                self.assertEqual(claimed.disposition, "claimed")
                self.assertNotEqual(claimed.run.run_id, selected.word_preview_state.current_run.run_id)
                self.assertEqual((claimed.job.quality_status, claimed.job.review_status, claimed.job.delivery_status),
                                 ("blocked", "unreviewed", "internal_draft"))
                recovered = finish(repo, claimed, b, success=True)
                self.assertEqual(recovered.quality_status, "passed")
                with self.assertRaisesRegex(ValueError, "上限"):
                    repo.claim_document_job_preview(job.id, request=request(job, "C"), observation=observation(recovered))
                replay = repo.claim_document_job_preview(job.id, request=a)
                self.assertEqual(replay.disposition, "historical")
                self.assertEqual(replay.run.run_id, selected.word_preview_state.current_run.run_id)
                self.assertEqual(replay.job.word_preview_state.current_request_key, "B")
