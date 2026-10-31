"""三 adapter 共用的预览领取/完成纯规则；外部 I/O 必须在 job 锁外。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, TYPE_CHECKING, get_args
import re
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictInt
from app.services.preview.models import PreviewPolicy, PreviewErrorCode, SHA256_PATTERN
from app.domains.files.models import DocumentFileRecord

if TYPE_CHECKING:
    from app.domains.document_jobs.models import DocumentJobRecord


class PreviewRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    request_fingerprint: str = Field(pattern=SHA256_PATTERN)
    requested_by: str
    reason_sha256: str = Field(pattern=SHA256_PATTERN)
    status: Literal["pending", "running", "succeeded", "failed", "unavailable"] = "pending"
    attempt_count: StrictInt = Field(default=0, ge=0)
    max_attempts: StrictInt = Field(ge=1)
    next_retry_at: datetime | None = None
    run_deadline_at: datetime
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    manifest_file_id: str | None = None
    error_code: PreviewErrorCode | None = None
    retryable: bool = False
    started_at: datetime
    completed_at: datetime | None = None
    artifact_stage: Literal["not_started", "registering", "confirmed"] | None = None
    confirmed_attempt: StrictInt | None = Field(default=None, ge=1)


class WordPreviewState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["word-preview-state/v1"] = "word-preview-state/v1"
    source_generation: StrictInt = Field(ge=0)
    source_result_file_id: str
    source_docx_sha256: str = Field(pattern=SHA256_PATTERN)
    profile_id: str
    profile_sha256: str = Field(pattern=SHA256_PATTERN)
    revision: StrictInt = Field(default=0, ge=0)
    current_request_key: str
    max_runs_per_result: StrictInt = Field(ge=1)
    runs_by_request_key: dict[str, PreviewRun] = Field(default_factory=dict)

    @property
    def current_run(self) -> PreviewRun:
        return self.runs_by_request_key[self.current_request_key]


class PreviewClaimRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    generation: StrictInt = Field(ge=0)
    result_file_id: str
    docx_sha256: str = Field(pattern=SHA256_PATTERN)
    policy: PreviewPolicy
    page_quality_policy_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    page_quality_context_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    request_key: str
    request_fingerprint: str = Field(pattern=SHA256_PATTERN)
    requested_by: str
    reason_sha256: str = Field(pattern=SHA256_PATTERN)
    independent: bool = False
    resume: bool = False


@dataclass(frozen=True)
class PreviewArtifactObservation:
    """应用锁外核验的完整证据，绑定当时的当前选择；不接受外部请求构造。"""

    source_generation: int
    source_result_file_id: str
    source_docx_sha256: str
    profile_id: str
    profile_sha256: str
    revision: int
    current_request_key: str
    run_id: str
    attempt: int
    manifest_file_id: str
    files: tuple[DocumentFileRecord, ...]
    earliest_expires_at: datetime
    available: bool
    page_quality_policy_sha256: str | None = None
    page_quality_run_sha256: str | None = None
    page_quality_reusable: bool | None = None

    def matches(self, state: WordPreviewState, now: datetime) -> bool:
        return (
            (self.source_generation, self.source_result_file_id, self.source_docx_sha256,
             self.profile_id, self.profile_sha256, self.revision, self.current_request_key,
             self.run_id, self.attempt, self.manifest_file_id)
            == (state.source_generation, state.source_result_file_id, state.source_docx_sha256,
                state.profile_id, state.profile_sha256, state.revision, state.current_request_key,
                state.current_run.run_id, state.current_run.attempt_count, state.current_run.manifest_file_id)
            and self.earliest_expires_at > now
        )


@dataclass(frozen=True)
class PreviewClaim:
    job: DocumentJobRecord
    disposition: Literal["claimed", "finalizing", "busy", "historical", "reused", "stale", "storage_failed"]
    lease_token: str | None = None
    run: PreviewRun | None = None


@dataclass(frozen=True)
class PreviewRetryResult:
    """job 保留最新选择，run 对应本次 request ID 的历史记录。"""

    job: DocumentJobRecord
    run: PreviewRun | None
    available: bool = False


def page_quality_context_sha256(job: Any, *, authenticated_plan=None, require_authenticated=False) -> str | None:
    """将实际任务版式与已选凭据的资源指纹绑定；历史缺证据保持未知。"""
    from app.services.renderer.render_plan import read_render_plan, content_hash
    from pydantic import ValidationError
    receipt = job.prepared_result
    if receipt is None or receipt.file.metadata.get("render_trace_status") != "complete":
        return None
    metadata = receipt.file.metadata
    if require_authenticated:
        plan = authenticated_plan
        if plan is None:
            return None
    else:
        try:
            plan = read_render_plan(metadata.get("render_plan"))
        except (ValidationError, ValueError, TypeError):
            return None
    context = {"template_version_id": job.template_version_id, "mode": job.mode,
        "document_language": job.document_language, "resource_identity": plan.resource_identity.model_dump(mode="json")}
    if plan.schema_version == "render-plan/v1":
        if "renderer_content_contract_version" in metadata or "formula_source_coverage" in metadata:
            return None
        # 历史校准的 canonical 输入保持逐字相同，不追溯增加版本字段。
        return content_hash(context)
    if metadata.get("renderer_content_contract_version") != "renderer-content/v2":
        return None
    return content_hash({"schema_version": "page-quality-context/v2",
        "renderer_content_contract_version": "renderer-content/v2",
        "renderer_policy_version": plan.renderer_policy_version, **context})


def matches_source(job: Any, request: PreviewClaimRequest, now: datetime) -> bool:
    receipt = job.prepared_result
    from app.services.preview.page_quality import parse_page_quality_policy, policy_sha256
    raw_quality = job.request_snapshot.get("page_quality")
    try:
        quality = parse_page_quality_policy(raw_quality) if "page_quality" in job.request_snapshot else None
    except ValueError:
        return False
    frozen_hash = policy_sha256(quality) if quality is not None and quality.enabled else None
    return bool(
        frozen_hash == request.page_quality_policy_sha256
        and (frozen_hash is None or request.page_quality_context_sha256 == page_quality_context_sha256(job)) and
        job.retry_count == request.generation and receipt is not None
        and receipt.file.id == request.result_file_id and receipt.file.checksum_sha256 == request.docx_sha256
        and receipt.generation == request.generation and receipt.file.expires_at is not None
        and receipt.file.expires_at > now and job.deleted_at is None and job.archived_at is None
        and job.delivery_status != "published"
        and ((job.status == "succeeded" and job.stage == "completed" and job.result_file_id == request.result_file_id)
             if request.independent else (job.status == "running" and job.stage == "uploading"
                                         and (job.timeout_at is None or job.timeout_at > now)))
        and job.request_snapshot.get("word_preview") == request.policy.model_dump(mode="json")
    )


def claim_preview(
    job: DocumentJobRecord, request: PreviewClaimRequest, *, now: datetime,
    observation: PreviewArtifactObservation | None = None,
) -> PreviewClaim:
    from app.domains.document_jobs.result_state import patched_job

    if not matches_source(job, request, now):
        return PreviewClaim(job, "stale")
    state = job.word_preview_state.model_copy(deep=True) if job.word_preview_state else None
    if state is not None and (
        state.source_generation, state.source_result_file_id, state.source_docx_sha256, state.profile_id, state.profile_sha256
    ) != (request.generation, request.result_file_id, request.docx_sha256, request.policy.profile_id, request.policy.profile_sha256):
        return PreviewClaim(job, "stale")
    if state is None:
        state = WordPreviewState(source_generation=request.generation, source_result_file_id=request.result_file_id,
            source_docx_sha256=request.docx_sha256, profile_id=request.policy.profile_id,
            profile_sha256=request.policy.profile_sha256, current_request_key=request.request_key,
            max_runs_per_result=request.policy.max_runs_per_result)
    existing = state.runs_by_request_key.get(request.request_key)
    recovering_lifecycle = False
    if existing is not None:
        if existing.request_fingerprint != request.request_fingerprint:
            raise ValueError("预览 request ID 已使用且参数不一致。")
        if state.current_request_key != request.request_key:
            disposition = "historical" if _confirmed(existing) else "storage_failed"
            return PreviewClaim(job, disposition, run=existing)
    # 旧current终态先核验再确认，初始key也能由新UUID复用；在途缺字段仍是未知。
    legacy_confirmed = False
    if state.runs_by_request_key:
        current = state.current_run
        if (current.artifact_stage is None and current.status in {"succeeded", "failed", "unavailable"}
                and observation is not None and observation.available and observation.matches(state, now)):
            current.artifact_stage, current.confirmed_attempt = "confirmed", current.attempt_count
            legacy_confirmed = True
            # 此处不递增revision；后续alias/claim与确认同锁一次提交，仍比较原观测revision。
    if existing is not None:
        run = existing
        if _confirmed(run) and (run.status == "succeeded" or not request.resume or not run.retryable):
            if legacy_confirmed:
                state.revision += 1
                job = patched_job(job, {"word_preview_state": state, "updated_at": now})
            return PreviewClaim(job, "historical", run=run)
    else:
        if state.runs_by_request_key:
            current = state.current_run
            if current.status == "running" and current.lease_expires_at is not None and current.lease_expires_at > now:
                return PreviewClaim(job, "busy")
            if not _confirmed(current):
                return _storage_failure(job, state, now)
        if len(state.runs_by_request_key) >= state.max_runs_per_result:
            raise ValueError("当前主件的预览重试请求已达上限。")
        if state.runs_by_request_key and state.current_run.status == "succeeded":
            if observation is None or not observation.matches(state, now):
                return PreviewClaim(job, "stale")
            if (request.page_quality_policy_sha256 is not None and observation.available
                    and observation.page_quality_reusable is None):
                return PreviewClaim(job, "stale")
            reusable_quality = (request.page_quality_policy_sha256 is None or (
                observation.page_quality_policy_sha256 == request.page_quality_policy_sha256
                and observation.page_quality_reusable is True
                and observation.page_quality_run_sha256 is not None
                and observation.page_quality_run_sha256 == job.quality_summary.get("checks_v1", {}).get(
                    "word_page_quality", {}).get("run_sha256")))
            if observation.available and reusable_quality:
                # 复用消费key但不改变current、实际run和attempt。
                alias = state.current_run.model_copy(deep=True, update={
                    "request_fingerprint": request.request_fingerprint, "requested_by": request.requested_by,
                    "reason_sha256": request.reason_sha256,
                })
                state.runs_by_request_key[request.request_key] = alias
                state.revision += 1
                updated = patched_job(job, {"word_preview_state": state, "updated_at": now})
                return PreviewClaim(updated, "reused", run=alias)
            recovering_lifecycle = True
        deadline = now + timedelta(seconds=request.policy.deadline_seconds)
        if (recovering_lifecycle and observation is not None and observation.available
                and request.page_quality_policy_sha256 is not None):
            # 缺报告恢复不借新 UUID 重置旧质量运行的剩余 deadline。
            deadline = min(deadline, state.current_run.run_deadline_at)
            if deadline <= now:
                raise ValueError("当前页面质量恢复窗口已过期。")
        if not request.independent and job.timeout_at is not None:
            deadline = min(deadline, job.timeout_at)
        run = PreviewRun(run_id=uuid4().hex, request_fingerprint=request.request_fingerprint,
            requested_by=request.requested_by, reason_sha256=request.reason_sha256,
            max_attempts=request.policy.max_attempts, run_deadline_at=deadline, started_at=now,
            artifact_stage="not_started")
        state.current_request_key = request.request_key
        state.runs_by_request_key[request.request_key] = run
    if run.status == "running" and run.lease_expires_at is not None and run.lease_expires_at > now:
        return PreviewClaim(job, "busy")
    if run.artifact_stage not in {"not_started", "confirmed"}:
        return _storage_failure(job, state, now)
    if run.run_deadline_at <= now:
        if _confirmed(run):
            run.retryable = False
            state.revision += 1
            updated = patched_job(job, {"word_preview_state": state, "updated_at": now})
            return PreviewClaim(updated, "historical", run=run)
        return _storage_failure(job, state, now)
    if run.next_retry_at is not None and run.next_retry_at > now:
        return PreviewClaim(job, "busy")
    finalizing = run.attempt_count >= run.max_attempts
    if not finalizing:
        run.attempt_count += 1
    # 每个新attempt清掉旧manifest，旧attempt不能为本次登记提供完成证明。
    run.status, run.artifact_stage, run.confirmed_attempt = "running", "not_started", None
    run.manifest_file_id = None
    run.lease_token = uuid4().hex
    run.lease_expires_at = min(run.run_deadline_at, now + timedelta(seconds=request.policy.timeout_seconds + 2))
    run.next_retry_at, run.completed_at = None, None
    state.revision += 1
    contribution = preview_summary(state, quality_status="blocked") if recovering_lifecycle else None
    page_contribution = None
    if request.page_quality_policy_sha256 is not None:
        previous = job.quality_summary.get("checks_v1", {}).get("word_page_quality", {})
        page_contribution = page_quality_pending(state, request, quality_status=(
            "blocked" if previous.get("quality_status") == "blocked" else "pending"))
    patch = {"word_preview_state": state, "updated_at": now}
    if recovering_lifecycle or (page_contribution is not None and job.review_status == "approved"):
        patch.update(review_status="unreviewed", delivery_status="internal_draft")
    updated = patched_job(job, patch, preview_contribution=contribution,
                          page_quality_contribution=page_contribution)
    return PreviewClaim(updated, "finalizing" if finalizing else "claimed", run.lease_token, run)


def _confirmed(run: PreviewRun) -> bool:
    return (run.artifact_stage == "confirmed" and run.confirmed_attempt == run.attempt_count
            and run.manifest_file_id is not None)


def _storage_failure(job: DocumentJobRecord, state: WordPreviewState, now: datetime) -> PreviewClaim:
    from app.domains.document_jobs.result_state import patched_job

    run = state.current_run
    run.status, run.retryable, run.error_code = "failed", False, "preview_storage_failed"
    run.lease_token, run.lease_expires_at = None, None
    state.revision += 1
    updated = patched_job(job, {"word_preview_state": state, "updated_at": now},
                          preview_contribution=preview_summary(state, quality_status="blocked"))
    return PreviewClaim(updated, "storage_failed", run=run)


def _active_state(job, request, *, revision, lease_token, now):
    if not matches_source(job, request, now) or job.word_preview_state is None:
        return None
    state = job.word_preview_state.model_copy(deep=True)
    if (state.revision != revision or state.current_request_key != request.request_key
            or (state.source_generation, state.source_result_file_id, state.source_docx_sha256,
                state.profile_id, state.profile_sha256) != (request.generation, request.result_file_id,
                request.docx_sha256, request.policy.profile_id, request.policy.profile_sha256)):
        return None
    run = state.current_run
    if (run.status != "running" or run.request_fingerprint != request.request_fingerprint or run.lease_token != lease_token
            or run.lease_expires_at is None or run.lease_expires_at <= now or run.run_deadline_at <= now):
        return None
    return state


def begin_preview_registration(job, request, *, revision, lease_token, attempt, now):
    """任何Artifact副作用前持久化阶段；迟到token不能开始写文件。"""
    from app.domains.document_jobs.result_state import patched_job

    state = _active_state(job, request, revision=revision, lease_token=lease_token, now=now)
    if state is None or state.current_run.attempt_count != attempt or state.current_run.artifact_stage != "not_started":
        return None
    state.current_run.artifact_stage = "registering"
    state.revision += 1
    return patched_job(job, {"word_preview_state": state, "updated_at": now})


def preview_summary(state: WordPreviewState, *, quality_status: str, **evidence: Any) -> dict:
    run = state.current_run
    return {"quality_status": quality_status, "status": run.status,
            "source_generation": state.source_generation, "source_result_file_id": state.source_result_file_id,
            "source_docx_sha256": state.source_docx_sha256, "profile_id": state.profile_id,
            "profile_sha256": state.profile_sha256, "run_id": run.run_id, "attempt": run.attempt_count,
            "manifest_file_id": run.manifest_file_id, "error_code": run.error_code, **evidence}


def page_quality_pending(state, request, *, quality_status="pending"):
    """身份从锁内当前 receipt/run 派生，摘要不接受调用方自由覆盖。"""
    run = state.current_run
    return {"quality_status": quality_status, "evaluation_state": "incomplete",
            "source_generation": state.source_generation, "source_result_file_id": state.source_result_file_id,
            "source_docx_sha256": state.source_docx_sha256, "profile_id": state.profile_id,
            "profile_sha256": state.profile_sha256, "run_id": run.run_id, "attempt": run.attempt_count,
            "policy_sha256": request.page_quality_policy_sha256, "manifest_file_id": run.manifest_file_id}


def finish_preview(job: DocumentJobRecord, request: PreviewClaimRequest, *, revision: int, lease_token: str,
                   status: Literal["succeeded", "failed", "unavailable"], manifest_file_id: str,
                   error_code: PreviewErrorCode | None, retryable: bool, evidence: dict, now: datetime,
                   page_quality_contribution: dict | None = None) -> DocumentJobRecord | None:
    from app.domains.document_jobs.result_state import patched_job

    state = _active_state(job, request, revision=revision, lease_token=lease_token, now=now)
    if state is None or state.current_run.artifact_stage != "registering":
        return None
    run = state.current_run
    allowed_evidence = {"provider_id", "provider_version", "page_count", "pdf_file_id", "page_file_ids"}
    if set(evidence) - allowed_evidence or (status == "succeeded") != (error_code is None):
        raise ValueError("预览完成证据或错误状态不一致。")
    if request.page_quality_policy_sha256 is None and page_quality_contribution is not None:
        raise ValueError("未启用的任务不能提交页面质量贡献。")
    page_contribution = None
    if request.page_quality_policy_sha256 is not None:
        page_contribution = page_quality_pending(state, request)
        if status == "succeeded" and page_quality_contribution is None:
            raise ValueError("成功预览必须显式提交已认证的页面质量贡献。")
        if page_quality_contribution is not None:
            expected = {"source_generation": state.source_generation,
                "source_result_file_id": state.source_result_file_id, "source_docx_sha256": state.source_docx_sha256,
                "profile_id": state.profile_id, "profile_sha256": state.profile_sha256,
                "run_id": run.run_id, "attempt": run.attempt_count,
                "policy_sha256": request.page_quality_policy_sha256, "manifest_file_id": manifest_file_id}
            if any(page_quality_contribution.get(key) != value for key, value in expected.items()):
                raise ValueError("页面质量贡献与当前预览身份不一致。")
            allowed_page = set(expected) | {"quality_status", "evaluation_state", "run_sha256", "summary"}
            if (set(page_quality_contribution) - allowed_page or status != "succeeded"
                    or page_quality_contribution.get("quality_status") not in {"pending", "passed", "warning"}):
                raise ValueError("页面质量贡献字段或状态无效。")
            safe_summary = page_quality_contribution.get("summary")
            summary_keys = {"schema_version", "evaluation_state", "quality_status", "reason_code", "counts"}
            count_keys = {"pages", "observed_pages", "flags", "manual_checks", "checked_rules", "not_checked_rules"}
            if (not isinstance(safe_summary, dict) or set(safe_summary) != summary_keys
                    or safe_summary.get("schema_version") != "page-quality-run/v1"
                    or safe_summary.get("quality_status") != page_quality_contribution["quality_status"]
                    or safe_summary.get("evaluation_state") != page_quality_contribution.get("evaluation_state")
                    or safe_summary.get("evaluation_state") not in {"complete", "incomplete"}
                    or not isinstance(safe_summary.get("counts"), dict) or set(safe_summary["counts"]) != count_keys
                    or any(type(value) is not int or value < 0 for value in safe_summary["counts"].values())):
                raise ValueError("页面质量摘要不是受控有界投影。")
            from app.services.preview.page_quality import HASH_PATTERN, Reason
            if (safe_summary.get("reason_code") not in (None, *get_args(Reason))
                    or not isinstance(page_quality_contribution.get("run_sha256"), str)
                    or not re.fullmatch(HASH_PATTERN, page_quality_contribution["run_sha256"])):
                raise ValueError("页面质量摘要 hash 或原因码无效。")
            page_contribution = page_quality_contribution
        page_contribution = {**page_contribution, "manifest_file_id": manifest_file_id}
    run.status, run.manifest_file_id, run.error_code = status, manifest_file_id, error_code
    run.artifact_stage, run.confirmed_attempt = "confirmed", run.attempt_count
    run.retryable = (retryable and error_code in {"preview_timeout", "preview_engine_failed"}
                     and run.attempt_count < run.max_attempts and run.run_deadline_at > now)
    run.lease_token, run.lease_expires_at, run.completed_at = None, None, now
    run.next_retry_at = now if run.retryable else None
    state.revision += 1
    quality_status = "passed" if status == "succeeded" else (
        "pending" if error_code == "preview_disabled" and not request.policy.required else "blocked")
    return patched_job(job, {"word_preview_state": state, "updated_at": now},
                       preview_contribution=preview_summary(state, quality_status=quality_status, **evidence),
                       page_quality_contribution=page_contribution)


def current_preview_ids(job: Any) -> set[str]:
    """供列表和 Token 读取共同使用；部分输出不能通过同代 fallback 获权。"""
    state = job.word_preview_state
    receipt = job.prepared_result
    if (state is None or receipt is None or job.status != "succeeded" or job.stage != "completed"
            or job.deleted_at is not None or state.source_generation != job.retry_count
            or state.source_result_file_id != job.result_file_id or receipt.file.id != job.result_file_id
            or state.source_docx_sha256 != receipt.file.checksum_sha256):
        return set()
    run = state.current_run
    summary = job.quality_summary.get("checks_v1", {}).get("word_preview", {})
    if (not _confirmed(run) or run.status == "running" or summary.get("manifest_file_id") != run.manifest_file_id
            or summary.get("run_id") != run.run_id or summary.get("profile_sha256") != state.profile_sha256):
        return set()
    ids = {run.manifest_file_id}
    if run.status == "succeeded":
        ids.update([summary.get("pdf_file_id"), *summary.get("page_file_ids", [])])
    return {value for value in ids if isinstance(value, str)}
