from __future__ import annotations

# app/domains/jobs/repository.py: 定义 jobs domain 依赖的持久化端口。

from typing import Any, Protocol

from app.domains.jobs.models import JobEvent, JobFile, JobRecord, JobStageMessage


class JobSnapshotRepositoryProtocol(Protocol):
    """Job 主记录读写合同。"""

    def create_job(self, job: JobRecord) -> None: ...
    def get_job(self, job_id: str) -> JobRecord | None: ...
    def list_jobs(self) -> list[JobRecord]: ...
    def update_job(self, job_id: str, **patch: Any) -> JobRecord: ...


class JobEventRepositoryProtocol(Protocol):
    """Job 审计事件读写合同。"""

    def append_event(self, job_id: str, event: JobEvent) -> None: ...
    def list_events(self, job_id: str) -> list[JobEvent]: ...


class JobFileRepositoryProtocol(Protocol):
    """Job artifact 记录读写合同。"""

    def upsert_file(self, job_id: str, file: JobFile) -> None: ...
    def list_files(self, job_id: str) -> list[JobFile]: ...


class JobRepositoryProtocol(
    JobSnapshotRepositoryProtocol,
    JobEventRepositoryProtocol,
    JobFileRepositoryProtocol,
    Protocol,
):
    """兼容旧的大 repository 命名；新代码优先依赖更窄协议。"""

    pass


class StageMessageStoreProtocol(Protocol):
    """Stage message spool 的最小存储合同。

    `pending` 和 `running` 都是 replayable；`running` 的 lease 字段用于观察
    卡住的 in-process worker，不作为跨进程排他锁；`failed` 保留现场且不自动
    replay。
    """

    def put_stage_message(self, message: JobStageMessage) -> None: ...
    def get_stage_message(self, message_id: str) -> JobStageMessage | None: ...
    def update_stage_message(self, message_id: str, **patch: Any) -> JobStageMessage: ...
    def list_replayable_stage_messages(self) -> list[JobStageMessage]: ...
    def count_stage_messages_by_status(self) -> dict[str, int]: ...
    def delete_stage_message(self, message_id: str) -> None: ...


class StageMessageRepositoryProtocol(StageMessageStoreProtocol, Protocol):
    """兼容旧命名；新代码应优先依赖 StageMessageStoreProtocol。"""

    pass
