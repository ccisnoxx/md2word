from __future__ import annotations

# app/services/jobs/workflow_events.py: 将领域 workflow 事件意图映射为当前持久化 JobEvent 语义。

from typing import Any

from app.core.job_models import JobEvent
from app.core.job_workflow import WorkflowEventIntent


DEFAULT_EVENT_MESSAGES: dict[str, str] = {
    "job_created": "任务已创建，等待后台处理。",
    "stage_enqueued": "任务已进入后台队列。",
    "conversion_started": "开始执行 MinerU 包转换。",
    "parsed_result_conversion_started": "开始执行 parsed 结果后处理。",
    "parsed_result_package_recovered": "parsed 结果 zip 已恢复到本地 artifact。",
    "translation_started": "开始执行英文转中文翻译。",
    "translation_completed": "翻译完成，已进入 DOCX 渲染。",
    "translation_failed": "翻译阶段失败。",
    "job_failed": "后台转换失败。",
    "job_completed": "DOCX 已生成，可供下载。",
    "mineru_submit_started": "开始提交 MinerU。",
    "mineru_submit_failed": "MinerU 提交失败。",
    "mineru_submit_succeeded": "MinerU 提交成功，等待外部回调。",
    "mineru_result_polled": "已主动查询 MinerU 结果。",
    "mineru_callback_received": "收到 MinerU callback，等待后台处理。",
    "mineru_callback_processed": "MinerU callback 已记录。",
    "mineru_callback_failed": "MinerU callback 报告失败。",
    "job_retry_requested": "任务已重新加入后台执行队列。",
    "job_canceled": "任务已取消。",
    "cleanup_local_files": "本地运行态文件清理完成。",
}

DEFAULT_EVENT_STATUSES: dict[str, str] = {
    "job_created": "accepted",
    "stage_enqueued": "accepted",
    "conversion_started": "running",
    "parsed_result_conversion_started": "running",
    "parsed_result_package_recovered": "succeeded",
    "translation_started": "running",
    "translation_completed": "succeeded",
    "translation_failed": "failed",
    "job_failed": "failed",
    "job_completed": "succeeded",
    "mineru_submit_started": "running",
    "mineru_submit_failed": "failed",
    "mineru_submit_succeeded": "succeeded",
    "mineru_result_polled": "accepted",
    "mineru_callback_received": "accepted",
    "mineru_callback_processed": "succeeded",
    "mineru_callback_failed": "failed",
    "job_retry_requested": "accepted",
    "job_canceled": "succeeded",
    "cleanup_local_files": "succeeded",
}


def build_job_event_from_intent(
    intent: WorkflowEventIntent,
    *,
    trace_id: str,
    message: str | None = None,
    status: str | None = None,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> JobEvent:
    """把领域事件意图映射成当前持久化 JobEvent，允许调用方覆写展示细节。"""

    merged_details = dict(intent.details)
    if details:
        merged_details.update(details)
    resolved_error_code = error_code if error_code is not None else merged_details.get("error_code")
    return JobEvent(
        stage=intent.kind,
        message=message or DEFAULT_EVENT_MESSAGES[intent.kind],
        status=status or DEFAULT_EVENT_STATUSES[intent.kind],
        error_code=resolved_error_code,
        details=merged_details,
        trace_id=trace_id,
    )
