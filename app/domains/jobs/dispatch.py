from __future__ import annotations

# app/domains/jobs/dispatch.py: 定义后台 stage 调度入口和当前同进程 adapter。

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domains.jobs.stage import JobStageService


class StageDispatcherProtocol(Protocol):
    """后台 stage 调度入口，隐藏具体执行 adapter。"""

    def dispatch(self, message_id: str) -> None:
        """尝试驱动指定 stage message 执行。"""

    def replay_pending(self) -> None:
        """尝试重放当前可恢复的 stage message。"""


class InProcessStageDispatcher:
    """当前默认 dispatcher：同进程委托给 JobStageService。"""

    def __init__(self, stage_service: JobStageService) -> None:
        self.stage_service = stage_service

    def dispatch(self, message_id: str) -> None:
        """保持现有行为：直接调用 JobStageService.dispatch_message()。"""

        self.stage_service.dispatch_message(message_id)

    def replay_pending(self) -> None:
        """保持现有行为：直接调用 JobStageService.replay_pending()。"""

        self.stage_service.replay_pending()


class ExternalWorkerStageDispatcher:
    """外部 worker 模式 dispatcher：API 只入队，消息由独立 worker 消费。"""

    def dispatch(self, message_id: str) -> None:
        """保留统一端口；外部 worker 模式下请求进程不执行 stage。"""

        return None

    def replay_pending(self) -> None:
        """应用启动时不 replay；独立 worker 负责轮询 stage message store。"""

        return None
