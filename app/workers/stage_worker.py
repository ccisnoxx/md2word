from __future__ import annotations

# app/workers/stage_worker.py: 独立 worker 进程轮询并消费 jobs stage message。

import logging
import time

from app.core.runtime import AppRuntime


class StageWorker:
    """轮询 stage message store，并在 worker 进程内执行 replayable stage。"""

    def __init__(self, runtime: AppRuntime, *, poll_interval_seconds: float | None = None) -> None:
        self.runtime = runtime
        self.poll_interval_seconds = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else runtime.settings.jobs_worker_poll_interval_seconds
        )
        self.logger = logging.getLogger("business")

    def run_once(self) -> int:
        """执行当前所有 replayable stage message，返回本轮尝试处理的数量。"""

        messages = self.runtime.stage_message_store.list_replayable_stage_messages()
        for message in messages:
            self.runtime.stage_service.dispatch_message(message.id)
        return len(messages)

    def run_forever(self) -> None:
        """持续轮询 stage message store；进程退出由外部 supervisor 或 Ctrl-C 控制。"""

        self.logger.info(
            "[worker_id=%s mode=%s] stage worker started",
            self.runtime.settings.jobs_worker_id,
            self.runtime.settings.jobs_worker_mode,
        )
        while True:
            processed_count = self.run_once()
            if processed_count:
                self.logger.info(
                    "[worker_id=%s processed=%s] stage worker loop completed",
                    self.runtime.settings.jobs_worker_id,
                    processed_count,
                )
            time.sleep(self.poll_interval_seconds)
