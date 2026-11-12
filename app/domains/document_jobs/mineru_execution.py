"""MinerU 执行：解析提交与轮询、回调排队与重放、结果下载登记与客户端构造。"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app.clients.mineru_client import MinerUClient, MinerUError
from app.core.config import Settings
from app.domains.document_jobs.execution_support import DocumentJobLifecycle, require_uploaded_file
from app.domains.document_jobs.models import DocumentJobCallbackMessage, DocumentJobRecord
from app.domains.document_jobs.repository import (
    DocumentJobCallbackMessageStoreProtocol,
    DocumentJobRepositoryProtocol,
)
from app.domains.files import FileUploadService
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.mineru.config import EffectiveMinerUConfig
from app.domains.resources.models import utc_now
from app.domains.translation.modes import spec_for_document_job_mode

class MinerUExecution:
    """MinerU 执行：由 DocumentJobExecutionService 构造并持有，负责解析提交与轮询、回调排队与重放、结果下载登记。

    任务级状态推进与事件记录统一经注入的 DocumentJobLifecycle 完成；settings、job_repository 等共用依赖
    与宿主引用同一对象，在构造时显式注入。
    """

    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        file_service: FileUploadService,
        lifecycle: DocumentJobLifecycle,
        callback_message_store: DocumentJobCallbackMessageStoreProtocol,
        mineru_config_resolver: Callable[[], EffectiveMinerUConfig],
        mineru_client_factory: Callable[[], Any] | None,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.file_repository = file_repository
        self.file_service = file_service
        self.lifecycle = lifecycle
        self.callback_message_store = callback_message_store
        self.mineru_config_resolver = mineru_config_resolver
        self.mineru_client_factory = mineru_client_factory or self._build_mineru_client
        self.logger = logging.getLogger("business")

    def _run_mineru_parse(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        current, can_continue = self._refresh_mineru_parse_attempt(job, trace_id=trace_id)
        if not can_continue:
            return current
        job = current
        if job.mineru_raw_result_file_id:
            parsed = self.job_repository.update_document_job_if_current(
                job.id,
                allowed_statuses={"running"},
                allowed_stages={"parsing"},
                expected_retry_count=job.retry_count,
                status="running",
                stage="parsed",
                progress=max(job.progress, 30),
                updated_at=utc_now(),
            )
            return parsed or self.job_repository.get_document_job(job.id) or job

        with tempfile.TemporaryDirectory(prefix="document_job_mineru_") as temp_dir:
            client = self.mineru_client_factory()
            data_id = job.mineru_data_id or job.id
            batch_id = job.mineru_batch_id
            if not batch_id:
                source_file = require_uploaded_file(self.file_repository, job.source_file_id)
                source_path = Path(temp_dir) / source_file.original_filename
                source_path.write_bytes(self.file_service.read_file_content(source_file))
                callback = self.settings.mineru_callback_url.strip() or None
                callback_seed = self._build_callback_seed() if callback else None
                batch_id, _file_urls = client.upload_files_batch(
                    [source_path],
                    task_uuids=[data_id],
                    enable_formula=self.settings.mineru_enable_formula,
                    enable_table=self.settings.mineru_enable_table,
                    language=self._mineru_language_for_job(job),
                    callback=callback,
                    seed=callback_seed,
                )
                updated_job = self.job_repository.update_document_job_if_current(
                    job.id,
                    allowed_statuses={"running"},
                    allowed_stages={"parsing"},
                    expected_retry_count=job.retry_count,
                    mineru_batch_id=batch_id,
                    mineru_data_id=data_id,
                    mineru_callback_seed=callback_seed,
                    progress=max(job.progress, 15),
                    updated_at=utc_now(),
                )
                if updated_job is None:
                    return self.job_repository.get_document_job(job.id) or job
                job = updated_job
                self.lifecycle.record_event(
                    job,
                    event_type="stage_succeeded",
                    stage="parsing",
                    message="MinerU 任务已提交。",
                    payload={"mineru_batch_id": batch_id, "mineru_data_id": data_id},
                    trace_id=trace_id,
                )

            payload = client.query_batch_extract_results(batch_id)
            current, can_continue = self._refresh_mineru_parse_attempt(job, trace_id=trace_id)
            if not can_continue:
                return current
            result_item = self._select_mineru_result(payload, data_id, batch_id=batch_id)
            state = str(result_item.get("state") or "").lower()
            if state == "failed":
                return self.lifecycle.mark_failed(
                    job, failed_stage="parsing", error_code="mineru_failed",
                    error_message="MinerU 查询返回解析失败。", trace_id=trace_id,
                )
            full_zip_url = result_item.get("full_zip_url")
            if state not in {"done", "success", "succeeded"} or not full_zip_url:
                waiting = self.job_repository.update_document_job_if_current(
                    job.id,
                    allowed_statuses={"running"},
                    allowed_stages={"parsing"},
                    expected_retry_count=job.retry_count,
                    status="running",
                    stage="parsing",
                    progress=max(job.progress, 20),
                    updated_at=utc_now(),
                )
                if waiting is None:
                    return self.job_repository.get_document_job(job.id) or job
                self.lifecycle.record_event(
                    waiting,
                    event_type="stage_started",
                    stage="parsing",
                    message="MinerU 结果尚未就绪，等待后续查询或回调。",
                    payload={"mineru_batch_id": batch_id, "mineru_state": state or "unknown"},
                    trace_id=trace_id,
                )
                return waiting

            return self._download_and_register_mineru_result(
                job,
                client=client,
                full_zip_url=str(full_zip_url),
                batch_id=str(batch_id),
                data_id=str(data_id),
                temp_dir=Path(temp_dir),
                trace_id=trace_id,
                expected_retry_count=job.retry_count,
            )

    def find_job_for_mineru_callback(self, payload: dict[str, Any]) -> DocumentJobRecord | None:
        """按 MinerU callback 里的 data_id/batch_id 匹配 document_job。"""

        data_id = str(payload.get("data_id") or "").strip()
        batch_id = str(payload.get("batch_id") or "").strip()
        jobs = self.job_repository.list_document_jobs()
        if data_id:
            for job in jobs:
                if job.mineru_data_id == data_id or job.id == data_id:
                    return job
        if batch_id:
            for job in jobs:
                if job.mineru_batch_id == batch_id:
                    return job
        return None

    def enqueue_mineru_callback_for_job(
        self,
        job: DocumentJobRecord,
        payload: dict[str, Any],
        *,
        trace_id: str | None,
    ) -> tuple[DocumentJobRecord, DocumentJobCallbackMessage, bool, bool]:
        """可信 MinerU callback 只落专用消息，并返回是否需要唤醒 Worker。"""

        normalized_payload = self._build_callback_message_payload(job, payload)
        message = DocumentJobCallbackMessage(
            id=f"doccb_{uuid4().hex[:12]}",
            job_id=job.id,
            job_retry_count=job.retry_count,
            dedupe_key=self._build_callback_dedupe_key(
                job_id=job.id,
                retry_count=job.retry_count,
                payload=normalized_payload,
            ),
            payload=normalized_payload,
            trace_id=trace_id,
        )
        stored_message, created = self.callback_message_store.put_or_get_callback_message(message)
        self.lifecycle.record_event(
            job,
            event_type="mineru_callback_received",
            stage=job.stage,
            message="MinerU callback 已接收并通过校验。",
            payload={
                "message_id": stored_message.id,
                "message_created": created,
                "mineru_batch_id": normalized_payload.get("batch_id"),
                "mineru_data_id": normalized_payload.get("data_id"),
                "mineru_state": normalized_payload.get("state") or "unknown",
            },
            trace_id=trace_id,
        )
        if job.status != "running" or job.stage != "parsing":
            if stored_message.status in {"pending", "running"}:
                stored_message = self.callback_message_store.mark_callback_message_ignored(
                    stored_message.id,
                    error_code="job_state_not_accepting_callback",
                    error_message=f"当前任务状态不消费 MinerU callback: status={job.status} stage={job.stage}",
                    updated_at=utc_now(),
                )
            self._record_callback_ignored_event(job, stored_message, trace_id=trace_id)
            return job, stored_message, created, False

        self.lifecycle.record_event(
            job,
            event_type="mineru_callback_queued",
            stage="parsing",
            message="MinerU callback 已进入 document_jobs Worker 队列。",
            payload={
                "message_id": stored_message.id,
                "message_created": created,
                "callback_status": stored_message.status,
            },
            trace_id=trace_id,
        )
        return job, stored_message, created, stored_message.status in {"pending", "running"}

    def _process_replayable_callback_messages(
        self,
        job: DocumentJobRecord,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        latest = job
        for message in self.callback_message_store.list_replayable_callback_messages(job.id):
            refreshed = self.job_repository.get_document_job(job.id)
            if refreshed is None:
                return latest
            latest = self._process_callback_message(refreshed, message, trace_id=message.trace_id or trace_id)
        return latest

    def _process_callback_message(
        self,
        job: DocumentJobRecord,
        message: DocumentJobCallbackMessage,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        now = utc_now()
        running_message = self.callback_message_store.mark_callback_message_running(
            message.id,
            attempts=message.attempts + 1,
            lease_owner="document_jobs_worker",
            leased_at=now,
            lease_expires_at=now + timedelta(seconds=self.settings.stage_message_lease_seconds),
            updated_at=now,
        )
        if running_message is None:
            return job
        if job.status in {"succeeded", "failed", "canceled"}:
            ignored = self.callback_message_store.mark_callback_message_ignored(
                running_message.id,
                error_code="job_terminal",
                error_message=f"任务已终态，不消费 callback: status={job.status}",
                updated_at=utc_now(),
            )
            self._record_callback_ignored_event(job, ignored, trace_id=trace_id)
            return job
        if job.retry_count != running_message.job_retry_count:
            ignored = self.callback_message_store.mark_callback_message_ignored(
                running_message.id,
                error_code="job_retry_changed",
                error_message="任务 retry_count 已变化，旧 callback 已忽略。",
                updated_at=utc_now(),
            )
            self._record_callback_ignored_event(job, ignored, trace_id=trace_id)
            return job
        if job.status != "running" or job.stage != "parsing":
            ignored = self.callback_message_store.mark_callback_message_ignored(
                running_message.id,
                error_code="job_state_not_accepting_callback",
                error_message=f"当前任务状态不消费 MinerU callback: status={job.status} stage={job.stage}",
                updated_at=utc_now(),
            )
            self._record_callback_ignored_event(job, ignored, trace_id=trace_id)
            return job

        payload = running_message.payload
        state = str(payload.get("state") or "").lower()
        batch_id = str(payload.get("batch_id") or job.mineru_batch_id or "").strip()
        data_id = str(payload.get("data_id") or job.mineru_data_id or job.id).strip()
        job = self._sync_callback_ids(job, batch_id=batch_id, data_id=data_id, trace_id=trace_id)
        if job.status != "running" or job.stage != "parsing":
            ignored = self.callback_message_store.mark_callback_message_ignored(
                running_message.id,
                error_code="job_state_not_accepting_callback",
                error_message=f"当前任务状态不消费 MinerU callback: status={job.status} stage={job.stage}",
                updated_at=utc_now(),
            )
            self._record_callback_ignored_event(job, ignored, trace_id=trace_id)
            return job
        if state == "failed":
            updated = self.lifecycle.mark_failed(
                job,
                failed_stage="parsing",
                error_code="mineru_failed",
                error_message="MinerU callback 返回 failed。",
                trace_id=trace_id,
            )
            self.callback_message_store.mark_callback_message_processed(running_message.id, updated_at=utc_now())
            return updated

        full_zip_url = payload.get("full_zip_url")
        if state not in {"done", "success", "succeeded"} or not full_zip_url:
            self.lifecycle.record_event(
                job,
                event_type="mineru_callback_processed",
                stage="parsing",
                message="MinerU callback 已消费，结果尚未就绪。",
                payload={
                    "message_id": running_message.id,
                    "mineru_batch_id": batch_id or None,
                    "mineru_state": state or "unknown",
                },
                trace_id=trace_id,
            )
            self.callback_message_store.mark_callback_message_processed(running_message.id, updated_at=utc_now())
            return job

        with tempfile.TemporaryDirectory(prefix="document_job_mineru_callback_") as temp_dir:
            parsed = self._download_and_register_mineru_result(
                job,
                client=self.mineru_client_factory(),
                full_zip_url=str(full_zip_url),
                batch_id=batch_id or str(job.mineru_batch_id or ""),
                data_id=data_id or job.id,
                temp_dir=Path(temp_dir),
                trace_id=trace_id,
                expected_retry_count=running_message.job_retry_count,
            )
        if parsed.status != "running" or parsed.stage != "parsed":
            ignored = self.callback_message_store.mark_callback_message_ignored(
                running_message.id,
                error_code="job_state_changed_before_callback_completed",
                error_message=f"callback 结果未应用，任务当前状态: status={parsed.status} stage={parsed.stage}",
                updated_at=utc_now(),
            )
            self._record_callback_ignored_event(parsed, ignored, trace_id=trace_id)
            return parsed
        self.callback_message_store.mark_callback_message_processed(running_message.id, updated_at=utc_now())
        self.lifecycle.record_event(
            parsed,
            event_type="mineru_callback_processed",
            stage="parsing",
            message="MinerU callback 已消费，解析结果已交给后续 Worker 阶段。",
            payload={"message_id": running_message.id, "mineru_raw_result_file_id": parsed.mineru_raw_result_file_id},
            trace_id=trace_id,
        )
        return parsed

    def _build_callback_message_payload(self, job: DocumentJobRecord, payload: dict[str, Any]) -> dict[str, Any]:
        state = str(payload.get("state") or "").lower()
        batch_id = str(payload.get("batch_id") or job.mineru_batch_id or "").strip() or None
        data_id = str(payload.get("data_id") or job.mineru_data_id or job.id).strip() or None
        full_zip_url = payload.get("full_zip_url")
        content = payload.get("content")
        content_hash = None
        if isinstance(content, str) and content.strip():
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {
            "batch_id": batch_id,
            "data_id": data_id,
            "state": state or None,
            "full_zip_url": str(full_zip_url) if full_zip_url is not None else None,
            "content_hash": content_hash,
        }

    def _build_callback_dedupe_key(self, *, job_id: str, retry_count: int, payload: dict[str, Any]) -> str:
        stable_payload = {
            "job_id": job_id,
            "retry_count": retry_count,
            "batch_id": payload.get("batch_id"),
            "data_id": payload.get("data_id"),
            "state": payload.get("state"),
            "full_zip_url": payload.get("full_zip_url"),
            "content_hash": payload.get("content_hash"),
        }
        encoded = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _sync_callback_ids(
        self,
        job: DocumentJobRecord,
        *,
        batch_id: str,
        data_id: str,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        patch: dict[str, Any] = {}
        if batch_id and batch_id != (job.mineru_batch_id or ""):
            patch["mineru_batch_id"] = batch_id
        if data_id and data_id != (job.mineru_data_id or ""):
            patch["mineru_data_id"] = data_id
        if not patch:
            return job
        updated = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"parsing"},
            expected_retry_count=job.retry_count,
            **patch,
            updated_at=utc_now(),
        )
        if updated is None:
            latest = self.job_repository.get_document_job(job.id)
            if latest is not None:
                self.lifecycle.record_event(
                    latest,
                    event_type="mineru_callback_ignored",
                    stage=latest.stage,
                    message="MinerU callback 关联信息写入被跳过，任务状态已变化。",
                    payload={"previous_stage": job.stage, "previous_status": job.status},
                    trace_id=trace_id,
                    level="warning",
                )
                return latest
            return job
        return updated

    def _record_callback_ignored_event(
        self,
        job: DocumentJobRecord,
        message: DocumentJobCallbackMessage,
        *,
        trace_id: str | None,
    ) -> None:
        self.lifecycle.record_event(
            job,
            event_type="mineru_callback_ignored",
            stage=job.stage,
            message="MinerU callback 已忽略。",
            payload={
                "message_id": message.id,
                "error_code": message.error_code,
                "error_message": message.error_message,
                "callback_status": message.status,
            },
            trace_id=trace_id,
            level="warning",
        )

    def _download_and_register_mineru_result(
        self,
        job: DocumentJobRecord,
        *,
        client: Any,
        full_zip_url: str,
        batch_id: str,
        data_id: str,
        temp_dir: Path,
        trace_id: str | None,
        expected_retry_count: int | None = None,
    ) -> DocumentJobRecord:
        """下载 MinerU 原始结果包，登记为 document_file 并把任务推进到 parsed。"""

        latest, can_continue = self._refresh_mineru_parse_attempt(job, trace_id=trace_id)
        if not can_continue:
            return latest
        if latest.mineru_raw_result_file_id:
            updated = self.job_repository.update_document_job_if_current(
                latest.id,
                allowed_statuses={"running"},
                allowed_stages={"parsing"},
                expected_retry_count=expected_retry_count,
                status="running",
                stage="parsed",
                progress=max(latest.progress, 30),
                updated_at=utc_now(),
            )
            return updated or self.job_repository.get_document_job(job.id) or latest
        raw_zip_path = temp_dir / "mineru_raw_result.zip"
        client.download_result_zip(full_zip_url, raw_zip_path)
        latest, can_continue = self._refresh_mineru_parse_attempt(job, trace_id=trace_id)
        if not can_continue:
            return latest
        raw_file = self.file_service.register_generated_content(
            tenant_id=latest.tenant_id,
            company_id=latest.company_id,
            job_id=latest.id,
            created_by=latest.created_by,
            file_type="mineru_raw_result",
            filename="mineru_raw_result.zip",
            mime_type="application/zip",
            content=raw_zip_path.read_bytes(),
            metadata={
                "source_file_id": latest.source_file_id,
                "mineru_batch_id": batch_id,
                "mineru_data_id": data_id,
                "full_zip_url": full_zip_url,
                "retry_count": latest.retry_count,
            },
        )
        parsed = self.job_repository.update_document_job_if_current(
            latest.id,
            allowed_statuses={"running"},
            allowed_stages={"parsing"},
            expected_retry_count=expected_retry_count,
            status="running",
            stage="parsed",
            progress=max(latest.progress, 30),
            mineru_raw_result_file_id=raw_file.id,
            updated_at=utc_now(),
        )
        if parsed is None:
            return self.job_repository.get_document_job(latest.id) or latest
        try:
            self.lifecycle.record_event(
                parsed,
                event_type="file_registered",
                stage="parsing",
                message="MinerU 原始结果已保存。",
                payload={"file_id": raw_file.id, "file_type": raw_file.file_type, "object_key": raw_file.object_key},
                trace_id=trace_id,
            )
            self.lifecycle.record_event(
                parsed,
                event_type="stage_succeeded",
                stage="parsing",
                message="解析阶段已完成。",
                payload={"mineru_raw_result_file_id": raw_file.id},
                trace_id=trace_id,
            )
            self.logger.info(
                "[trace_id=%s job_id=%s stage=parsing status=parsed] mineru_raw_result_file_id=%s",
                trace_id,
                latest.id,
                raw_file.id,
            )
        except Exception as exc:
            return self.lifecycle.fail_stage_attempt(parsed, exc, trace_id=trace_id)
        return parsed

    def _mineru_language_for_job(self, job: DocumentJobRecord) -> str:
        spec = spec_for_document_job_mode(job.mode)
        return spec.mineru_language or self.settings.mineru_language

    def _refresh_mineru_parse_attempt(
        self, job: DocumentJobRecord, *, trace_id: str | None,
    ) -> tuple[DocumentJobRecord, bool]:
        """解析外端调用前后核对本次身份和固定期限，避免旧结果归入新代。"""

        latest = self.job_repository.get_document_job(job.id)
        if latest is None:
            return job, False
        if (latest.retry_count != job.retry_count or latest.status != "running" or latest.stage != "parsing"
                or latest.mineru_batch_id != job.mineru_batch_id or latest.mineru_data_id != job.mineru_data_id):
            return latest, False
        if latest.timeout_at is None:
            # 旧新代可能已提交批次却未保存期限；只能沿本代稳定起点补齐，不能从每轮 now 续期。
            if latest.started_at is None:
                return self.lifecycle.mark_failed(
                    latest, failed_stage="parsing", error_code="document_job_timeout",
                    error_message="解析记录缺少本代开始时间，无法确定绝对截止期限，已停止执行。",
                    trace_id=trace_id,
                ), False
            updated = self.job_repository.update_document_job_if_current(
                latest.id, allowed_statuses={"running"}, allowed_stages={"parsing"},
                expected_retry_count=latest.retry_count,
                timeout_at=latest.started_at + timedelta(seconds=self.settings.p0_document_job_timeout_seconds),
                updated_at=utc_now(),
            )
            if updated is None:
                return self.job_repository.get_document_job(latest.id) or latest, False
            latest = updated
        timed_out = self.lifecycle.mark_timed_out_if_needed(latest, trace_id=trace_id)
        return (timed_out, False) if timed_out is not None else (latest, True)

    def _select_mineru_result(self, payload: dict, data_id: str, *, batch_id: str) -> dict:
        results = payload.get("extract_result") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise ValueError("MinerU 查询结果缺少 extract_result 数组。")
        if payload.get("batch_id") and str(payload["batch_id"]) != batch_id:
            raise MinerUError("MinerU 查询结果的 batch_id 与当前批次不一致。")
        for item in results:
            if isinstance(item, dict) and str(item.get("data_id") or "") == data_id:
                return item
        if not results:
            return {}
        # 历史单文件结果和既有适配器可能不回传 data_id；显式异身份不能借此兜底。
        if len(results) == 1 and isinstance(results[0], dict) and not results[0].get("data_id"):
            return results[0]
        raise MinerUError("MinerU 查询结果缺少匹配当前 data_id 的记录。")

    @staticmethod
    def _build_callback_seed(length: int = 32) -> str:
        """生成 MinerU checksum 使用的单任务 seed。"""

        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _build_mineru_client(self) -> MinerUClient:
        config = self.mineru_config_resolver()
        if not config.api_token:
            raise RuntimeError("MINERU_API_TOKEN 未配置，无法提交 MinerU。")
        return MinerUClient(
            api_token=config.api_token,
            result_host_allowlist=self.settings.allowed_mineru_result_hosts,
            model_version=self.settings.mineru_model_version,
            user_token=config.uid or "",
        )
