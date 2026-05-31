from __future__ import annotations

# app/infrastructure/persistence/file/stage_messages.py: file backend 的 stage message spool adapter。

from typing import Any

from app.domains.jobs.models import JobStageMessage
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileStageMessageStore:
    """用 file backend 读写 replayable stage message spool。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def put_stage_message(self, message: JobStageMessage) -> None:
        self.backend.write_json(
            self.backend.stage_messages_dir / f"{message.id}.json",
            message.model_dump(mode="json"),
        )

    def get_stage_message(self, message_id: str) -> JobStageMessage | None:
        path = self.backend.stage_messages_dir / f"{message_id}.json"
        if not path.exists():
            return None
        return JobStageMessage.model_validate(self.backend.read_json(path, {}))

    def update_stage_message(self, message_id: str, **patch: Any) -> JobStageMessage:
        existing = self.get_stage_message(message_id)
        if existing is None:
            raise FileNotFoundError(f"stage message 不存在: {message_id}")
        updated = existing.model_copy(update=patch)
        self.put_stage_message(updated)
        return updated

    def list_replayable_stage_messages(self) -> list[JobStageMessage]:
        messages: list[JobStageMessage] = []
        for path in sorted(self.backend.stage_messages_dir.glob("*.json")):
            message = JobStageMessage.model_validate(self.backend.read_json(path, {}))
            if message.status in {"pending", "running"}:
                messages.append(message)
        return messages

    def list_stage_messages(self) -> list[JobStageMessage]:
        return [
            JobStageMessage.model_validate(self.backend.read_json(path, {}))
            for path in sorted(self.backend.stage_messages_dir.glob("*.json"))
        ]

    def list_pending_stage_messages(self) -> list[JobStageMessage]:
        return self.list_replayable_stage_messages()

    def count_stage_messages_by_status(self) -> dict[str, int]:
        counts = {"pending": 0, "running": 0, "failed": 0}
        for path in sorted(self.backend.stage_messages_dir.glob("*.json")):
            message = JobStageMessage.model_validate(self.backend.read_json(path, {}))
            counts[message.status] = counts.get(message.status, 0) + 1
        return counts

    def delete_stage_message(self, message_id: str) -> None:
        (self.backend.stage_messages_dir / f"{message_id}.json").unlink(missing_ok=True)
