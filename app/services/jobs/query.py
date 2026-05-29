from __future__ import annotations

from collections import Counter

from fastapi import HTTPException, status

from app.repositories.protocols import JobEventRepositoryProtocol, JobFileRepositoryProtocol, JobSnapshotRepositoryProtocol


class JobQueryService:
    def __init__(
        self,
        job_repository: JobSnapshotRepositoryProtocol,
        job_file_repository: JobFileRepositoryProtocol,
        job_event_repository: JobEventRepositoryProtocol,
    ) -> None:
        self.job_repository = job_repository
        self.job_file_repository = job_file_repository
        self.job_event_repository = job_event_repository

    def list_jobs(
        self,
        *,
        page: int,
        page_size: int,
        status_filter: str | None,
        query_text: str | None,
        sort: str,
    ):
        jobs = self.job_repository.list_jobs()
        if status_filter is not None:
            jobs = [item for item in jobs if item.status == status_filter]
        if query_text is not None:
            query_lower = query_text.lower()
            jobs = [
                item
                for item in jobs
                if query_lower in item.id.lower() or query_lower in item.source_filename.lower()
            ]

        sort_key = "created_at"
        reverse = True
        if sort == "created_at_asc":
            reverse = False
        elif sort == "updated_at_desc":
            sort_key = "updated_at"
        elif sort == "updated_at_asc":
            sort_key = "updated_at"
            reverse = False
        jobs.sort(key=lambda item: getattr(item, sort_key), reverse=reverse)

        total = len(jobs)
        summary_counter = Counter(item.status for item in jobs)
        summary = {
            "uploaded": summary_counter.get("uploaded", 0),
            "queued": summary_counter.get("queued", 0),
            "submitting": summary_counter.get("submitting", 0),
            "parsing": summary_counter.get("parsing", 0),
            "parsed": summary_counter.get("parsed", 0),
            "converting": summary_counter.get("converting", 0),
            "completed": summary_counter.get("completed", 0),
            "failed": summary_counter.get("failed", 0),
            "canceled": summary_counter.get("canceled", 0),
        }
        start = (page - 1) * page_size
        end = start + page_size
        return jobs[start:end], total, summary

    def get_job(self, job_id: str):
        job = self.job_repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务不存在: {job_id}")
        return job

    def get_job_detail(self, job_id: str):
        job = self.get_job(job_id)
        return job, self.list_files(job_id), self.list_events(job_id)

    def list_files(self, job_id: str):
        return self.job_file_repository.list_files(job_id)

    def list_events(self, job_id: str):
        return self.job_event_repository.list_events(job_id)

    def get_file_by_type(self, job_id: str, file_type: str):
        for item in self.job_file_repository.list_files(job_id):
            if item.file_type == file_type:
                return item
        return None
