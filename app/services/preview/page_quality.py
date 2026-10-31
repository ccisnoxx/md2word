"""派生预览的页级质量合同与纯规则；不读取文件，也不解码客户内容。"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from statistics import median
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.services.preview.models import SHA256_PATTERN

ANALYZER_VERSION = "native-page-observer/v1"
SCHEMA_VERSION = "page-quality-run/v1"
RULES = ("clipping", "overflow", "blank", "overlap", "density")
HASH_PATTERN = r"^[0-9a-f]{64}$"
Hash = Annotated[str, Field(pattern=HASH_PATTERN)]
Count = Annotated[int, Field(strict=True, ge=0)]
Reason = Literal["observer_unavailable", "geometry_unsupported", "png_unavailable", "uncalibrated",
                 "resource_exceeded", "observer_timeout", "invalid_observation", "unexpected_error",
                 "rule_disabled", "body_region_unavailable", "zero_denominator", "layout_unavailable"]
Rect = tuple[float, float, float, float]
THRESHOLDS = {
    "clipping": {"outside_area_ratio", "edge_ink_ratio", "edge_band_pt"},
    "overflow": {"outside_body_area_ratio"},
    "blank": {"max_ink_ratio", "max_foreground_count"},
    "overlap": {"intersection_min_area_ratio"},
    "density": {"min_ink_ratio", "max_ink_ratio", "median_absolute_deviation", "min_comparable_pages"},
}


class QualityContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _rect(value: Rect, *, normalized: bool = False) -> Rect:
    if value[0] > value[2] or value[1] > value[3] or (normalized and not all(0 <= x <= 1 for x in value)):
        raise ValueError("页面矩形的坐标或方向无效。")
    return value


class CalibrationEvidence(QualityContract):
    manifest_sha256: Hash
    input_set_sha256: Hash
    output_set_sha256: Hash
    review_reference: str = Field(min_length=1, max_length=200)
    approved: bool = False
    held_out_passed: bool = False
    domain: str = Field(min_length=1, max_length=100)
    profile_id: str = Field(min_length=1, max_length=100)
    profile_sha256: str = Field(pattern=SHA256_PATTERN)
    actual_context_sha256: Hash | None = None
    analyzer_version: Literal["native-page-observer/v1"] = ANALYZER_VERSION


class RulePolicy(QualityContract):
    enabled: bool = False
    thresholds: dict[str, float] = Field(default_factory=dict)
    calibration: CalibrationEvidence | None = None


class PageRegion(QualityContract):
    """规范化到有效页的明确区域；页选择不从源 PDF 坐标推断。"""

    page_indices: tuple[Count, ...]
    orientation: Literal["portrait", "landscape", "any"] = "any"
    body_bbox: Rect
    exclusion_bboxes: tuple[Rect, ...] = ()
    blank_exempt: bool = False
    density_group: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid_rects(self):
        _rect(self.body_bbox, normalized=True)
        for box in self.exclusion_bboxes:
            _rect(box, normalized=True)
        if len(set(self.page_indices)) != len(self.page_indices):
            raise ValueError("区域的页面选择不能重复。")
        return self


class PageQualityPolicy(QualityContract):
    schema_version: Literal["page-quality-policy/v1"] = "page-quality-policy/v1"
    enabled: bool = False
    policy_version: str = Field(default="v1", min_length=1, max_length=100)
    analyzer_version: Literal["native-page-observer/v1"] = ANALYZER_VERSION
    profile_id: str = Field(default="unconfigured", min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    profile_sha256: str = Field(default="sha256:" + "0" * 64, pattern=SHA256_PATTERN)
    applicability_domain: str = Field(default="unconfigured", min_length=1, max_length=100)
    production_ready: bool = False
    rules: dict[str, RulePolicy] = Field(default_factory=lambda: {name: RulePolicy() for name in RULES})
    regions: tuple[PageRegion, ...] = ()
    render_budget_seconds: float = Field(default=35, gt=0, le=300)
    observe_budget_seconds: float = Field(default=20, gt=0, le=300)
    registration_budget_seconds: float = Field(default=5, gt=0, le=300)
    max_objects: int = Field(default=100000, strict=True, ge=1, le=100000)
    max_pairs: int = Field(default=200000, strict=True, ge=1, le=10000000)
    max_report_bytes: int = Field(default=8 * 1024 * 1024, strict=True, ge=8192, le=8 * 1024 * 1024)
    max_examples: int = Field(default=20, strict=True, ge=0, le=100)
    ink_luminance_threshold: int = Field(default=245, strict=True, ge=0, le=254)

    @model_validator(mode="after")
    def rule_contract(self):
        if set(self.rules) != set(RULES):
            raise ValueError("页面质量策略必须明确包含五类规则。")
        for name, rule in self.rules.items():
            if rule.enabled and set(rule.thresholds) != THRESHOLDS[name]:
                raise ValueError("启用规则必须明确提供完整阈值。")
            if any(value < 0 for value in rule.thresholds.values()):
                raise ValueError("页面质量阈值不能为负数。")
            if name == "clipping" and rule.enabled and rule.thresholds["edge_band_pt"] <= 0:
                raise ValueError("启用裁切检查必须提供正的边带宽度。")
            for key, value in rule.thresholds.items():
                if key.endswith("ratio") and value > 1:
                    raise ValueError("面积或墨迹比例阈值必须位于零与一之间。")
            if name == "density" and rule.enabled:
                if rule.thresholds["min_ink_ratio"] > rule.thresholds["max_ink_ratio"] or rule.thresholds["min_comparable_pages"] < 2:
                    raise ValueError("密度规则的区间或可比页数无效。")
        selected = [index for region in self.regions for index in region.page_indices]
        if len(selected) != len(set(selected)):
            raise ValueError("同一页面不能匹配多个正文区域。")
        if self.production_ready and self.applicability_domain == "public_synthetic":
            raise ValueError("公开合成校准不能签署生产启用。")
        if len(canonical_bytes(self.model_dump(mode="json"))) > min(65536, self.max_report_bytes - 3072):
            raise ValueError("页面质量策略超过报告所能保留的身份预算。")
        return self


def parse_page_quality_policy(value: object) -> PageQualityPolicy:
    return PageQualityPolicy.model_validate(value)


def policy_sha256(policy: PageQualityPolicy) -> str:
    return _hash(policy.model_dump(mode="json"))


class NativeObject(QualityContract):
    object_id: str = Field(min_length=1, max_length=100)
    kind: Literal["char", "image", "path"]
    bbox: Rect
    text_line_id: str | None = Field(default=None, max_length=100)
    role: Literal["foreground", "background", "decoration"] = "foreground"

    @model_validator(mode="after")
    def bounds(self):
        _rect(self.bbox)
        return self


class RasterObservation(QualityContract):
    png_sha256: str = Field(pattern=SHA256_PATTERN)
    width: Annotated[int, Field(strict=True, gt=0)]
    height: Annotated[int, Field(strict=True, gt=0)]
    dpi_x: float = Field(gt=0)
    dpi_y: float = Field(gt=0)
    ink_pixels: Count
    total_pixels: Annotated[int, Field(strict=True, gt=0)]
    body_ink_pixels: Count | None = None
    body_pixels: Count | None = None
    edge_ink_pixels: Count
    edge_pixels: Count
    content_bbox: Rect | None = None

    @model_validator(mode="after")
    def counts(self):
        if (self.total_pixels != self.width * self.height or self.ink_pixels > self.total_pixels
                or self.edge_ink_pixels > self.edge_pixels or self.edge_pixels > self.total_pixels
                or (self.body_pixels is None) != (self.body_ink_pixels is None)
                or (self.body_pixels is not None and (self.body_ink_pixels > self.body_pixels or self.body_pixels > self.total_pixels))):
            raise ValueError("页面栅格统计的计数不一致。")
        if self.content_bbox is not None:
            _rect(self.content_bbox)
        return self


class PageObservation(QualityContract):
    preview_page_index: Count
    width_pt: float = Field(gt=0)
    height_pt: float = Field(gt=0)
    crop_box: Rect
    rotation: Literal[0, 90, 180, 270]
    geometry_supported: bool
    reason_code: Reason | None = None
    objects: tuple[NativeObject, ...] = ()
    raster: RasterObservation | None = None

    @model_validator(mode="after")
    def shape(self):
        _rect(self.crop_box)
        width, height = self.crop_box[2] - self.crop_box[0], self.crop_box[3] - self.crop_box[1]
        if self.rotation in {90, 270}:
            width, height = height, width
        if not math.isclose(width, self.width_pt, abs_tol=1e-6) or not math.isclose(height, self.height_pt, abs_tol=1e-6):
            raise ValueError("有效页面尺寸与裁剪和旋转不一致。")
        if len({obj.object_id for obj in self.objects}) != len(self.objects):
            raise ValueError("原生叶对象身份不能重复。")
        if not self.geometry_supported and self.reason_code is None:
            raise ValueError("缺失几何能力必须说明原因。")
        if self.raster is not None:
            if (not math.isclose(self.raster.dpi_x, self.raster.width / self.width_pt * 72, abs_tol=1e-6)
                    or not math.isclose(self.raster.dpi_y, self.raster.height / self.height_pt * 72, abs_tol=1e-6)):
                raise ValueError("页面 DPI 与有效尺寸不一致。")
        return self


class PageObservationBatch(QualityContract):
    schema_version: Literal["word-page-observation/v1"] = "word-page-observation/v1"
    status: Literal["ok", "incomplete", "error"]
    reason_code: Reason | None = None
    input_sha256: str = Field(pattern=SHA256_PATTERN)
    profile_id: str
    profile_sha256: str = Field(pattern=SHA256_PATTERN)
    analyzer_version: Literal["native-page-observer/v1"] = ANALYZER_VERSION
    analyzer_sha256: str = Field(default="sha256:" + "0" * 64, pattern=SHA256_PATTERN)
    dependencies_sha256: str = Field(default="sha256:" + "0" * 64, pattern=SHA256_PATTERN)
    policy_sha256: Hash
    page_count: Annotated[int, Field(strict=True, gt=0)]
    pages: tuple[PageObservation, ...] = ()

    @model_validator(mode="after")
    def continuity(self):
        if self.status == "ok" and (self.reason_code is not None or len(self.pages) != self.page_count):
            raise ValueError("完整观测必须覆盖全部页面。")
        if self.status != "ok" and self.reason_code is None:
            raise ValueError("未完成观测必须说明原因。")
        if self.pages and (len(self.pages) != self.page_count or any(page.preview_page_index != i for i, page in enumerate(self.pages))):
            raise ValueError("观测不能以截断页序声称完整。")
        return self


class PageQualityBinding(QualityContract):
    source_generation: Count
    result_file_id: str = Field(min_length=1, max_length=200)
    docx_sha256: str = Field(pattern=SHA256_PATTERN)
    preview_run_id: str = Field(min_length=1, max_length=200)
    attempt: Annotated[int, Field(strict=True, ge=1)]
    preview_pdf_file_id: str = Field(min_length=1, max_length=200)
    preview_pdf_sha256: str = Field(pattern=SHA256_PATTERN)
    page_count: Annotated[int, Field(strict=True, ge=1, le=10000)]
    profile_id: str = Field(min_length=1, max_length=100)
    profile_sha256: str = Field(pattern=SHA256_PATTERN)
    policy_sha256: Hash
    mapping_sha256: Hash | None = None
    actual_context_sha256: Hash | None = None


class RuleResult(QualityContract):
    rule_version: Literal["v1"] = "v1"
    checked: bool
    reason_code: Reason | None = None
    metrics: dict[str, float | int | None]
    units: dict[str, Literal["pt", "pt2", "ratio", "count", "char/pt2"]]

    @model_validator(mode="after")
    def coverage(self):
        if self.checked != (self.reason_code is None) or set(self.metrics) != set(self.units):
            raise ValueError("规则覆盖、原因和指标单位不一致。")
        return self


class QualityFlag(QualityContract):
    code: Literal["page_clip_risk", "page_overflow_risk", "unexpected_blank_page_suspected",
                  "page_overlap_suspected", "page_density_low", "page_density_high"]
    severity: Literal["warning", "info"] = "warning"
    rule_version: Literal["v1"] = "v1"
    preview_page_index: Count
    metric_refs: tuple[str, ...]
    evidence_kind: Literal["native_and_raster"] = "native_and_raster"
    manual_check_required: Literal[True] = True


class PageQualityResult(QualityContract):
    preview_page_index: Count
    rules: dict[str, RuleResult]
    flags: tuple[QualityFlag, ...]
    manual_checks: tuple[str, ...]
    content_bbox: Rect | None = None
    block_candidates: tuple[dict, ...] = ()
    candidate_block_ids: tuple[str, ...] = ()
    defect_block_ids: tuple[str, ...] = ()
    overlap_examples: tuple[tuple[str, str], ...] = ()
    overlap_examples_omitted: Count = 0


class PageQualityRun(QualityContract):
    schema_version: Literal["page-quality-run/v1"] = SCHEMA_VERSION
    producer: Literal["word_page_quality"] = "word_page_quality"
    id: str = Field(pattern=r"^page-quality:[0-9a-f]{64}$")
    binding: PageQualityBinding
    analyzer_version: Literal["native-page-observer/v1"] = ANALYZER_VERSION
    policy: PageQualityPolicy
    created_at: str = Field(min_length=1, max_length=100)
    evaluation_state: Literal["complete", "incomplete"]
    quality_status: Literal["pending", "passed", "warning"]
    reason_code: Reason | None
    manual_checks: tuple[Reason, ...]
    pages: tuple[PageQualityResult, ...]
    coverage: dict[str, dict[str, int]]
    counts: dict[str, int]
    run_sha256: Hash


def page_region(policy: PageQualityPolicy, page: PageObservation) -> PageRegion | None:
    orientation = "landscape" if page.width_pt > page.height_pt else "portrait"
    return next((region for region in policy.regions if page.preview_page_index in region.page_indices
                 and region.orientation in {"any", orientation}), None)


def absolute_rect(box: Rect, width: float, height: float) -> Rect:
    return box[0] * width, box[1] * height, box[2] * width, box[3] * height


def _area(box: Rect) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _intersection(a: Rect, b: Rect) -> Rect:
    return max(a[0], b[0]), max(a[1], b[1]), max(max(a[0], b[0]), min(a[2], b[2])), max(max(a[1], b[1]), min(a[3], b[3]))


def union_area(boxes: list[Rect]) -> float:
    """扫描线与覆盖树避免重复/嵌套 bbox 重复累加，复杂度 O(N log N)。"""
    boxes = [box for box in boxes if _area(box) > 0]
    if not boxes:
        return 0.0
    ys = sorted({value for box in boxes for value in (box[1], box[3])})
    ranks = {value: i for i, value in enumerate(ys)}
    cover, length = [0] * (4 * len(ys)), [0.0] * (4 * len(ys))

    def update(node, low, high, left, right, delta):
        if left <= low and high <= right:
            cover[node] += delta
        else:
            middle = (low + high) // 2
            if left < middle:
                update(node * 2, low, middle, left, right, delta)
            if right > middle:
                update(node * 2 + 1, middle, high, left, right, delta)
        length[node] = ys[high] - ys[low] if cover[node] else (0.0 if high - low == 1 else length[node * 2] + length[node * 2 + 1])

    events = sorted((x, delta, ranks[box[1]], ranks[box[3]]) for box in boxes for x, delta in ((box[0], 1), (box[2], -1)))
    previous, total = events[0][0], 0.0
    for x, delta, left, right in events:
        total += (x - previous) * length[1]
        update(1, 0, len(ys) - 1, left, right, delta)
        previous = x
    return total


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 0 else None


class _PairBudgetExceeded(Exception):
    pass


def _overlaps(objects: list[NativeObject], policy: PageQualityPolicy, budget: list[int]):
    active, count, maximum, examples = [], 0, 0.0, []
    for current in sorted(objects, key=lambda obj: obj.bbox[0]):
        active = [other for other in active if other.bbox[2] > current.bbox[0]]
        for other in active:
            budget[0] += 1
            if budget[0] > policy.max_pairs:
                raise _PairBudgetExceeded()
            if current.text_line_id is not None and current.text_line_id == other.text_line_id:
                continue
            denominator = min(_area(current.bbox), _area(other.bbox))
            overlap = _ratio(_area(_intersection(current.bbox, other.bbox)), denominator)
            if overlap is not None and overlap > 0:
                count += 1
                maximum = max(maximum, overlap)
                if len(examples) < policy.max_examples:
                    examples.append((other.object_id, current.object_id))
        active.append(current)
    return count, maximum if objects else None, examples


def _calibrated(rule: RulePolicy, policy: PageQualityPolicy, actual_context_sha256: str | None) -> bool:
    evidence = rule.calibration
    return bool(evidence and evidence.approved and evidence.held_out_passed
                and evidence.domain == policy.applicability_domain and evidence.profile_id == policy.profile_id
                and evidence.profile_sha256 == policy.profile_sha256
                and actual_context_sha256 is not None and evidence.actual_context_sha256 == actual_context_sha256
                and evidence.analyzer_version == policy.analyzer_version)


def _evaluate_page(page: PageObservation, policy: PageQualityPolicy, batch_reason: Reason | None, pair_budget: list[int], actual_context_sha256: str | None):
    region = page_region(policy, page)
    exclusions = [absolute_rect(box, page.width_pt, page.height_pt) for box in region.exclusion_bboxes] if region else []
    objects = [obj for obj in page.objects if obj.role == "foreground" and _area(obj.bbox) > 0
               and not any(_intersection(obj.bbox, box) == obj.bbox for box in exclusions)]
    boxes = list({obj.bbox for obj in objects})
    area = union_area(boxes)
    page_box = (0.0, 0.0, page.width_pt, page.height_pt)
    outside = max(0.0, area - union_area([_intersection(box, page_box) for box in boxes]))
    body = absolute_rect(region.body_bbox, page.width_pt, page.height_pt) if region else None
    body_area = _area(body) - union_area([_intersection(box, body) for box in exclusions]) if body else None
    body_foreground_area = None
    if body:
        excluded_foreground = []
        for box in boxes:
            for exclusion in exclusions:
                pair_budget[0] += 1
                if pair_budget[0] > policy.max_pairs:
                    raise _PairBudgetExceeded()
                excluded_foreground.append(_intersection(_intersection(box, body), exclusion))
        body_foreground_area = max(0.0, union_area([_intersection(box, body) for box in boxes]) - union_area(excluded_foreground))
    outside_body = max(0.0, area - union_area([_intersection(box, body) for box in boxes])) if body else None
    raster = page.raster
    overlap_count, overlap_max, examples = _overlaps(objects, policy, pair_budget)
    metrics = {
        "clipping": {"native_outside_area_pt2": outside, "foreground_union_area_pt2": area,
                     "outside_area_ratio": _ratio(outside, area), "outside_object_count": sum(_area(_intersection(box, page_box)) < _area(box) for box in boxes),
                     "max_outside_distance_pt": max((max(0, -box[0], -box[1], box[2] - page.width_pt, box[3] - page.height_pt) for box in boxes), default=0),
                     "edge_ink_ratio": _ratio(raster.edge_ink_pixels, raster.edge_pixels) if raster else None},
        "overflow": {"outside_body_area_ratio": _ratio(outside_body, area) if body else None,
                     "clearance_pt": min((min(box[0] - body[0], box[1] - body[1], body[2] - box[2], body[3] - box[3]) for box in boxes), default=None) if body else None,
                     "excluded_object_count": len(page.objects) - len(objects)},
        "blank": {"ink_area_ratio": _ratio(raster.ink_pixels, raster.total_pixels) if raster else None,
                  "foreground_object_count": len(objects), "char_count": sum(obj.kind == "char" for obj in objects)},
        "overlap": {"positive_pair_count": overlap_count, "max_intersection_min_area_ratio": overlap_max},
        "density": {"body_ink_ratio": _ratio(raster.body_ink_pixels, raster.body_pixels) if raster and raster.body_pixels is not None else None,
                    "native_foreground_body_area_ratio": _ratio(body_foreground_area, body_area) if body else None,
                    "char_density": _ratio(sum(obj.kind == "char" and _area(_intersection(obj.bbox, body)) > 0 for obj in objects), body_area) if body else None,
                    "group_median": None, "median_absolute_deviation": None},
    }
    output, flags, manual = {}, [], []
    for name in RULES:
        rule = policy.rules[name]
        reason = ("rule_disabled" if not rule.enabled else batch_reason or
                  (page.reason_code or "geometry_unsupported" if not page.geometry_supported else None) or
                  ("png_unavailable" if raster is None else None) or
                  ("body_region_unavailable" if name in {"overflow", "density"} and body is None else None) or
                  ("uncalibrated" if not _calibrated(rule, policy, actual_context_sha256) else None))
        if reason is None and name in {"clipping", "overflow", "overlap"} and area == 0:
            reason = "zero_denominator"
        if reason is None and name == "clipping" and metrics[name]["edge_ink_ratio"] is None:
            reason = "zero_denominator"
        if reason is None and name == "density" and metrics[name]["body_ink_ratio"] is None:
            reason = "zero_denominator"
        values = metrics[name]
        if (reason is None and name == "blank" and not (region and region.blank_exempt)
                and values["ink_area_ratio"] <= rule.thresholds["max_ink_ratio"]
                and values["foreground_object_count"] > rule.thresholds["max_foreground_count"]):
            # 白色、极淡或被盖印的叶对象仍有 bbox；原生计数不能代替其实际可见性。
            reason = "geometry_unsupported"
        units = {key: "pt2" if key.endswith("pt2") else "pt" if key.endswith("_pt") else "count" if "count" in key else "char/pt2" if key == "char_density" else "ratio" for key in values}
        output[name] = RuleResult(checked=reason is None, reason_code=reason, metrics=values, units=units)
        if reason is not None:
            if reason != "rule_disabled":
                manual.append(name + ":" + reason)
            continue
        t, code = rule.thresholds, None
        if name == "clipping" and (values["outside_area_ratio"] > t["outside_area_ratio"] or values["edge_ink_ratio"] is not None and values["edge_ink_ratio"] > t["edge_ink_ratio"]):
            code = "page_clip_risk"
        elif name == "overflow" and values["outside_body_area_ratio"] > t["outside_body_area_ratio"]:
            code = "page_overflow_risk"
        elif name == "blank" and values["ink_area_ratio"] <= t["max_ink_ratio"] and values["foreground_object_count"] <= t["max_foreground_count"] and not (region and region.blank_exempt):
            code = "unexpected_blank_page_suspected"
        elif name == "overlap" and values["max_intersection_min_area_ratio"] > t["intersection_min_area_ratio"]:
            code = "page_overlap_suspected"
        if code:
            flags.append(QualityFlag(code=code, preview_page_index=page.preview_page_index, metric_refs=tuple(name + "." + key for key in values)))
    return PageQualityResult(preview_page_index=page.preview_page_index, rules=output, flags=tuple(flags),
                             manual_checks=tuple(manual), content_bbox=raster.content_bbox if raster else None,
                             overlap_examples=tuple(examples), overlap_examples_omitted=overlap_count - len(examples))


def _associate(pages: list[dict], mapping: dict | None, binding: PageQualityBinding):
    if mapping is None or binding.mapping_sha256 is None:
        return
    from app.services.preview.page_mapping import MappingBinding, read_page_mapping
    try:
        parsed = read_page_mapping(mapping, binding=MappingBinding.model_validate(mapping["binding"]))
    except (ValidationError, ValueError, KeyError, TypeError, RecursionError):
        return
    if parsed is None or parsed.get("mapping_sha256") != binding.mapping_sha256:
        return
    mb = parsed["binding"]
    for key, value in {"source_generation": binding.source_generation, "result_file_id": binding.result_file_id,
                       "docx_sha256": binding.docx_sha256, "run_id": binding.preview_run_id, "attempt": binding.attempt,
                       "preview_pdf_file_id": binding.preview_pdf_file_id, "preview_pdf_sha256": binding.preview_pdf_sha256,
                       "page_count": binding.page_count, "profile_sha256": binding.profile_sha256}.items():
        if mb.get(key) != value:
            return
    for entry in parsed["entries"]:
        location, fallback = entry["location"], entry.get("fallback")
        index = location["preview_page_index"]
        association, confidence = location["kind"], location["confidence"]
        if index is None and fallback:
            index, association, confidence = fallback["page_index"], "navigation_fallback", "low"
        if index is None or index >= len(pages):
            continue
        candidate = {"block_id": entry["block_id"], "association": association, "confidence": confidence,
                     "source_spans": entry["source"]["source_spans"], "source_page_indices": sorted({span["page_index"] for span in entry["source"]["source_spans"] if isinstance(span.get("page_index"), int) and span["page_index"] >= 0})}
        pages[index]["block_candidates"].append(candidate)
        pages[index]["candidate_block_ids"].append(entry["block_id"])


def _finish_report(binding: PageQualityBinding, policy: PageQualityPolicy, pages: list[dict], created_at: str, reason: Reason | None) -> dict:
    coverage = {name: {"checked": sum(page["rules"][name]["checked"] for page in pages),
                       "not_checked": binding.page_count - sum(page["rules"][name]["checked"] for page in pages)} for name in RULES}
    enabled = [name for name in RULES if policy.rules[name].enabled]
    complete = bool(policy.enabled and enabled and reason is None and len(pages) == binding.page_count
                    and all(coverage[name]["not_checked"] == 0 for name in enabled))
    flags = sum(len(page["flags"]) for page in pages)
    report = {"schema_version": SCHEMA_VERSION, "producer": "word_page_quality",
              "id": "page-quality:" + _hash({"binding": binding.model_dump(mode="json"), "policy_sha256": policy_sha256(policy), "analyzer_version": policy.analyzer_version}),
              "binding": binding.model_dump(mode="json"), "analyzer_version": policy.analyzer_version,
              "policy": policy.model_dump(mode="json"), "created_at": created_at,
              "evaluation_state": "complete" if complete else "incomplete",
              "quality_status": ("warning" if flags else "passed") if complete else "pending", "reason_code": reason,
              "manual_checks": [reason] if reason else [],
              "pages": pages, "coverage": coverage,
              "counts": {"pages": binding.page_count, "observed_pages": len(pages), "flags": flags,
                         "manual_checks": sum(len(page["manual_checks"]) for page in pages) + (1 if reason else 0),
                         "checked_rules": sum(value["checked"] for value in coverage.values()),
                         "not_checked_rules": sum(value["not_checked"] for value in coverage.values())}}
    report["run_sha256"] = _hash(report)
    return report


def build_page_quality_run(*, binding: PageQualityBinding | dict, policy: PageQualityPolicy,
                           observation: PageObservationBatch | None = None, mapping: dict | None = None,
                           created_at: str, reason_code: Reason | None = None) -> dict:
    binding = PageQualityBinding.model_validate(binding)
    if (binding.policy_sha256 != policy_sha256(policy) or binding.profile_id != policy.profile_id or binding.profile_sha256 != policy.profile_sha256):
        raise ValueError("页面质量运行与冻结策略身份不一致。")
    pages, reason = [], reason_code
    try:
        if observation is None:
            reason = reason or "observer_unavailable"
        else:
            observation = PageObservationBatch.model_validate(observation.model_dump(mode="python"))
            if (observation.input_sha256 != binding.preview_pdf_sha256 or observation.page_count != binding.page_count
                    or observation.profile_id != binding.profile_id or observation.profile_sha256 != binding.profile_sha256
                    or observation.policy_sha256 != binding.policy_sha256 or observation.analyzer_version != policy.analyzer_version):
                reason = "invalid_observation"
            elif sum(len(page.objects) for page in observation.pages) > policy.max_objects:
                reason = "resource_exceeded"
            else:
                reason = reason or observation.reason_code
                budget = [0]
                pages = [_evaluate_page(page, policy, reason, budget, binding.actual_context_sha256).model_dump(mode="json") for page in observation.pages]
                groups = {}
                for page, result in zip(observation.pages, pages):
                    region = page_region(policy, page)
                    if region and result["rules"]["density"]["checked"]:
                        groups.setdefault(region.density_group, []).append(result)
                for group in groups.values():
                    middle = median(result["rules"]["density"]["metrics"]["body_ink_ratio"] for result in group)
                    for result in group:
                        metrics = result["rules"]["density"]["metrics"]
                        value, t = metrics["body_ink_ratio"], policy.rules["density"].thresholds
                        metrics["group_median"] = middle if len(group) >= t["min_comparable_pages"] else None
                        metrics["median_absolute_deviation"] = abs(value - middle) if metrics["group_median"] is not None else None
                        low, high = value < t["min_ink_ratio"], value > t["max_ink_ratio"]
                        if metrics["median_absolute_deviation"] is not None and metrics["median_absolute_deviation"] > t["median_absolute_deviation"]:
                            low, high = low or value < middle, high or value > middle
                        if low or high:
                            result["flags"].append(QualityFlag(code="page_density_low" if low else "page_density_high", preview_page_index=result["preview_page_index"], metric_refs=("density.body_ink_ratio",)).model_dump(mode="json"))
                _associate(pages, mapping, binding)
    except _PairBudgetExceeded:
        pages, reason = [], "resource_exceeded"
    except (ValidationError, ValueError, TypeError, KeyError, AttributeError):
        logging.getLogger("system").warning("页面质量计算未完成 reason=invalid_observation")
        pages, reason = [], "invalid_observation"
    except Exception:
        logging.getLogger("system").error("页面质量计算异常 reason=unexpected_error")
        pages, reason = [], "unexpected_error"
    report = _finish_report(binding, policy, pages, created_at, reason)
    if len(canonical_bytes(report)) > policy.max_report_bytes:
        report = _finish_report(binding, policy, [], created_at, "resource_exceeded")
    return report


def read_page_quality_run(value: object, *, binding: PageQualityBinding | dict | None = None,
                          policy: PageQualityPolicy | None = None) -> dict | None:
    """可选内层报告损坏只返回不可用；不替代外层 Artifact 的权限/完整性检查。"""
    try:
        if not isinstance(value, dict) or len(canonical_bytes(value)) > 8 * 1024 * 1024:
            return None
        model = PageQualityRun.model_validate(value)
        parsed = model.model_dump(mode="json")
        if canonical_bytes(parsed) != canonical_bytes(value):
            return None
        unsigned = {key: item for key, item in value.items() if key != "run_sha256"}
        if _hash(unsigned) != model.run_sha256 or policy_sha256(model.policy) != model.binding.policy_sha256:
            return None
        if binding is not None and model.binding != PageQualityBinding.model_validate(binding):
            return None
        if policy is not None and policy_sha256(policy) != model.binding.policy_sha256:
            return None
        if model.binding.profile_id != model.policy.profile_id or model.binding.profile_sha256 != model.policy.profile_sha256:
            return None
        if model.pages and (len(model.pages) != model.binding.page_count or any(page.preview_page_index != i or set(page.rules) != set(RULES) or page.defect_block_ids for i, page in enumerate(model.pages))):
            return None
        if any(flag.preview_page_index != page.preview_page_index for page in model.pages for flag in page.flags):
            return None
        for page in model.pages:
            for name, result in page.rules.items():
                rule = model.policy.rules[name]
                if result.checked and (not model.policy.enabled or not rule.enabled or not _calibrated(rule, model.policy, model.binding.actual_context_sha256)):
                    return None
                if not rule.enabled and (result.checked or result.reason_code != "rule_disabled"):
                    return None
        expected = _finish_report(model.binding, model.policy, parsed["pages"], model.created_at, model.reason_code)
        if any(parsed[key] != expected[key] for key in ("id", "coverage", "counts", "evaluation_state", "quality_status", "manual_checks")):
            return None
        if len(canonical_bytes(value)) > model.policy.max_report_bytes:
            return None
        return parsed
    except (ValidationError, ValueError, TypeError, KeyError, RecursionError):
        return None


validate_page_quality_run = read_page_quality_run


def page_quality_summary(run: dict) -> dict:
    parsed = read_page_quality_run(run)
    if parsed is None:
        return {"schema_version": SCHEMA_VERSION, "evaluation_state": "incomplete", "quality_status": "pending", "reason_code": "invalid_observation"}
    return {name: parsed[name] for name in ("schema_version", "evaluation_state", "quality_status", "reason_code", "counts")}


def page_quality_contribution(run: dict) -> dict:
    summary = page_quality_summary(run)
    return {"quality_status": summary["quality_status"], **summary}
