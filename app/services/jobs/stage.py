from __future__ import annotations

# app/services/jobs/stage.py: 驱动后台 stage 执行，并通过集中 workflow 规则推进 job 状态。

import logging
import secrets
from pathlib import Path
from typing import Callable
from uuid import uuid4

from app.clients.mineru_client import MinerUClient
from app.conversion.contracts import ConversionEntrypoint, ConversionFailure
from app.conversion.entrypoint import build_job_conversion_request
from app.core.config import Settings
from app.core.job_workflow import (
    JobWorkflowViolation,
    build_conversion_completed_transition,
    build_conversion_failed_transition,
    build_conversion_started_transition,
    build_mineru_callback_transition,
    build_parsed_result_conversion_failed_transition,
    build_parsed_result_package_recovered_intent,
    build_parsed_result_conversion_started_transition,
    build_mineru_submission_failed_transition,
    build_mineru_submission_started_transition,
    build_mineru_submission_succeeded_transition,
    build_stage_enqueue_transition,
    build_translation_completed_intent,
    build_translation_started_intent,
)
from app.core.job_models import ConversionOptions, JobRecord, JobStageMessage, utc_now
from app.core.job_paths import build_job_paths
from app.core.mineru_callback import validate_mineru_result_url
from app.repositories.protocols import JobStageWorkflowRepositoryProtocol
from app.services.jobs.artifacts import JobArtifactService
from app.services.jobs.workflow_events import build_job_event_from_intent


class JobStageService:
    def __init__(
        self,
        settings: Settings,
        repository: JobStageWorkflowRepositoryProtocol,
        conversion_entrypoint: ConversionEntrypoint,
        artifact_service: JobArtifactService,
        mineru_client_factory: Callable[[], MinerUClient] | None = None,
        resolve_template_path: Callable[[str | None], Path | None] | None = None,
        resolve_subscript_config_path: Callable[[], Path | None] | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.conversion_entrypoint = conversion_entrypoint
        self.artifact_service = artifact_service
        self.mineru_client_factory = mineru_client_factory or self._build_mineru_client
        self.resolve_template_path = resolve_template_path or (lambda _template_id: self.settings.default_template_path)
        self.resolve_subscript_config_path = resolve_subscript_config_path or (lambda: self.settings.subscript_config_path)
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
        self.repository.put_stage_message(message)
        return message

    def enqueue_parsed_result_conversion(self, job: JobRecord, trace_id: str) -> JobStageMessage:
        return self._enqueue_stage(
            job=job,
            stage="convert_parsed_result",
            trace_id=trace_id,
            event_message="parsed 结果已进入在线后处理队列。",
            event_details={"source_kind": "source_pdf", "from_lifecycle_status": job.resolved_lifecycle_status()},
        )

    def dispatch_message(self, message_id: str) -> None:
        message = self.repository.get_stage_message(message_id)
        if message is None:
            return

        job = self.repository.get_job(message.job_id)
        if job is None or job.status == "canceled":
            self.repository.delete_stage_message(message_id)
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

        self.repository.delete_stage_message(message_id)

    def replay_pending(self) -> None:
        for message in self.repository.list_pending_stage_messages():
            self.dispatch_message(message.id)

    def _enqueue_stage(
        self,
        *,
        job: JobRecord,
        stage: str,
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
        self.repository.put_stage_message(message)
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
            self.repository.append_event(job_id, event)

    def _apply_transition(
        self,
        job: JobRecord,
        transition,
        *,
        extra_updates: dict | None = None,
    ) -> JobRecord:
        """统一写入 job transition，避免每个 stage 手工拼 patch。"""

        return self.repository.update_job(
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
        self.repository.update_stage_message(
            message.id,
            status="running",
            attempts=message.attempts + 1,
            updated_at=utc_now(),
            error_code=None,
            error_message=None,
        )

    def _mark_stage_failed(self, message: JobStageMessage, *, error_code: str, error_message: str) -> None:
        self.repository.update_stage_message(
            message.id,
            status="failed",
            updated_at=utc_now(),
            error_code=error_code,
            error_message=error_message,
        )

    def _log_stage_failure(self, message: JobStageMessage, job_id: str, error_message: str) -> None:
        self.logger.exception(
            "[trace_id=%s job_id=%s stage=%s status=failed] %s",
            message.trace_id,
            job_id,
            message.stage,
            error_message,
        )

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
        request = build_job_conversion_request(
            job=job,
            job_paths=job_paths,
            settings=self.settings,
            package_path=package_path,
            template_path=self.resolve_template_path(job.template_id),
            subscript_config_path=self.resolve_subscript_config_path(),
        )
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

        self.repository.upsert_file(job.id, self.artifact_service.build_registered_file("result_docx", job_paths))
        if request.translation_request_output is not None and request.translation_request_output.exists():
            self.repository.upsert_file(
                job.id,
                self.artifact_service.build_registered_file("translation_request", job_paths),
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
        self.repository.delete_stage_message(message.id)
        self.logger.info(
            "[trace_id=%s job_id=%s stage=%s status=completed] result=%s",
            message.trace_id,
            job.id,
            message.stage,
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
            client = self.mineru_client_factory()
            client.download_result_zip(result_zip_url, job_paths.parsed_result_package)
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

        self.repository.upsert_file(
            job.id,
            self.artifact_service.build_registered_file("parsed_result_package", job_paths),
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
            client = self.mineru_client_factory()
            callback = self.settings.mineru_callback_url or None
            callback_seed = self._build_callback_seed() if callback else None
            batch_id, _file_urls = client.upload_files_batch(
                [job_paths.source_pdf],
                task_uuids=[job.id],
                enable_formula=self.settings.mineru_enable_formula,
                enable_table=self.settings.mineru_enable_table,
                language=self.settings.mineru_language,
                callback=callback,
                seed=callback_seed,
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
            data_id=job.id,
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
        self.repository.delete_stage_message(message.id)
        self.logger.info(
            "[trace_id=%s job_id=%s stage=%s status=parsing] batch_id=%s data_id=%s",
            message.trace_id,
            job.id,
            message.stage,
            batch_id,
            job.id,
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
            self.repository.delete_stage_message(message.id)
            self.logger.warning(
                "[trace_id=%s job_id=%s stage=%s status=skipped] %s",
                message.trace_id,
                job.id,
                message.stage,
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
        self.repository.delete_stage_message(message.id)
        if transition.resolved_status(job) == "parsed":
            next_message = self.enqueue_parsed_result_conversion(updated_job, message.trace_id)
            self.logger.info(
                "[trace_id=%s job_id=%s stage=%s status=%s] auto_enqueue=%s",
                message.trace_id,
                job.id,
                message.stage,
                transition.resolved_status(job),
                next_message.stage,
            )
            self.dispatch_message(next_message.id)
            return
        self.logger.info(
            "[trace_id=%s job_id=%s stage=%s status=%s] batch_id=%s state=%s",
            message.trace_id,
            job.id,
            message.stage,
            transition.resolved_status(job),
            batch_id,
            state,
        )

    def _build_mineru_client(self) -> MinerUClient:
        return MinerUClient(
            api_token=self.settings.mineru_api_token,
            model_version=self.settings.mineru_model_version,
        )

    @staticmethod
    def _build_callback_seed(length: int = 32) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _validate_mineru_result_url(self, full_zip_url: str) -> None:
        validate_mineru_result_url(full_zip_url, self.settings.allowed_mineru_result_hosts)
