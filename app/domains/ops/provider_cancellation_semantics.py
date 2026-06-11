# File: app/domains/ops/provider_cancellation_semantics.py
# Purpose: Provide read-only MinerU provider cancellation semantics verification evidence.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.domains.resources.models import utc_now
from app.domains.ops.schemas import OpsProviderCancellationProvider


PROVIDER_CANCELLATION_SEMANTICS_DECISION = "unsupported_by_public_docs"
PROVIDER_CANCELLATION_SEMANTICS_STATUS = "verified_blocked"
PROVIDER_CANCELLATION_SEMANTICS_CHECKED_ON = "2026-06-07"


@dataclass(frozen=True, slots=True)
class OpsProviderCancellationSemanticsSource:
    """保存一次 provider cancellation 语义核查使用的公开来源摘要。"""

    label: str
    url: str
    source_type: Literal["primary_docs"]
    finding: str

    def to_dict(self) -> dict[str, str]:
        """转换为 API response 可校验的字典。"""

        return {
            "label": self.label,
            "url": self.url,
            "source_type": self.source_type,
            "finding": self.finding,
        }


@dataclass(frozen=True, slots=True)
class OpsProviderCancellationSemanticsReport:
    """汇总 MinerU provider cancellation 语义核查结论和安全声明。"""

    generated_at: datetime
    action_mode: Literal["semantics_verification"]
    provider: OpsProviderCancellationProvider
    verification_status: str
    checked_on: str
    decision: str
    public_docs_support_real_cancel: bool
    real_provider_cancel_allowed: bool
    supported_provider_operations: list[str]
    documented_task_statuses: list[str]
    unsupported_operations: list[str]
    blocking_reasons: list[str]
    recommended_next_steps: list[str]
    sources: list[OpsProviderCancellationSemanticsSource]
    safety: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        """转换为 API response 可校验的 JSON-safe 字典。"""

        return {
            "generated_at": self.generated_at,
            "action_mode": self.action_mode,
            "provider": self.provider,
            "verification_status": self.verification_status,
            "checked_on": self.checked_on,
            "decision": self.decision,
            "public_docs_support_real_cancel": self.public_docs_support_real_cancel,
            "real_provider_cancel_allowed": self.real_provider_cancel_allowed,
            "supported_provider_operations": list(self.supported_provider_operations),
            "documented_task_statuses": list(self.documented_task_statuses),
            "unsupported_operations": list(self.unsupported_operations),
            "blocking_reasons": list(self.blocking_reasons),
            "recommended_next_steps": list(self.recommended_next_steps),
            "sources": [source.to_dict() for source in self.sources],
            "safety": dict(self.safety),
        }


class OpsProviderCancellationSemanticsService:
    """生成 provider cancellation 语义核查报告，不调用 MinerU 或读取 secret。"""

    def build_report(self) -> OpsProviderCancellationSemanticsReport:
        """返回当前 MinerU cancellation 公开文档语义核查结论。"""

        return OpsProviderCancellationSemanticsReport(
            generated_at=utc_now(),
            action_mode="semantics_verification",
            provider="mineru",
            verification_status=PROVIDER_CANCELLATION_SEMANTICS_STATUS,
            checked_on=PROVIDER_CANCELLATION_SEMANTICS_CHECKED_ON,
            decision=PROVIDER_CANCELLATION_SEMANTICS_DECISION,
            public_docs_support_real_cancel=False,
            real_provider_cancel_allowed=False,
            supported_provider_operations=[
                "file_url_batch_request",
                "extract_task_submit",
                "extract_task_batch_submit",
                "extract_results_batch_query",
            ],
            documented_task_statuses=[
                "done",
                "waiting-file",
                "pending",
                "running",
                "failed",
                "converting",
            ],
            unsupported_operations=[
                "provider_cancel_endpoint_not_documented",
                "running_task_delete_not_supported_as_cancel_semantics",
                "provider_cancel_idempotency_not_documented",
                "provider_cancel_timeout_result_not_documented",
            ],
            blocking_reasons=[
                "provider_cancellation_unsupported_by_public_docs",
                "real_provider_cancellation_adapter_not_implemented",
                "local_job_mutation_after_provider_cancel_not_defined",
            ],
            recommended_next_steps=[
                "request_provider_written_confirmation_for_cancel_endpoint_and_status_semantics",
                "define_idempotency_timeout_and_error_contract_before_real_adapter",
                "keep_fake_cancellation_as_the_only_available_execution_path",
            ],
            sources=[
                OpsProviderCancellationSemanticsSource(
                    label="MinerU API docs index",
                    url="https://mineru.net/doc/docs/index_en/",
                    source_type="primary_docs",
                    finding=(
                        "公开 API 文档覆盖上传、提交解析和结果查询；未发现可用于取消运行中任务的公开 cancel endpoint。"
                    ),
                ),
                OpsProviderCancellationSemanticsSource(
                    label="MinerU API usage docs",
                    url="https://mineru.net/doc/docs/quick_usage/api_usage/",
                    source_type="primary_docs",
                    finding=(
                        "任务结果状态包含 done/waiting-file/pending/running/failed/converting；未给出取消请求、取消成功或幂等重试语义。"
                    ),
                ),
            ],
            safety={
                "read_only": True,
                "real_provider_cancel_executed": False,
                "provider_calls_executed": False,
                "local_job_mutated": False,
                "queue_mutated": False,
                "cleanup_executed": False,
                "delete_executed": False,
                "conversion_workflow_executed": False,
                "audit_events_written": False,
                "secret_values_exposed": False,
            },
        )
