from __future__ import annotations

# app/domains/jobs/stage.py: 驱动后台 stage 执行，并通过集中 workflow 规则推进 job 状态。

import logging
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Callable
from uuid import uuid4

from app.clients.mineru_client import MinerUClient
from app.conversion.contracts import ConversionEntrypoint, ConversionFailure
from app.conversion.entrypoint import build_job_conversion_request
from app.core.config import Settings
from app.domains.jobs.workflow import (
    JobWorkflowViolation,
    build_conversion_completed_transition,
    build_conversion_failed_transition,
    build_conversion_started_transition,
    build_mineru_callback_transition,
    build_mineru_result_polled_intent,
    build_parsed_result_conversion_failed_transition,
    build_parsed_result_package_recovered_intent,
    build_parsed_result_conversion_started_transition,
    build_mineru_submission_failed_transition,
    build_mineru_submission_started_transition,
    build_mineru_submission_succeeded_transition,
    build_stage_enqueue_transition,
    build_translation_completed_intent,
    build_translation_started_intent,
    describe_applied_stage,
)
from app.domains.jobs.models import ConversionOptions, JobRecord, JobStageMessage, JobStageName, utc_now
from app.domains.jobs.paths import build_job_paths
from app.domains.jobs.mineru_callback import validate_mineru_result_url
from app.domains.translation.models import TranslationProfileSnapshot
from app.domains.jobs.repository import (
    JobEventRepositoryProtocol,
    JobFileRepositoryProtocol,
    JobSnapshotRepositoryProtocol,
    StageMessageStoreProtocol,
)
from app.domains.jobs.artifact_storage import ArtifactStorageProtocol
from app.domains.jobs.resource_snapshots import JobResourceSnapshotError, JobResourceSnapshotService
from app.domains.jobs.workflow_events import build_job_event_from_intent


