"""仅为复核和表格证据的既有 Python 相等生成无损比较事实。"""
from __future__ import annotations

from datetime import datetime
import json
import math
from typing import Any

from pydantic import BaseModel


def datetime_query_key(value: datetime) -> tuple[int, str]:
    offset = value.utcoffset()
    delta = value.replace(tzinfo=None) - datetime(1970, 1, 1)
    if offset is not None:
        delta -= offset
    return ((delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds,
            "aware" if offset is not None else "naive")


def equality_key(value: Any) -> tuple[str, bool]:
    """完整文本而非哈希；NaN 在独立持久化读取间不可相等。"""
    comparable = True

    def normalize(item: Any):
        nonlocal comparable
        if item is None:
            return ["null"]
        if isinstance(item, (bool, int)):
            return ["number", str(int(item)), "1"]
        if isinstance(item, float):
            if math.isnan(item):
                comparable = False
                return ["nan"]
            if math.isinf(item):
                return ["infinity", "+" if item > 0 else "-"]
            numerator, denominator = item.as_integer_ratio()
            return ["number", str(numerator), str(denominator)]
        if isinstance(item, str):
            return ["string", item]
        if isinstance(item, datetime):
            micros, kind = datetime_query_key(item)
            return ["datetime", kind, str(micros)]
        if isinstance(item, BaseModel):
            # 比较声明字段的 Python 值，不能再经 JSON 序列化改变 metadata。
            return ["model", type(item).__module__, type(item).__qualname__,
                    normalize({name: getattr(item, name) for name in type(item).model_fields})]
        if isinstance(item, dict):
            return ["object", [[key, normalize(item[key])] for key in sorted(item)]]
        if isinstance(item, (list, tuple)):
            return ["list" if isinstance(item, list) else "tuple", [normalize(part) for part in item]]
        raise TypeError(f"持久化比较事实出现不支持的类型: {type(item).__name__}")

    normalized = normalize(value)
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":")), comparable


def receipt_file_key(file) -> tuple[str, bool]:
    excluded = {"etag", "updated_at", "expires_at", "review_source_revision"}
    return equality_key({name: getattr(file, name) for name in type(file).model_fields if name not in excluded})


def table_evidence_snapshot_key(job) -> tuple[str, bool]:
    from app.domains.document_jobs.table_evidence import table_evidence_snapshot_values
    return equality_key(table_evidence_snapshot_values(job))
