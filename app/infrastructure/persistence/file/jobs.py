from __future__ import annotations

# app/infrastructure/persistence/file/jobs.py: file backend 的 job 主记录和事件 adapter。

from typing import Any

from app.domains.jobs.models import JobEvent, JobRecord, sync_source_pdf_compatibility_fields
from app.domains.jobs.paths import ensure_job_dirs
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileJobSnapshotRepository:
    """用 file backend 读写 JobRecord 主记录。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def create_job(self, job: JobRecord) -> None:
        paths = self.backend.job_paths(job.id)
        ensure_job_dirs(paths)
        storage_job = sync_source_pdf_compatibility_fields(job)
        self.backend.write_json(paths.job_json, storage_job.model_dump(mode="json"))

    def get_job(self, job_id: str) -> JobRecord | None:
        path = self.backend.job_paths(job_id).job_json
        if not path.exists():
            return None
        return JobRecord.model_validate(self.backend.read_json(path, {}))

    def list_jobs(self) -> list[JobRecord]:
        jobs: list[JobRecord] = []
        if not self.backend.jobs_dir.exists():
            return jobs
        for job_json in sorted(self.backend.jobs_dir.glob("*/job.json")):
            jobs.append(JobRecord.model_validate(self.backend.read_json(job_json, {})))
        return jobs

    def update_job(self, job_id: str, **patch: Any) -> JobRecord:
        existing = self.get_job(job_id)
        if existing is None:
            raise FileNotFoundError(f"任务不存在: {job_id}")
        updated = sync_source_pdf_compatibility_fields(existing.model_copy(update=patch))
        self.backend.write_json(
            self.backend.job_paths(job_id).job_json,
            updated.model_dump(mode="json"),
        )
        return updated


class FileJobEventRepository:
    """用 file backend 追加和读取 JobEvent JSONL。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def append_event(self, job_id: str, event: JobEvent) -> None:
        self.backend.append_json_line(
            self.backend.job_paths(job_id).events_jsonl,
            event.model_dump_json(),
        )

    def list_events(self, job_id: str) -> list[JobEvent]:
        path = self.backend.job_paths(job_id).events_jsonl
        return [JobEvent.model_validate_json(line) for line in self.backend.read_json_lines(path)]
