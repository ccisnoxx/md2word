from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Callable
from uuid import uuid4

from app.clients.mineru_client import MinerUClient
from app.conversion.contracts import ConversionEntrypoint, ConversionFailure
from app.conversion.entrypoint import build_job_conversion_request
from app.core.config import Settings
from app.core.job_models import ConversionOptions, JobEvent, JobRecord, JobStageMessage, utc_now
from app.core.job_paths import build_job_paths
from app.core.mineru_callback import validate_mineru_result_url
from app.repositories.file_job_repository import FileJobRepository
from app.services.jobs.artifacts import JobArtifactService


class JobStageService:
    def __init__(
        self,
        settings: Settings,
        repository: FileJobRepository,
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
        self.repository.update_job(
            job.id,
            status="queued",
            progress=10,
            updated_at=utc_now(),
        )
        self._append_event(
            job.id,
            stage="stage_enqueued",
            message=event_message,
            status="accepted",
            details=event_details,
            trace_id=trace_id,
        )
        return message

    def _append_event(
        self,
        job_id: str,
        *,
        stage: str,
        message: str,
        status: str,
        trace_id: str,
        error_code: str | None = None,
        details: dict | None = None,
    ) -> None:
        self.repository.append_event(
            job_id,
            JobEvent(
                stage=stage,
                message=message,
                status=status,
                error_code=error_code,
                details=details or {},
                trace_id=trace_id,
            ),
        )

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

    def _mark_job_failed(
        self,
        job: JobRecord,
        *,
        error_code: str,
        error_message: str,
        **extra_updates,
    ) -> None:
        self.repository.update_job(
            job.id,
            status="failed",
            progress=100,
            updated_at=utc_now(),
            error_code=error_code,
            error_message=error_message,
            **extra_updates,
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
        self.repository.update_job(
            job.id,
            status="converting",
            progress=50,
            started_at=job.started_at or utc_now(),
            updated_at=utc_now(),
            error_code=None,
            error_message=None,
        )
        self._append_event(
            job.id,
            stage="conversion_started",
            message="开始执行 MinerU 包转换。",
            status="running",
            trace_id=message.trace_id,
        )

        job_paths = build_job_paths(self.settings.data_path, job.id)
        request = build_job_conversion_request(
            job=job,
            job_paths=job_paths,
            settings=self.settings,
            template_path=self.resolve_template_path(job.template_id),
            subscript_config_path=self.resolve_subscript_config_path(),
        )
        if job.translation_mode == "en2zh":
            self._append_event(
                job.id,
                stage="translation_started",
                message="开始执行英文转中文翻译。",
                status="running",
                details={"translation_model": request.translation_model},
                trace_id=message.trace_id,
            )

        try:
            result = self.conversion_entrypoint.convert(request)
        except ConversionFailure as exc:
            error_code = exc.code
            error_message = exc.message
            self._mark_job_failed(job, error_code=error_code, error_message=error_message)
            self._mark_stage_failed(message, error_code=error_code, error_message=error_message)
            if job.translation_mode == "en2zh" and error_code.startswith("translation_"):
                self._append_event(
                    job.id,
                    stage="translation_failed",
                    message="翻译阶段失败。",
                    status="failed",
                    error_code=error_code,
                    details={"error_message": error_message},
                    trace_id=message.trace_id,
                )
            self._append_event(
                job.id,
                stage="job_failed",
                message="后台转换失败。",
                status="failed",
                error_code=error_code,
                details={"error_message": error_message},
                trace_id=message.trace_id,
            )
            self._log_stage_failure(message, job.id, error_message)
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
            self._append_event(
                job.id,
                stage="translation_completed",
                message="翻译完成，已进入 DOCX 渲染。",
                status="succeeded",
                details={
                    "translation_request_recorded": bool(request.translation_request_output and request.translation_request_output.exists()),
                    "translation_model": request.translation_model,
                },
                trace_id=message.trace_id,
            )

        self.repository.update_job(
            job.id,
            status="completed",
            progress=100,
            result_ready=True,
            resolved_document_language=result.document_language,
            updated_at=utc_now(),
            completed_at=utc_now(),
        )
        self._append_event(
            job.id,
            stage="job_completed",
            message="DOCX 已生成，可供下载。",
            status="succeeded",
            details={
                "pages": result.pages,
                "document_language": result.document_language,
            },
            trace_id=message.trace_id,
        )
        self.repository.delete_stage_message(message.id)
        self.logger.info(
            "[trace_id=%s job_id=%s stage=%s status=completed] result=%s",
            message.trace_id,
            job.id,
            message.stage,
            job_paths.result_docx,
        )

    def _dispatch_submit_to_mineru(self, job: JobRecord, message: JobStageMessage) -> None:
        self._mark_stage_running(message)
        self.repository.update_job(
            job.id,
            status="submitting",
            progress=15,
            started_at=job.started_at or utc_now(),
            updated_at=utc_now(),
            error_code=None,
            error_message=None,
        )
        self._append_event(
            job.id,
            stage="mineru_submit_started",
            message="开始提交 MinerU。",
            status="running",
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
            self._mark_job_failed(
                job,
                error_code="mineru_submit_failed",
                error_message=error_message,
            )
            self._mark_stage_failed(
                message,
                error_code="mineru_submit_failed",
                error_message=error_message,
            )
            self._append_event(
                job.id,
                stage="mineru_submit_failed",
                message="MinerU 提交失败。",
                status="failed",
                error_code="mineru_submit_failed",
                details={"error_message": error_message},
                trace_id=message.trace_id,
            )
            self._append_event(
                job.id,
                stage="job_failed",
                message="后台转换失败。",
                status="failed",
                error_code="mineru_submit_failed",
                details={"error_message": error_message},
                trace_id=message.trace_id,
            )
            self._log_stage_failure(message, job.id, error_message)
            return

        self.repository.update_job(
            job.id,
            status="parsing",
            progress=25,
            updated_at=utc_now(),
            mineru_batch_id=batch_id,
            mineru_data_id=job.id,
            mineru_callback_seed=callback_seed,
            mineru_status="submitted",
        )
        self._append_event(
            job.id,
            stage="mineru_submit_succeeded",
            message="MinerU 提交成功，等待外部回调。",
            status="succeeded",
            details={"batch_id": batch_id, "data_id": job.id},
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

        if job.status not in {"parsing", "parsed", "failed"}:
            self.repository.delete_stage_message(message.id)
            self.logger.warning(
                "[trace_id=%s job_id=%s stage=%s status=skipped] unsupported job status for callback: %s",
                message.trace_id,
                job.id,
                message.stage,
                job.status,
            )
            return

        if full_zip_url:
            self._validate_mineru_result_url(str(full_zip_url))

        updates = {
            "updated_at": utc_now(),
            "mineru_status": state or job.mineru_status,
        }
        if data_id:
            updates["mineru_data_id"] = str(data_id)
        if batch_id:
            updates["mineru_batch_id"] = str(batch_id)
        if full_zip_url:
            updates["mineru_result_zip_url"] = str(full_zip_url)

        event_message = "MinerU callback 已记录。"
        event_status = "succeeded"
        event_stage = "mineru_callback_processed"

        if state == "done" and full_zip_url:
            updates["status"] = "parsed"
            updates["progress"] = 60
            event_message = "MinerU callback 命中终态结果，任务进入 parsed。"
        elif state == "failed":
            updates["status"] = "failed"
            updates["progress"] = 100
            updates["error_code"] = "mineru_failed"
            updates["error_message"] = "MinerU 返回 failed"
            event_message = "MinerU callback 报告失败。"
            event_stage = "mineru_callback_failed"
            event_status = "failed"

        self.repository.update_job(job.id, **updates)
        self._append_event(
            job.id,
            stage=event_stage,
            message=event_message,
            status=event_status,
            error_code="mineru_failed" if state == "failed" else None,
            details={
                "batch_id": batch_id,
                "data_id": data_id,
                "state": state,
                "full_zip_url": full_zip_url,
            },
            trace_id=message.trace_id,
        )
        self.repository.delete_stage_message(message.id)
        self.logger.info(
            "[trace_id=%s job_id=%s stage=%s status=%s] batch_id=%s state=%s",
            message.trace_id,
            job.id,
            message.stage,
            updates.get("status", job.status),
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
