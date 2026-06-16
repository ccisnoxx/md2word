from __future__ import annotations

# app/infrastructure/persistence/mysql/stage_messages.py: MySQL backend 的 stage message spool adapter。

from typing import Any

from app.domains.jobs.models import JobStageMessage
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlStageMessageStore:
    """用 MySQL backend 读写 replayable stage message spool。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def put_stage_message(self, message: JobStageMessage) -> None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO stage_messages (message_id, job_id, status, payload, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        job_id = VALUES(job_id),
                        status = VALUES(status),
                        payload = VALUES(payload),
                        created_at = VALUES(created_at),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        message.id,
                        message.job_id,
                        message.status,
                        self.backend.dump_payload(message),
                        message.created_at.isoformat(),
                        message.updated_at.isoformat(),
                    ),
                )

    def get_stage_message(self, message_id: str) -> JobStageMessage | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM stage_messages WHERE message_id = %s",
                    (message_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return JobStageMessage.model_validate_json(row["payload"])

    def update_stage_message(self, message_id: str, **patch: Any) -> JobStageMessage:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM stage_messages WHERE message_id = %s",
                    (message_id,),
                )
                row = cursor.fetchone()
            if row is None:
                raise FileNotFoundError(f"stage message 不存在: {message_id}")
            updated = JobStageMessage.model_validate_json(row["payload"]).model_copy(update=patch)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE stage_messages
                    SET job_id = %s, status = %s, payload = %s, created_at = %s, updated_at = %s
                    WHERE message_id = %s
                    """,
                    (
                        updated.job_id,
                        updated.status,
                        self.backend.dump_payload(updated),
                        updated.created_at.isoformat(),
                        updated.updated_at.isoformat(),
                        message_id,
                    ),
                )
        return updated

    def list_replayable_stage_messages(self) -> list[JobStageMessage]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payload FROM stage_messages
                    WHERE status IN ('pending', 'running')
                    ORDER BY created_at, message_id
                    """
                )
                rows = cursor.fetchall()
        return [JobStageMessage.model_validate_json(row["payload"]) for row in rows]

    def list_stage_messages(self) -> list[JobStageMessage]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payload FROM stage_messages
                    ORDER BY created_at, message_id
                    """
                )
                rows = cursor.fetchall()
        return [JobStageMessage.model_validate_json(row["payload"]) for row in rows]

    def list_pending_stage_messages(self) -> list[JobStageMessage]:
        return self.list_replayable_stage_messages()

    def count_stage_messages_by_status(self) -> dict[str, int]:
        counts = {"pending": 0, "running": 0, "failed": 0}
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT status, COUNT(*) AS count FROM stage_messages GROUP BY status")
                rows = cursor.fetchall()
        for row in rows:
            counts[row["status"]] = int(row["count"])
        return counts

    def delete_stage_message(self, message_id: str) -> None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM stage_messages WHERE message_id = %s", (message_id,))