class JobStageService:
    """后台 stage driver，负责分派消息并协调 workflow、provider 与 conversion handler。

    职责边界：
    - workflow rule: `app.domains.jobs.workflow`
    - stage message 状态写入: `_mark_stage_running` / `_mark_stage_failed` / `_delete_stage_message`
    - MinerU provider 调用: `_submit_pdf_to_mineru` / `_download_mineru_result_package`
    - conversion 执行: `_run_conversion_pipeline`
    """

    def __init__(
        self,
        settings: Settings,
        job_repository: JobSnapshotRepositoryProtocol,
        job_file_repository: JobFileRepositoryProtocol,
        job_event_repository: JobEventRepositoryProtocol,
        conversion_entrypoint: ConversionEntrypoint,
        artifact_storage: ArtifactStorageProtocol,
        *,
        stage_message_store: StageMessageStoreProtocol,
        stage_worker_id: str = "in_process",
        mineru_client_factory: Callable[[], MinerUClient] | None = None,
        resolve_template_path: Callable[[str | None], Path | None] | None = None,
        resolve_subscript_config_path: Callable[[], Path | None] | None = None,
        resolve_translation_profile_snapshot: Callable[[], TranslationProfileSnapshot | None] | None = None,
        resource_snapshot_service: JobResourceSnapshotService | None = None,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.job_file_repository = job_file_repository
        self.job_event_repository = job_event_repository
        self.stage_message_store = stage_message_store
        self.stage_worker_id = stage_worker_id
        self.conversion_entrypoint = conversion_entrypoint
        self.artifact_storage = artifact_storage
        self._custom_mineru_client_factory = mineru_client_factory
        self.mineru_client_factory = mineru_client_factory or self._build_mineru_client
        self.resolve_template_path = resolve_template_path or (lambda _template_id: self.settings.default_template_path)
        self.resolve_subscript_config_path = resolve_subscript_config_path or (lambda: self.settings.subscript_config_path)
        self.resolve_translation_profile_snapshot = resolve_translation_profile_snapshot or (lambda: None)
        self.resource_snapshot_service = resource_snapshot_service
        self.logger = logging.getLogger("business")

    def enqueue_conversion(self, job: JobRecord, options: ConversionOptions, trace_id: str) -> JobStageMessage:
        return self._enqueue_stage(
            job=job,
            stage="convert_package",
            trace_id=trace_id,
            event_message="转换任务已进入后台队列。",
            event_details=options.model_dump(mode="json"),
        )

    def enqueue_mineru_submission(self, job: JobRecord, options: ConversionOptions, trace_id: str) -> JobStageMessage:
        return self._enqueue_stage(
            job=job,
            stage="submit_to_mineru",
            trace_id=trace_id,
            event_message="PDF 任务已进入 MinerU 提交队列。",
            event_details={**options.model_dump(mode="json"), "source_kind": "source_pdf"},
        )

    def enqueue_process_callback(self, job: JobRecord, payload: dict, trace_id: str) -> JobStageMessage:
        message = JobStageMessage(
            id=f"msg_{uuid4().hex[:12]}",
            job_id=job.id,
            stage="process_callback",
            trace_id=trace_id,
            payload=payload,
        )
        self.stage_message_store.put_stage_message(message)
        return message

    def enqueue_mineru_result_recovery(self, job: JobRecord, trace_id: str) -> JobStageMessage:
        """主动查询 MinerU 批量结果，并复用 callback stage 完成后续恢复。"""

        payload = self._query_mineru_result_payload(job)
        self._append_intent_events(
            job.id,
            (build_mineru_result_polled_intent(payload),),
            trace_id=trace_id,
        )
        return self.enqueue_process_callback(job, payload, trace_id)

    def enqueue_parsed_result_conversion(self, job: JobRecord, trace_id: str) -> JobStageMessage:
        return self._enqueue_stage(
            job=job,
            stage="convert_parsed_result",
            trace_id=trace_id,
            event_message="parsed 结果已进入在线后处理队列。",
            event_details={"source_kind": "source_pdf", "from_lifecycle_status": job.resolved_lifecycle_status()},
        )

    def dispatch_message(self, message_id: str) -> None:
        message = self.stage_message_store.get_stage_message(message_id)
        if message is None:
            return

        job = self.job_repository.get_job(message.job_id)
        if job is None or job.status == "canceled":
            self._delete_stage_message(message_id)
            return
        if self._delete_if_stage_already_applied(job, message):
            return

        if message.stage == "submit_to_mineru":
            self._dispatch_submit_to_mineru(job, message)
            return
        if message.stage == "process_callback":
            self._dispatch_process_callback(job, message)
            return
        if message.stage == "convert_package":
            self._dispatch_convert_package(job, message)
            return
        if message.stage == "convert_parsed_result":
            self._dispatch_convert_parsed_result(job, message)
            return

        self._delete_stage_message(message_id)

    def replay_pending(self) -> None:
        for message in self.stage_message_store.list_replayable_stage_messages():
            self.dispatch_message(message.id)

    def _enqueue_stage(
        self,
        *,
        job: JobRecord,
        stage: JobStageName,
        trace_id: str,
        event_message: str,
        event_details: dict,
    ) -> JobStageMessage:
        message = JobStageMessage(
            id=f"msg_{uuid4().hex[:12]}",
            job_id=job.id,
            stage=stage,
            trace_id=trace_id,
        )
        self.stage_message_store.put_stage_message(message)
        transition = build_stage_enqueue_transition(job, stage=stage)
        updated_job = self._apply_transition(
            job,
            transition,
            extra_updates={"updated_at": utc_now()},
        )
        self._append_intent_events(
            job.id,
            transition.event_intents,
            trace_id=trace_id,
            overrides_by_kind={
                "stage_enqueued": {
                    "message": event_message,
                    "details": event_details,
                }
            },
        )
        return message

    def _append_intent_events(
        self,
        job_id: str,
        intents: tuple,
        *,
        trace_id: str,
        overrides_by_kind: dict[str, dict] | None = None,
    ) -> None:
        """把领域事件意图统一映射为持久化 JobEvent。"""

        overrides = overrides_by_kind or {}
        for intent in intents:
            event = build_job_event_from_intent(
                intent,
                trace_id=trace_id,
                **overrides.get(intent.kind, {}),
            )
            self.job_event_repository.append_event(job_id, event)

    def _apply_transition(
        self,
        job: JobRecord,
        transition,
        *,
        extra_updates: dict | None = None,
    ) -> JobRecord:
        """统一写入 job transition，避免每个 stage 手工拼 patch。"""

        return self.job_repository.update_job(
            job.id,
            **(extra_updates or {}),
            **transition.as_job_update_patch(job),
        )

    def _handle_stage_failure(
        self,
        *,
        job: JobRecord,
        message: JobStageMessage,
        transition,
        error_code: str,
        error_message: str,
        event_overrides: dict[str, dict],
    ) -> None:
        """统一处理失败场景的 job patch、stage failure、事件落盘和日志。"""

        updated_job = self._apply_transition(
            job,
            transition,
            extra_updates={"updated_at": utc_now()},
        )
        self._mark_stage_failed(message, error_code=error_code, error_message=error_message)
        self._append_intent_events(
            job.id,
            transition.event_intents,
            trace_id=message.trace_id,
            overrides_by_kind=event_overrides,
        )
        self._log_stage_failure(message, job.id, error_message)

    def _mark_stage_running(self, message: JobStageMessage) -> None:
        now = utc_now()
        self.stage_message_store.update_stage_message(
            message.id,
            status="running",
            attempts=message.attempts + 1,
            lease_owner=self.stage_worker_id,
            leased_at=now,
            lease_expires_at=now + timedelta(seconds=self.settings.stage_message_lease_seconds),
            updated_at=now,
            error_code=None,
            error_message=None,
        )

    def _mark_stage_failed(self, message: JobStageMessage, *, error_code: str, error_message: str) -> None:
        self.stage_message_store.update_stage_message(
            message.id,
            status="failed",
            updated_at=utc_now(),
            lease_owner=None,
            leased_at=None,
            lease_expires_at=None,
            error_code=error_code,
            error_message=error_message,
        )

    def _delete_stage_message(self, message_id: str) -> None:
        self.stage_message_store.delete_stage_message(message_id)

    def _log_stage_failure(self, message: JobStageMessage, job_id: str, error_message: str) -> None:
        self.logger.exception(
            "[trace_id=%s job_id=%s stage=%s message_id=%s status=failed] %s",
            message.trace_id,
            job_id,
            message.stage,
            message.id,
            error_message,
        )

    def _delete_if_stage_already_applied(self, job: JobRecord, message: JobStageMessage) -> bool:
        """删除已被 job 状态覆盖的遗留 stage message，避免 replay 重复副作用。"""

        skip_reason = describe_applied_stage(job, stage=message.stage)
        if skip_reason is None:
            return False
        self._delete_stage_message(message.id)
        self.logger.info(
            "[trace_id=%s job_id=%s stage=%s message_id=%s status=skipped] reason=%s",
            message.trace_id,
            job.id,
            message.stage,
            message.id,
            skip_reason,
        )
        return True

    def _dispatch_convert_package(self, job: JobRecord, message: JobStageMessage) -> None:
        self._mark_stage_running(message)
        transition = build_conversion_started_transition(job)
        self._apply_transition(
            job,
            transition,
            extra_updates={
                "started_at": job.started_at or utc_now(),
                "updated_at": utc_now(),
            },
        )
        self._append_intent_events(
            job.id,
            transition.event_intents,
            trace_id=message.trace_id,
        )

        self._run_conversion_pipeline(
            job,
            message,
            package_path=build_job_paths(self.settings.data_path, job.id).source_package,
        )

    def _run_conversion_pipeline(
        self,
        job: JobRecord,
        message: JobStageMessage,
        *,
        package_path: Path,
    ) -> None:
        """执行共享 conversion pipeline，供 convert_package 与 convert_parsed_result 复用。"""

        job_paths = build_job_paths(self.settings.data_path, job.id)
        try:
            if job.resource_snapshot is not None and self.resource_snapshot_service is None:
                raise JobResourceSnapshotError(
                    "当前 stage runtime 缺少 resource snapshot service。",
                    status_code=503,
                    code="resource_snapshot_unavailable",
                )
            materialized_resources = (
                self.resource_snapshot_service.materialize(job, job_paths)
                if job.resource_snapshot is not None
                else None
            )
            translation_profile = (
                materialized_resources.translation_profile
                if materialized_resources is not None
                else self.resolve_translation_profile_snapshot() if job.translation_mode == "en2zh" else None
            )
            request = build_job_conversion_request(
                job=job,
                job_paths=job_paths,
                settings=self.settings,
                package_path=package_path,
                template_path=(
                    materialized_resources.template_path
                    if materialized_resources is not None
                    else self.resolve_template_path(job.template_id)
                ),
                subscript_config_path=(
                    materialized_resources.subscript_config_path
                    if materialized_resources is not None
                    else self.resolve_subscript_config_path()
                ),
                translation_profile=translation_profile,
            )
        except JobResourceSnapshotError as exc:
            failure_transition = build_conversion_failed_transition(
                job,
                error_code=exc.code,
                error_message=exc.message,
            )
            self._handle_stage_failure(
                job=job,
                message=message,
                transition=failure_transition,
                error_code=exc.code,
                error_message=exc.message,
                event_overrides={
                    "translation_failed": {
                        "error_code": exc.code,
                        "details": {"error_message": exc.message},
                    },
                    "job_failed": {
                        "error_code": exc.code,
                        "details": {"error_message": exc.message},
                    },
                },
            )
            return
        if job.translation_mode == "en2zh":
            self._append_intent_events(
                job.id,
                (build_translation_started_intent(translation_model=request.translation_model),),
                trace_id=message.trace_id,
            )

        try:
            result = self.conversion_entrypoint.convert(request)
        except ConversionFailure as exc:
            error_code = exc.code
            error_message = exc.message
            failure_transition = build_conversion_failed_transition(
                job,
                error_code=error_code,
                error_message=error_message,
            )
            self._handle_stage_failure(
                job=job,
                message=message,
                transition=failure_transition,
                error_code=error_code,
                error_message=error_message,
                event_overrides={
                    "translation_failed": {
                        "error_code": error_code,
                        "details": {"error_message": error_message},
                    },
                    "job_failed": {
                        "error_code": error_code,
                        "details": {"error_message": error_message},
                    },
                },
            )
            return
        except Exception as exc:  # pragma: no cover - final guard
            self._log_stage_failure(message, job.id, str(exc))
            raise

        self.job_file_repository.upsert_file(job.id, self.artifact_storage.build_registered_file("result_docx", job_paths))
        if request.translation_request_output is not None and request.translation_request_output.exists():
            self.job_file_repository.upsert_file(
                job.id,
                self.artifact_storage.build_registered_file("translation_request", job_paths),
            )
        if request.translation_trace_output is not None and request.translation_trace_output.exists():
            self.job_file_repository.upsert_file(
                job.id,
                self.artifact_storage.build_registered_file("translation_trace", job_paths),
            )
        if job.translation_mode == "en2zh":
            self._append_intent_events(
                job.id,
                (
                    build_translation_completed_intent(
                        translation_model=request.translation_model,
                        translation_request_recorded=bool(
                            request.translation_request_output and request.translation_request_output.exists()
                        ),
                    ),
                ),
                trace_id=message.trace_id,
            )

        completion_transition = build_conversion_completed_transition(
            job,
            document_language=result.document_language,
        )
        self._apply_transition(
            job,
            completion_transition,
            extra_updates={
                "updated_at": utc_now(),
                "completed_at": utc_now(),
            },
        )
        self._append_intent_events(
            job.id,
            completion_transition.event_intents,
            trace_id=message.trace_id,
            overrides_by_kind={
                "job_completed": {
                    "details": {
                        "pages": result.pages,
                        "document_language": result.document_language,
                    }
                }
            },
        )
        self._delete_stage_message(message.id)
        self.logger.info(
            "[trace_id=%s job_id=%s stage=%s message_id=%s status=completed] result=%s",
            message.trace_id,
            job.id,
            message.stage,
            message.id,
            job_paths.result_docx,
        )

    def _dispatch_convert_parsed_result(self, job: JobRecord, message: JobStageMessage) -> None:
        self._mark_stage_running(message)
        transition = build_parsed_result_conversion_started_transition(job)
        updated_job = self._apply_transition(
            job,
            transition,
            extra_updates={"updated_at": utc_now()},
        )
        self._append_intent_events(
            job.id,
            transition.event_intents,
            trace_id=message.trace_id,
        )

        job_paths = build_job_paths(self.settings.data_path, job.id)
        result_zip_url = job.read_mineru_result_zip_url()
        if not result_zip_url:
            failure_transition = build_parsed_result_conversion_failed_transition(
                job,
                error_code="parsed_result_zip_missing",
                error_message="当前任务缺少 mineru_result_zip_url，无法恢复 parsed 结果包",
            )
            self._handle_stage_failure(
                job=job,
                message=message,
                transition=failure_transition,
                error_code="parsed_result_zip_missing",
                error_message="当前任务缺少 mineru_result_zip_url，无法恢复 parsed 结果包",
                event_overrides={
                    "job_failed": {
                        "error_code": "parsed_result_zip_missing",
                        "details": {"error_message": "当前任务缺少 mineru_result_zip_url，无法恢复 parsed 结果包"},
                    }
                },
            )
            return

        try:
            self._download_mineru_result_package(result_zip_url, job_paths.parsed_result_package)
        except Exception as exc:
            error_message = str(exc)
            failure_transition = build_parsed_result_conversion_failed_transition(
                job,
                error_code="parsed_result_download_failed",
                error_message=error_message,
            )
            self._handle_stage_failure(
                job=job,
                message=message,
                transition=failure_transition,
                error_code="parsed_result_download_failed",
                error_message=error_message,
                event_overrides={
                    "job_failed": {
                        "error_code": "parsed_result_download_failed",
                        "details": {"error_message": error_message},
                    }
                },
            )
            return

        self.job_file_repository.upsert_file(
            job.id,
            self.artifact_storage.build_registered_file("parsed_result_package", job_paths),
        )
        self._append_intent_events(
            job.id,
            (build_parsed_result_package_recovered_intent(source_url=result_zip_url),),
            trace_id=message.trace_id,
        )

        self._run_conversion_pipeline(
            job,
            message,
            package_path=job_paths.parsed_result_package,
        )

    def _dispatch_submit_to_mineru(self, job: JobRecord, message: JobStageMessage) -> None:
        self._mark_stage_running(message)
        transition = build_mineru_submission_started_transition(job)
        self._apply_transition(
            job,
            transition,
            extra_updates={
                "started_at": job.started_at or utc_now(),
                "updated_at": utc_now(),
            },
        )
        self._append_intent_events(
            job.id,
            transition.event_intents,
            trace_id=message.trace_id,
        )

        job_paths = build_job_paths(self.settings.data_path, job.id)
        try:
            callback = self.settings.mineru_callback_url or None
            callback_seed = self._build_callback_seed() if callback else None
            mineru_snapshot = job.resource_snapshot.mineru if job.resource_snapshot is not None else None
            if mineru_snapshot is not None and not mineru_snapshot.callback_enabled:
                callback = None
                callback_seed = None
            mineru_data_id = mineru_snapshot.data_id if mineru_snapshot is not None and mineru_snapshot.data_id else job.id
            batch_id = self._submit_pdf_to_mineru(
                source_pdf=job_paths.source_pdf,
                data_id=mineru_data_id,
                callback=callback,
                callback_seed=callback_seed,
                model_version=mineru_snapshot.model_version if mineru_snapshot is not None else self.settings.mineru_model_version,
                enable_formula=(
                    mineru_snapshot.enable_formula
                    if mineru_snapshot is not None and mineru_snapshot.enable_formula is not None
                    else self.settings.mineru_enable_formula
                ),
                enable_table=(
                    mineru_snapshot.enable_table
                    if mineru_snapshot is not None and mineru_snapshot.enable_table is not None
                    else self.settings.mineru_enable_table
                ),
                language=mineru_snapshot.language if mineru_snapshot is not None and mineru_snapshot.language else self.settings.mineru_language,
            )
        except Exception as exc:
            error_message = str(exc)
            failure_transition = build_mineru_submission_failed_transition(
                job,
                error_message=error_message,
            )
            self._handle_stage_failure(
                job=job,
                message=message,
                transition=failure_transition,
                error_code="mineru_submit_failed",
                error_message=error_message,
                event_overrides={
                    "mineru_submit_failed": {
                        "error_code": "mineru_submit_failed",
                        "details": {"error_message": error_message},
                    },
                    "job_failed": {
                        "error_code": "mineru_submit_failed",
                        "details": {"error_message": error_message},
                    },
                },
            )
            return

        success_transition = build_mineru_submission_succeeded_transition(
            job,
            batch_id=str(batch_id),
            data_id=mineru_data_id,
            callback_seed=callback_seed,
        )
        self._apply_transition(
            job,
            success_transition,
            extra_updates={"updated_at": utc_now()},
        )
        self._append_intent_events(
            job.id,
            success_transition.event_intents,
            trace_id=message.trace_id,
        )
        self._delete_stage_message(message.id)
        self.logger.info(
            "[trace_id=%s job_id=%s stage=%s message_id=%s status=parsing] batch_id=%s data_id=%s",
            message.trace_id,
            job.id,
            message.stage,
            message.id,
            batch_id,
            mineru_data_id,
        )

    def _dispatch_process_callback(self, job: JobRecord, message: JobStageMessage) -> None:
        self._mark_stage_running(message)
        payload = dict(message.payload)
        state = str(payload.get("state") or "")
        full_zip_url = payload.get("full_zip_url")
        batch_id = payload.get("batch_id")
        data_id = payload.get("data_id")

        if full_zip_url:
            self._validate_mineru_result_url(str(full_zip_url))

        # replay 或并发情况下，stage 层也必须复用同一套状态规则。
        try:
            transition = build_mineru_callback_transition(
                job,
                callback_state=state,
                batch_id=str(batch_id) if batch_id is not None else None,
                data_id=str(data_id) if data_id is not None else None,
                full_zip_url=str(full_zip_url) if full_zip_url is not None else None,
            )
        except JobWorkflowViolation as exc:
            self._delete_stage_message(message.id)
            self.logger.warning(
                "[trace_id=%s job_id=%s stage=%s message_id=%s status=skipped] %s",
                message.trace_id,
                job.id,
                message.stage,
                message.id,
                exc.message,
            )
            return

        event_intent = transition.event_intents[0]
        overrides: dict[str, dict] = {
            event_intent.kind: {
                "details": {
                    "batch_id": batch_id,
                    "data_id": data_id,
                    "state": state,
                    "full_zip_url": full_zip_url,
                }
            }
        }

        if transition.resolved_status(job) == "parsed":
            overrides[event_intent.kind]["message"] = "MinerU callback 命中终态结果，任务进入 parsed。"
        elif event_intent.kind == "mineru_callback_failed":
            overrides[event_intent.kind]["error_code"] = "mineru_failed"
        elif state == "failed":
            overrides[event_intent.kind]["error_code"] = "mineru_failed"

        updated_job = self._apply_transition(
            job,
            transition,
            extra_updates={"updated_at": utc_now()},
        )
        self._append_intent_events(
            job.id,
            transition.event_intents,
            trace_id=message.trace_id,
            overrides_by_kind=overrides,
        )
        self._delete_stage_message(message.id)
        if transition.resolved_status(job) == "parsed":
            next_message = self.enqueue_parsed_result_conversion(updated_job, message.trace_id)
            self.logger.info(
                "[trace_id=%s job_id=%s stage=%s message_id=%s status=%s] auto_enqueue=%s",
                message.trace_id,
                job.id,
                message.stage,
                message.id,
                transition.resolved_status(job),
                next_message.stage,
            )
            self.dispatch_message(next_message.id)
            return
        self.logger.info(
            "[trace_id=%s job_id=%s stage=%s message_id=%s status=%s] batch_id=%s state=%s",
            message.trace_id,
            job.id,
            message.stage,
            message.id,
            transition.resolved_status(job),
            batch_id,
            state,
        )

    def _build_mineru_client(self, model_version: str | None = None) -> MinerUClient:
        return MinerUClient(
            api_token=self.settings.mineru_api_token,
            model_version=model_version or self.settings.mineru_model_version,
            user_token=self.settings.mineru_uid,
        )

    def _create_mineru_client(self, *, model_version: str | None = None) -> MinerUClient:
        if self._custom_mineru_client_factory is not None:
            return self._custom_mineru_client_factory()
        return self._build_mineru_client(model_version=model_version)

    def _submit_pdf_to_mineru(
        self,
        *,
        source_pdf: Path,
        data_id: str,
        callback: str | None,
        callback_seed: str | None,
        model_version: str | None,
        enable_formula: bool,
        enable_table: bool,
        language: str,
    ) -> str:
        """提交单个 source PDF 到 MinerU，并只把 batch_id 暴露给 stage workflow。"""

        client = self._create_mineru_client(model_version=model_version)
        batch_id, _file_urls = client.upload_files_batch(
            [source_pdf],
            task_uuids=[data_id],
            enable_formula=enable_formula,
            enable_table=enable_table,
            language=language,
            callback=callback,
            seed=callback_seed,
        )
        return str(batch_id)

    def _download_mineru_result_package(self, result_zip_url: str, output_path: Path) -> Path:
        """下载 MinerU parsed result zip，隔离 provider 下载细节。"""

        client = self._create_mineru_client()
        return client.download_result_zip(result_zip_url, output_path)

    def _query_mineru_result_payload(self, job: JobRecord) -> dict:
        """把 MinerU batch 查询结果归一化成 process_callback stage payload。"""

        if job.source_kind != "source_pdf":
            raise JobWorkflowViolation("只有 source_pdf 任务允许主动查询 MinerU 结果")
        if job.resolved_execution_status() != "parsing":
            raise JobWorkflowViolation(f"当前任务状态 {job.projected_status()} 不允许主动查询 MinerU 结果")
        batch_id = job.read_mineru_batch_id()
        if not batch_id:
            raise JobWorkflowViolation("当前任务缺少 MinerU batch_id，无法主动查询结果")

        client = self._create_mineru_client()
        data = client.query_batch_extract_results(batch_id)
        extract_results = data.get("extract_result") or []
        if not isinstance(extract_results, list):
            raise ValueError("MinerU 查询结果 extract_result 不是数组")

        expected_data_id = job.read_mineru_data_id() or job.id
        matched_item = None
        for item in extract_results:
            if not isinstance(item, dict):
                continue
            if item.get("data_id") == expected_data_id:
                matched_item = item
                break
        if matched_item is None and len(extract_results) == 1 and isinstance(extract_results[0], dict):
            matched_item = extract_results[0]
        if matched_item is None:
            raise FileNotFoundError(f"MinerU 查询结果缺少匹配 data_id: {expected_data_id}")

        full_zip_url = (
            matched_item.get("full_zip_url")
            or matched_item.get("full_zip_oss_url")
            or matched_item.get("result_zip_url")
        )
        if full_zip_url:
            self._validate_mineru_result_url(str(full_zip_url))

        payload = {
            "batch_id": data.get("batch_id") or batch_id,
            "data_id": matched_item.get("data_id") or expected_data_id,
            "state": matched_item.get("state") or "",
            "data": data,
        }
        if full_zip_url:
            payload["full_zip_url"] = str(full_zip_url)
        return payload

    @staticmethod
    def _build_callback_seed(length: int = 32) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _validate_mineru_result_url(self, full_zip_url: str) -> None:
        validate_mineru_result_url(full_zip_url, self.settings.allowed_mineru_result_hosts)
