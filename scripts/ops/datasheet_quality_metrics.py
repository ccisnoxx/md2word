#!/usr/bin/env python3
"""按固定样本计划复算 Datasheet 质量指标。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import fmean
from typing import Any


OBSERVATION_VERSION = "datasheet-quality-observations/v1"
REPORT_VERSION = "datasheet-quality-metrics/v1"
BASELINE_VERSION = "datasheet-quality-baseline/v1"
BASELINE_REPORT_VERSION = "datasheet-quality-baseline-report/v1"
MANUAL_REVIEW_VERSION = "datasheet-quality-manual-reviews/v1"
GROUP_FIELDS = ("cohort", "evidence_level", "mode")
BLOCKER_FIELDS = ("code", "scope", "delivery_status")
VISUAL_LAYOUT_COUNTS = ("overflow", "clipped")


def _object(value: Any, field: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{field} 必须为对象。")
    return value


def _items(value: Any, field: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{field} 必须为数组。")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 必须为非空字符串。")
    return value


def _count(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} 必须为非负整数。")
    return value


def _number(value: Any, field: str, *, nonnegative: bool = True) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or (nonnegative and value < 0):
        raise ValueError(f"{field} 数值无效。")
    return value


def _counts(value: Any, field: str) -> dict[str, int]:
    return {_text(key, field): _count(count, field) for key, count in _object(value, field).items()}


def _index(payload: Any, field: str) -> dict[tuple[str, str], dict]:
    rows = {}
    for item in _items(payload, field):
        row = _object(item, field)
        key = (_text(row.get("sample_id"), "sample_id"), _text(row.get("mode"), "mode"))
        if key in rows:
            raise ValueError(f"{field} 中的 sample_id 和 mode 组合重复。")
        rows[key] = row
    return rows


def _optional_object(row: dict, field: str) -> dict | None:
    value = row.get(field)
    return None if value is None else _object(value, field)


def _ratio(matched: int, expected: int | None, assessed: int, *, reason: str | None = None) -> dict:
    if not 0 <= matched <= assessed or (expected is not None and assessed > expected):
        raise ValueError("匹配数量、已评估数量与预期数量不一致。")
    if expected is None or expected > 0 and assessed == 0:
        status = "not_measured"
    elif expected == 0:
        status = "not_applicable"
    elif assessed < expected:
        status = "partial"
    else:
        status = "measured"
    return {
        "status": status,
        "numerator": matched,
        "denominator": expected,
        "value": matched / expected if expected else None,
        "assessed": assessed,
        "unassessed": expected - assessed if expected is not None else None,
        "coverage": assessed / expected if expected else None,
        "reason": _text(reason, "reason") if reason is not None else None,
    }


def _combined_ratio(ratios: list[dict]) -> dict:
    known = [ratio for ratio in ratios if ratio["denominator"] is not None]
    missing = len(ratios) - len(known)
    result = _ratio(
        sum(ratio["numerator"] for ratio in known),
        sum(ratio["denominator"] for ratio in known) if known or not ratios else None,
        sum(ratio["assessed"] for ratio in known),
    )
    result["annotated_samples"] = len(known)
    result["unannotated_samples"] = missing
    return result


def _conversion(raw: dict | None) -> dict:
    if raw is None:
        return {"status": "not_run", "success": False, "reason": "not_run"}
    status = _text(raw.get("status"), "conversion.status")
    available = raw.get("docx_available")
    openable = raw.get("docx_openable")
    for field, value in (("docx_available", available), ("docx_openable", openable)):
        if value is not None and type(value) is not bool:
            raise ValueError(f"conversion.{field} 必须为布尔值。")
    success = status == "succeeded" and available is True and openable is True
    reason = raw.get("reason")
    if reason is None and not success:
        if status != "succeeded":
            reason = status
        elif available is False:
            reason = "docx_unavailable"
        elif openable is False:
            reason = "docx_not_openable"
        else:
            reason = "docx_unverified"
    return {"status": status, "success": success, "reason": _text(reason, "conversion.reason") if reason is not None else None}


def _blocker(raw: dict) -> dict:
    return {field: _text(raw.get(field), f"blocker.{field}") for field in BLOCKER_FIELDS}


def _table(plan: dict, raw: dict | None, reason: str | None) -> dict:
    expected = plan.get("expected_tables")
    if expected is None:
        return _ratio(0, None, 0, reason=reason or "annotation_unavailable")
    expected = _count(expected, "expected_tables")
    if raw is None:
        return _ratio(0, expected, 0, reason=(reason or "table_not_observed") if expected else None)
    assessed = _count(raw.get("assessed", expected), "table.assessed")
    result = _ratio(
        _count(raw.get("matched"), "table.matched"),
        expected,
        assessed,
        reason=reason or ("table_coverage_incomplete" if assessed < expected else None),
    )
    result["unexpected"] = _count(raw.get("unexpected", 0), "table.unexpected")
    result["duplicate"] = _count(raw.get("duplicate", 0), "table.duplicate")
    result["reasons"] = raw.get("reasons", [])
    return result


def _tokens(plan: dict, raw: dict | None, reason: str | None) -> dict:
    expected = plan.get("expected_tokens")
    if expected is None:
        return {**_ratio(0, None, 0, reason=reason or "annotation_unavailable"), "by_kind": {}}
    expected = _counts(expected, "expected_tokens")
    matched = {} if raw is None else _counts(raw.get("matched"), "tokens.matched")
    assessed = {} if raw is None else _counts(raw.get("assessed", expected), "tokens.assessed")
    extras = {
        field: _counts((raw or {}).get(field, {}), f"tokens.{field}")
        for field in ("extras", "duplicates", "misplaced")
    }
    kinds = expected.keys() | matched.keys() | assessed.keys()
    for counts in extras.values():
        kinds |= counts.keys()
    by_kind = {
        kind: {
            **_ratio(matched.get(kind, 0), expected.get(kind, 0), assessed.get(kind, 0)),
            **{field: counts.get(kind, 0) for field, counts in extras.items()},
        }
        for kind in sorted(kinds)
    }
    expected_count = sum(expected.values())
    assessed_count = sum(assessed.values())
    if reason is None and assessed_count < expected_count:
        reason = "tokens_not_observed" if raw is None else "token_coverage_incomplete"
    result = _ratio(sum(matched.values()), expected_count, assessed_count, reason=reason)
    return {**result, "by_kind": by_kind, "reasons": (raw or {}).get("reasons", [])}


def _bbox(raw: Any) -> tuple[float, ...]:
    values = tuple(_number(value, "visual.region.bbox", nonnegative=False) for value in _items(raw, "visual.region.bbox"))
    if len(values) != 4 or values[0] > values[2] or values[1] > values[3]:
        raise ValueError("视觉区域边界必须按左、上、右、下四个坐标记录。")
    return values


def _visual(plan: dict, raw: dict | None, reason: str | None) -> dict:
    raw = raw or {}
    layout_counts = {
        field: _count(raw[field], f"visual.{field}") if raw.get(field) is not None else None
        for field in VISUAL_LAYOUT_COUNTS
    }
    pages = plan.get("expected_visual_pages")
    regions = plan.get("expected_visual_regions")
    if pages is None or regions is None:
        return {"pages": _ratio(0, None, 0), "regions": _ratio(0, None, 0), "offsets": [],
                "reason": reason or "annotation_unavailable", **layout_counts}
    pages = _count(pages, "expected_visual_pages")
    regions = _count(regions, "expected_visual_regions")
    matched_pages = _count(raw.get("matched_pages", 0), "visual.matched_pages")
    offsets = {}
    for item in _items(raw.get("regions", []), "visual.regions"):
        region = _object(item, "visual.region")
        region_id = _text(region.get("id"), "visual.region.id")
        if region_id in offsets:
            raise ValueError("视觉区域 ID 重复。")
        source = _bbox(region.get("source_bbox"))
        result = _bbox(region.get("result_bbox"))
        offsets[region_id] = fmean(abs(left - right) for left, right in zip(source, result))
    reason = raw.get("reason") or reason
    if reason is None and (matched_pages < pages or len(offsets) < regions):
        reason = "visual_coverage_incomplete" if raw else "visual_not_observed"
    return {
        "pages": _ratio(matched_pages, pages, matched_pages),
        "regions": _ratio(len(offsets), regions, len(offsets)),
        "offsets": [{"id": region_id, "offset": value} for region_id, value in sorted(offsets.items())],
        **layout_counts,
        "reason": _text(reason, "visual.reason") if reason is not None else None,
    }


def _measurement(value: int | float | None, reason: str | None = None) -> dict:
    return {
        "status": "not_measured" if value is None else "measured",
        "value": value,
        "reason": _text(reason, "reason") if reason is not None else None,
    }


def _manual(raw: dict | None, missing: dict) -> tuple[dict, dict]:
    raw = raw or {}
    edits = raw.get("edits")
    edit_count = None
    if edits is not None:
        fixed = set()
        for item in _items(edits, "manual.edits"):
            edit = _object(item, "manual.edit")
            defect_id = _text(edit.get("id"), "manual.edit.id")
            if _text(edit.get("disposition"), "manual.edit.disposition") == "fixed":
                fixed.add(defect_id)
        edit_count = len(fixed)

    rounds = raw.get("rounds")
    review_seconds = None
    incomplete = False
    if rounds is not None:
        rounds = _items(rounds, "manual.rounds")
        incomplete = not rounds
        seconds = []
        seen_rounds = set()
        for item in rounds:
            review = _object(item, "manual.round")
            key = (_text(review.get("id"), "manual.round.id"), _text(review.get("reviewer"), "manual.round.reviewer"))
            if key in seen_rounds:
                raise ValueError("同一审核人员的审核轮次重复。")
            seen_rounds.add(key)
            spans = []
            for item in _items(review.get("intervals", []), "manual.round.intervals"):
                span = _object(item, "manual.round.interval")
                if span.get("start_seconds") is None or span.get("end_seconds") is None:
                    incomplete = True
                    continue
                start = _number(span["start_seconds"], "manual.round.interval.start_seconds")
                end = _number(span["end_seconds"], "manual.round.interval.end_seconds")
                if end < start:
                    raise ValueError("审核区间结束时间早于开始时间。")
                spans.append((start, end))
            ordered = sorted(spans)
            if any(previous[1] > current[0] for previous, current in zip(ordered, ordered[1:])):
                raise ValueError("同一审核轮次的有效区间重叠。")
            incomplete |= not ordered
            seconds.extend(end - start for start, end in ordered)
        if not incomplete:
            review_seconds = math.fsum(seconds)
    reason = raw.get("reason") or ("incomplete_review_round" if incomplete else None)
    return (
        _measurement(edit_count, (missing.get("edits") or raw.get("reason") or "edits_not_recorded") if edit_count is None else None),
        _measurement(review_seconds / 60 if review_seconds is not None else None,
                     (missing.get("review_time") or reason or "review_time_not_recorded") if review_seconds is None else None),
    )


def measure_cost(raw: dict | None, reason: str | None = None) -> dict:
    """校验费用口径并计算已覆盖全部分项的总额。"""
    if raw is None:
        return _measurement(None, reason or "cost_not_recorded")
    complete = raw.get("complete")
    if type(complete) is not bool:
        raise ValueError("cost.complete 必须为布尔值。")
    currency = _text(raw.get("currency"), "cost.currency")
    basis = _text(raw.get("basis"), "cost.basis")
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha() or not currency.isupper():
        raise ValueError("cost.currency 必须为三个大写英文字母。")
    if basis not in {"actual", "estimated"}:
        raise ValueError("cost.basis 必须为 actual 或 estimated。")
    reference = _text(raw.get("reference"), "cost.reference")
    components = {
        key: _number(value, "cost.components")
        for key, value in _object(raw.get("components"), "cost.components").items()
    }
    if components.keys() - {"parser", "translation"} or complete and components.keys() != {"parser", "translation"}:
        raise ValueError("费用分项必须使用 parser 和 translation，完整费用须包含两项。")
    amount = float(sum(Decimal(str(value)) for value in components.values())) if complete else None
    if amount is not None and not math.isfinite(amount):
        raise ValueError("费用合计必须为有限数值。")
    return {
        **_measurement(amount, None if complete else raw.get("reason") or reason or "partial_cost"),
        "currency": currency,
        "basis": basis,
        "reference": reference,
        "components": components,
    }


def _latency(raw: dict | None, reason: str | None) -> dict:
    if raw is None:
        return _measurement(None, reason or "latency_not_recorded")
    kind = _text(raw.get("kind"), "latency.kind")
    if kind not in {"end_to_end", "local_replay"}:
        raise ValueError("latency.kind 必须为 end_to_end 或 local_replay。")
    result = {**_measurement(_number(raw.get("seconds"), "latency.seconds")), "kind": kind}
    interval = raw.get("poll_interval_seconds")
    if interval is not None:
        result["poll_interval_seconds"] = _number(interval, "latency.poll_interval_seconds")
    return result


def _analyze(plan: dict, observation: dict) -> dict:
    identity = {field: _text(plan.get(field), field) for field in ("sample_id", *GROUP_FIELDS)}
    outcome = plan.get("expected_outcome")
    conversion = _conversion(_optional_object(observation, "conversion"))
    missing = _optional_object(observation, "missing") or {}
    row = {
        **identity,
        "expected_outcome": outcome,
        "conversion": conversion,
        "cost": measure_cost(_optional_object(observation, "cost"), missing.get("cost")),
        "latency_seconds": _latency(_optional_object(observation, "latency"), missing.get("latency")),
    }
    if outcome == "blocked":
        expected = _blocker(_object(plan.get("expected_blocker"), "expected_blocker"))
        raw = _optional_object(observation, "blocker")
        actual = _blocker(raw) if raw is not None else None
        row["blocker"] = {"expected": expected, "actual": actual,
                          "status": "not_measured" if actual is None else "matched" if actual == expected else "mismatch",
                          "reason": (missing.get("blocker") or conversion["reason"]) if actual is None else None}
        return row
    if outcome != "normal":
        raise ValueError("expected_outcome 必须为 normal 或 blocked。")
    table = _optional_object(observation, "table")
    tokens = _optional_object(observation, "tokens")
    visual = _optional_object(observation, "visual")
    if any(item is not None for item in (table, tokens, visual)) and not conversion["success"]:
        raise ValueError("表格、Token 与页面匹配必须绑定成功且可打开的产物。")
    edits, review_time = _manual(_optional_object(observation, "manual"), missing)
    return {
        **row,
        "table": _table(plan, table, missing.get("table")),
        "tokens": _tokens(plan, tokens, missing.get("tokens")),
        "visual": _visual(plan, visual, missing.get("visual")),
        "edits": edits,
        "review_time_minutes": review_time,
    }


def _distribution(values: list[int | float]) -> dict:
    ordered = sorted(values)
    size = len(ordered)
    return {
        "count": size,
        "mean": fmean(ordered) if size else None,
        "p50": ordered[math.ceil(size * 0.50) - 1] if size else None,
        "p95": ordered[math.ceil(size * 0.95) - 1] if size else None,
    }


def _measured_distribution(rows: list[dict], field: str) -> dict:
    values = [row[field]["value"] for row in rows if row[field]["status"] == "measured"]
    return {
        **_distribution(values),
        "planned": len(rows),
        "missing_reasons": dict(Counter(row[field]["reason"] for row in rows if row[field]["status"] == "not_measured")),
    }


def _summarize(rows: list[dict]) -> dict:
    normal = [row for row in rows if row["expected_outcome"] == "normal"]
    blockers = [row["blocker"] for row in rows if row["expected_outcome"] == "blocked"]
    successes = sum(row["conversion"]["success"] for row in normal)
    assessed = sum(row["conversion"]["status"] != "not_run" for row in normal)
    table = [row["table"] for row in normal]
    tokens = [row["tokens"] for row in normal]
    visual = [row["visual"] for row in normal]
    layout_counts = {}
    for field in VISUAL_LAYOUT_COUNTS:
        values = [item[field] for item in visual if item[field] is not None]
        layout_counts[field] = sum(values) if values else None
        layout_counts[f"{field}_observed_samples"] = len(values)
    by_kind = defaultdict(list)
    costs = defaultdict(list)
    latency = defaultdict(lambda: defaultdict(list))
    for row in normal:
        for kind, counts in row["tokens"]["by_kind"].items():
            by_kind[kind].append(counts)
        cost = row["cost"]
        if cost["status"] == "measured":
            costs[(cost["currency"], cost["basis"])].append(cost["value"])
        time = row["latency_seconds"]
        if time["status"] == "measured":
            outcome = "succeeded" if row["conversion"]["success"] else row["conversion"]["reason"]
            latency[time["kind"]][outcome].append(time["value"])
    return {
        "sample_count": len(rows),
        "conversion_success": {
            **_ratio(successes, len(normal), assessed),
            "failure_reasons": dict(Counter(row["conversion"]["reason"] for row in normal if not row["conversion"]["success"])),
        },
        "blocking_cases": {"planned": len(blockers), **Counter(blocker["status"] for blocker in blockers)},
        "table_structure": {
            **_combined_ratio(table),
            "unexpected": sum(item.get("unexpected", 0) for item in table),
            "duplicate": sum(item.get("duplicate", 0) for item in table),
        },
        "technical_tokens": {
            **_combined_ratio(tokens),
            "by_kind": {
                kind: {
                    **_combined_ratio(counts),
                    **{field: sum(row[field] for row in counts) for field in ("extras", "duplicates", "misplaced")},
                }
                for kind, counts in sorted(by_kind.items())
            },
        },
        "page_visual": {
            "pages": _combined_ratio([item["pages"] for item in visual]),
            "regions": _combined_ratio([item["regions"] for item in visual]),
            "offset": _distribution([region["offset"] for item in visual for region in item["offsets"]]),
            **layout_counts,
        },
        "manual_edits": _measured_distribution(normal, "edits"),
        "manual_review_minutes": _measured_distribution(normal, "review_time_minutes"),
        "cost": {
            "planned": len(normal),
            "missing_reasons": dict(Counter(row["cost"]["reason"] for row in normal if row["cost"]["status"] == "not_measured")),
            "by_currency_and_basis": [
                {"currency": currency, "basis": basis, **_distribution(values)}
                for (currency, basis), values in sorted(costs.items())
            ],
        },
        "latency_seconds": {
            "planned": len(normal),
            "missing_reasons": dict(Counter(
                row["latency_seconds"]["reason"] for row in normal if row["latency_seconds"]["status"] == "not_measured"
            )),
            "by_kind_and_outcome": {
                kind: {outcome: _distribution(values) for outcome, values in sorted(outcomes.items())}
                for kind, outcomes in sorted(latency.items())
            },
        },
    }


def build_report(payload: dict) -> dict:
    """按计划项对账，再按样本组、模式和证据层级汇总。"""
    payload = _object(payload, "原始观测")
    if payload.get("schema_version") != OBSERVATION_VERSION:
        raise ValueError("原始观测 schema_version 不受支持。")
    plans = _index(payload.get("plan"), "plan")
    observations = _index(payload.get("observations"), "observations")
    if observations.keys() - plans.keys():
        raise ValueError("存在未列入固定计划的观测。")

    samples = [_analyze(plan, observations.get(key, {})) for key, plan in sorted(plans.items())]
    groups = defaultdict(list)
    for sample in samples:
        groups[tuple(sample[field] for field in GROUP_FIELDS)].append(sample)
    return {
        "schema_version": REPORT_VERSION,
        "metadata": _object(payload.get("metadata", {}), "metadata"),
        "samples": samples,
        "groups": [
            {**dict(zip(GROUP_FIELDS, group)), **_summarize(rows)}
            for group, rows in sorted(groups.items())
        ],
    }


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("输入 JSON 包含重复键。")
        result[key] = value
    return result


def read_metrics_input(path: Path) -> tuple[dict, str]:
    """拒绝重复 JSON 字段，并保留原始字节的指纹。"""
    content = path.read_bytes()
    payload = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
    return _object(payload, "输入 JSON"), hashlib.sha256(content).hexdigest()


def _sha256(value: Any, field: str) -> str:
    digest = _text(value, field)
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"{field} 必须为 64 位小写十六进制 SHA-256。")
    return digest


def _attach_manual_reviews(observations: dict, manual: dict) -> dict:
    """以运行、计划项及产物对账人工数据，仅为本次计算叠加。"""
    if manual.get("schema_version") != MANUAL_REVIEW_VERSION or manual.keys() - {"schema_version", "reviews"}:
        raise ValueError("人工审核文件版本或字段不受支持。")
    reviews = _index(manual.get("reviews"), "reviews")
    plans = _index(observations.get("plan"), "plan")
    rows = _index(observations.get("observations"), "observations")
    for key, review in reviews.items():
        if review.keys() - {"sample_id", "mode", "initial_docx_sha256", "revisions", "edits", "rounds"}:
            raise ValueError("人工审核记录含有未定义字段。")
        row = rows.get(key)
        if plans.get(key, {}).get("expected_outcome") != "normal" or row is None or not _conversion(
            _optional_object(row, "conversion")
        )["success"]:
            raise ValueError("人工审核须绑定到本次计划中已成功且可打开的 DOCX。")
        if row.get("manual") is not None:
            raise ValueError("人工审核文件不能覆盖已有人工观测。")
        initial = _sha256(review.get("initial_docx_sha256"), "reviews.initial_docx_sha256")
        artifacts = _optional_object(row, "artifacts") or {}
        recorded = [artifacts[name] for name in ("docx_sha256", "reviewed_docx_sha256")
                    if artifacts.get(name) is not None]
        if not recorded or any(initial != digest for digest in recorded):
            raise ValueError("首次 DOCX 的 SHA-256 与本次运行观测不一致。")

        document_hashes = {initial}
        for revision in _items(review.get("revisions", []), "reviews.revisions"):
            digest = _sha256(revision, "reviews.revisions")
            if digest in document_hashes:
                raise ValueError("人工审核的产物指纹重复。")
            document_hashes.add(digest)
        if "rounds" in review:
            for item in _items(review["rounds"], "reviews.rounds"):
                round_ = _object(item, "reviews.round")
                if _sha256(round_.get("docx_sha256"), "reviews.round.docx_sha256") not in document_hashes:
                    raise ValueError("审核轮次须绑定到首次 DOCX 或已登记修订产物。")
        if "edits" in review:
            for item in _items(review["edits"], "reviews.edits"):
                edit = _object(item, "reviews.edit")
                if _text(edit.get("disposition"), "reviews.edit.disposition") not in {"fixed", "reported", "accepted"}:
                    raise ValueError("人工修改记录的处置必须为 fixed、reported 或 accepted。")
        measurements = {name: review[name] for name in ("edits", "rounds") if name in review}
        missing = dict(_optional_object(row, "missing") or {})
        for field, reason_key in (("edits", "edits"), ("rounds", "review_time")):
            if field in measurements:
                missing.pop(reason_key, None)
        rows[key] = {**row, "manual": measurements, "missing": missing}
    return {**observations, "observations": list(rows.values())}


def _manifest_input(directory: Path, value: Any, field: str) -> Path:
    path = Path(_text(value, field))
    if path.is_absolute():
        raise ValueError(f"{field} 须使用相对于基线清单的路径。")
    return directory / path


def _build_baseline(payload: dict, directory: Path, input_paths: list[Path]) -> dict:
    """逐次复算相互独立的运行快照，保留每份输入的字节指纹。"""
    if payload.keys() - {"schema_version", "runs"}:
        raise ValueError("基线清单含有未定义字段。")
    runs = _items(payload.get("runs"), "runs")
    if not runs:
        raise ValueError("基线清单至少需要一次运行。")
    reports = []
    run_ids = set()
    for item in runs:
        run = _object(item, "runs")
        if run.keys() - {"id", "observations", "manual_reviews"}:
            raise ValueError("基线运行含有未定义字段。")
        run_id = _text(run.get("id"), "runs.id")
        if run_id in run_ids:
            raise ValueError("基线运行 ID 重复。")
        run_ids.add(run_id)
        observation_path = _manifest_input(directory, run.get("observations"), "runs.observations")
        input_paths.append(observation_path)
        observations, observation_hash = read_metrics_input(observation_path)
        entry = {"id": run_id, "observations_sha256": observation_hash}
        if "manual_reviews" in run:
            manual_path = _manifest_input(directory, run["manual_reviews"], "runs.manual_reviews")
            input_paths.append(manual_path)
            manual, entry["manual_reviews_sha256"] = read_metrics_input(manual_path)
            observations = _attach_manual_reviews(observations, manual)
        entry["report"] = build_report(observations)
        reports.append(entry)
    return {"schema_version": BASELINE_REPORT_VERSION, "runs": reports}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="按版本化计划复算 Datasheet 质量指标。")
    parser.add_argument("observations", type=Path, help="单次原始观测或多次运行基线清单 JSON。")
    parser.add_argument("--output", type=Path, help="报告 JSON 路径，默认输出到标准输出。")
    args = parser.parse_args(argv)
    try:
        input_paths = [args.observations]
        payload, _ = read_metrics_input(args.observations)
        report = (_build_baseline(payload, args.observations.parent, input_paths)
                  if payload.get("schema_version") == BASELINE_VERSION else build_report(payload))
        if args.output is not None and any(
            args.output.resolve() == path.resolve() or args.output.exists() and args.output.samefile(path)
            for path in input_paths
        ):
            raise ValueError("报告路径必须与清单、原始观测和人工审核文件分开。")
        content = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        if args.output is None:
            print(content)
        else:
            args.output.write_text(content + "\n", encoding="utf-8")
    except (OSError, ValueError, OverflowError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
