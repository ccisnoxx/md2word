"""异常中心队列、详情与批量处置的请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentJobIncidentBulkRequest(BaseModel):
    job_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
