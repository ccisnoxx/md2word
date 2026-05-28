from __future__ import annotations

# app/repositories/file_job_repository.py: 文件后端 repository，并在持久化边界同步兼容投影字段。

import json
from pathlib import Path
from typing import Any

from app.core.job_models import JobEvent, JobFile, JobRecord, JobStageMessage, sync_source_pdf_compatibility_fields
from app.core.job_paths import build_job_paths, ensure_job_dirs


class FileJobRepository:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.jobs_dir = data_dir / "jobs"
        self.stage_messages_dir = data_dir / "stage_messages"
        self.tmp_dir = data_dir / "tmp"
        for path in (self.jobs_dir, self.stage_messages_dir, self.tmp_dir):
            path.mkdir(parents=True, exist_ok=True)

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def create_job(self, job: JobRecord) -> None:
        paths = build_job_paths(self.data_dir, job.id)
        ensure_job_dirs(paths)
        # source_pdf_context -> mineru_* 兼容投影的同步责任明确留在持久化边界。
        storage_job = sync_source_pdf_compatibility_fields(job)
        self._write_json(paths.job_json, storage_job.model_dump(mode="json"))

    def get_job(self, job_id: str) -> JobRecord | None:
        path = build_job_paths(self.data_dir, job_id).job_json
        if not path.exists():
            return None
        return JobRecord.model_validate(self._read_json(path, {}))

    def list_jobs(self) -> list[JobRecord]:
        jobs: list[JobRecord] = []
        if not self.jobs_dir.exists():
            return jobs
        for job_json in sorted(self.jobs_dir.glob("*/job.json")):
            jobs.append(JobRecord.model_validate(self._read_json(job_json, {})))
        return jobs

    def update_job(self, job_id: str, **patch: Any) -> JobRecord:
        existing = self.get_job(job_id)
        if existing is None:
            raise FileNotFoundError(f"任务不存在: {job_id}")
        # 所有 nested-first 的 source_pdf 写法都在这里统一同步回兼容平铺字段。
        updated = sync_source_pdf_compatibility_fields(existing.model_copy(update=patch))
        self._write_json(
            build_job_paths(self.data_dir, job_id).job_json,
            updated.model_dump(mode="json"),
        )
        return updated

    def append_event(self, job_id: str, event: JobEvent) -> None:
        path = build_job_paths(self.data_dir, job_id).events_jsonl
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json())
            handle.write("\n")

    def list_events(self, job_id: str) -> list[JobEvent]:
        path = build_job_paths(self.data_dir, job_id).events_jsonl
        if not path.exists():
            return []
        events: list[JobEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(JobEvent.model_validate_json(line))
        return events

    def upsert_file(self, job_id: str, file: JobFile) -> None:
        path = build_job_paths(self.data_dir, job_id).files_json
        existing = [
            JobFile.model_validate(item)
            for item in self._read_json(path, [])
        ]
        kept = [item for item in existing if item.file_type != file.file_type]
        kept.append(file)
        self._write_json(path, [item.model_dump(mode="json") for item in kept])

    def list_files(self, job_id: str) -> list[JobFile]:
        path = build_job_paths(self.data_dir, job_id).files_json
        return [JobFile.model_validate(item) for item in self._read_json(path, [])]

    def put_stage_message(self, message: JobStageMessage) -> None:
        path = self.stage_messages_dir / f"{message.id}.json"
        self._write_json(path, message.model_dump(mode="json"))

    def get_stage_message(self, message_id: str) -> JobStageMessage | None:
        path = self.stage_messages_dir / f"{message_id}.json"
        if not path.exists():
            return None
        return JobStageMessage.model_validate(self._read_json(path, {}))

    def update_stage_message(self, message_id: str, **patch: Any) -> JobStageMessage:
        existing = self.get_stage_message(message_id)
        if existing is None:
            raise FileNotFoundError(f"stage message 不存在: {message_id}")
        updated = existing.model_copy(update=patch)
        self.put_stage_message(updated)
        return updated

    def list_pending_stage_messages(self) -> list[JobStageMessage]:
        messages: list[JobStageMessage] = []
        for path in sorted(self.stage_messages_dir.glob("*.json")):
            message = JobStageMessage.model_validate(self._read_json(path, {}))
            if message.status in {"pending", "running"}:
                messages.append(message)
        return messages

    def delete_stage_message(self, message_id: str) -> None:
        (self.stage_messages_dir / f"{message_id}.json").unlink(missing_ok=True)
