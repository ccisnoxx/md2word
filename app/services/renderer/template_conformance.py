"""认证生成 DOCX 中实际可达的模板页眉、页脚和媒体。"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import Field, ValidationError

from app.services.ooxml_package import (
    DecorationFingerprint,
    DocxPackageError,
    DocxPackageInspection,
    inspect_docx_package,
)
from app.services.renderer.render_plan import RenderContract, ResourceIdentity, Sha256

TemplateConformanceMode = Literal["preserve_template", "override", "no_template"]
DecorationKind = Literal["header", "footer"]
ReferenceType = Literal["default", "first", "even"]
REPORT_VERSION = "template-conformance/v1"
REPORT_INVALID = "template_conformance:report_invalid"
BINDING_MISMATCH = "template_conformance:binding_mismatch"
RELATIONSHIP_BROKEN = "template_conformance:relationship_broken"
HASH_FAILURES = {
    "template_docx_hash_match": "template_conformance:template_docx_hash_mismatch",
    "layout_config_hash_match": "template_conformance:layout_config_hash_mismatch",
}
BOOLEAN_FAILURES = {
    **HASH_FAILURES,
    "template_package_valid": "template_conformance:template_package_invalid",
    "section_settings_preserved": "template_conformance:section_settings_changed",
    "section_header_references_valid": "template_conformance:section_header_reference_invalid",
    "section_footer_references_valid": "template_conformance:section_footer_reference_invalid",
}
PRESERVATION_FAILURES = {
    f"{kind}_{field}_preserved": (
        f"template_conformance:{kind}_{target}_missing", f"template_conformance:{kind}_{target}_changed",
    )
    for kind in ("header", "footer") for field, target in (("parts", "part"), ("media", "media"))
}
TEMPLATE_CONFORMANCE_FLAGS = frozenset({
    REPORT_INVALID, BINDING_MISMATCH, RELATIONSHIP_BROKEN, "template_conformance:output_package_invalid",
    *BOOLEAN_FAILURES.values(), *(flag for failures in PRESERVATION_FAILURES.values() for flag in failures),
})


class TemplateConformanceError(ValueError):
    """模板符合性证据不满足固定合同。"""


class TemplateDecorationContract(RenderContract):
    """冻结清除正文后继续生效的最后一节装饰。"""

    schema_version: Literal["template-decoration-contract/v1"]
    header: dict[ReferenceType, DecorationFingerprint]
    footer: dict[ReferenceType, DecorationFingerprint]
    title_page: bool
    even_and_odd_headers: bool


class TemplateConformanceReport(RenderContract):
    """仅供私有证据保存的模板与最终 DOCX 绑定。"""

    schema_version: Literal["template-conformance/v1"]
    mode: TemplateConformanceMode
    result_docx_sha256: Sha256
    template_docx_sha256: Sha256 | None
    layout_config_sha256: Sha256 | None
    template_docx_hash_match: bool | None
    layout_config_hash_match: bool | None
    header_override: bool
    footer_override: bool
    template_package_valid: bool | None
    expected_decoration: TemplateDecorationContract | None
    header_parts_preserved: bool | None
    footer_parts_preserved: bool | None
    header_media_preserved: bool | None
    footer_media_preserved: bool | None
    section_header_references_valid: bool
    section_footer_references_valid: bool
    section_settings_preserved: bool | None
    broken_relationship_count: int = Field(ge=0)
    missing_header_media_sha256: list[Sha256]
    missing_footer_media_sha256: list[Sha256]
    blocking_flags: list[str]


@dataclass(frozen=True, slots=True)
class _DecorationAssessment:
    parts_preserved: bool | None
    media_preserved: bool | None
    references_valid: bool
    missing_media: list[str]
    flags: tuple[str, ...]


def build_template_conformance_report(
    word_content: bytes, *, template_content: bytes | None, layout_config_content: bytes | None = None,
    header_override: bool = False, footer_override: bool = False, resource_hashes_verified: bool = False,
) -> TemplateConformanceReport:
    """使用 Renderer 消费的原始字节和实际保存的 DOCX 生成证据。"""

    expected = None
    template_package_valid = None
    if template_content is not None:
        try:
            source = inspect_docx_package(template_content)
        except DocxPackageError:
            template_package_valid = False
        else:
            template_package_valid = not source.issues
            if template_package_valid:
                section = source.sections[-1]
                expected = TemplateDecorationContract(
                    schema_version="template-decoration-contract/v1",
                    header=section.header, footer=section.footer, title_page=section.title_page,
                    even_and_odd_headers=source.even_and_odd_headers,
                )
    mode: TemplateConformanceMode = "no_template" if template_content is None else (
        "override" if header_override or footer_override else "preserve_template"
    )
    return TemplateConformanceReport(
        schema_version=REPORT_VERSION,
        mode=mode,
        result_docx_sha256=hashlib.sha256(word_content).hexdigest(),
        template_docx_sha256=hashlib.sha256(template_content).hexdigest() if template_content is not None else None,
        layout_config_sha256=hashlib.sha256(layout_config_content).hexdigest() if layout_config_content is not None else None,
        template_docx_hash_match=True if resource_hashes_verified and template_content is not None else None,
        layout_config_hash_match=True if resource_hashes_verified and layout_config_content is not None else None,
        header_override=header_override,
        footer_override=footer_override,
        template_package_valid=template_package_valid,
        expected_decoration=expected,
        **_evaluate_output(word_content, expected, template_package_valid, header_override, footer_override),
    )


def read_template_conformance_report(value: Any) -> TemplateConformanceReport:
    """只接受完整的私有报告，不把缺失字段推断为通过。"""

    try:
        report = TemplateConformanceReport.model_validate(value)
    except ValidationError:
        raise TemplateConformanceError(REPORT_INVALID) from None
    has_template = report.template_docx_sha256 is not None
    mode = "no_template" if not has_template else "override" if report.header_override or report.footer_override else "preserve_template"
    if (
        report.mode != mode or has_template != (report.template_package_valid is not None)
        or (report.expected_decoration is not None) != (report.template_package_valid is True)
        or (report.template_docx_hash_match is not None and not has_template)
        or (report.layout_config_hash_match is not None and report.layout_config_sha256 is None)
        or any(flag not in TEMPLATE_CONFORMANCE_FLAGS for flag in report.blocking_flags)
    ):
        raise TemplateConformanceError(REPORT_INVALID)
    return report


def verify_template_conformance_report(
    value: Any, word_content: bytes, *, template_docx_sha256: str | None, layout_config_sha256: str | None,
    resource_identity: ResourceIdentity | None,
) -> TemplateConformanceReport:
    """从最终 DOCX 重算符合性，并与已认证的原始模板和 YAML 字节身份核对。"""

    report = read_template_conformance_report(value)
    for field, flag in HASH_FAILURES.items():
        if getattr(report, field) is False:
            raise TemplateConformanceError(flag)
    if (
        report.result_docx_sha256 != hashlib.sha256(word_content).hexdigest()
        or report.template_docx_sha256 != template_docx_sha256
        or report.layout_config_sha256 != layout_config_sha256
        or (resource_identity is not None and report.template_docx_sha256 != resource_identity.template_sha256)
    ):
        raise TemplateConformanceError(BINDING_MISMATCH)
    actual = _evaluate_output(
        word_content, report.expected_decoration, report.template_package_valid, report.header_override, report.footer_override,
    )
    if any(getattr(report, field) != result for field, result in actual.items()):
        raise TemplateConformanceError(BINDING_MISMATCH)
    return report


def _blocking_flags(value: dict[str, Any], flags: list[str]) -> list[str]:
    flags = [*flags, *(flag for field, flag in BOOLEAN_FAILURES.items() if value.get(field) is False)]
    if value["broken_relationship_count"]:
        flags.append(RELATIONSHIP_BROKEN)
    if any(value.get(field) is False and not any(flag in flags for flag in allowed)
           for field, allowed in PRESERVATION_FAILURES.items()):
        flags.append(REPORT_INVALID)
    return list(dict.fromkeys(flags))


def template_conformance_blocking_flags(report: TemplateConformanceReport) -> list[str]:
    """质量门独立消费嵌套阻断，顶层列表缺漏仍然拒绝。"""

    return _blocking_flags(report.model_dump(), report.blocking_flags)


def build_template_conformance_summary(value: object) -> dict[str, Any] | None:
    """只投影固定状态、计数与代码，可再次用于事件脱敏。"""

    if not isinstance(value, dict) or value.get("schema_version") != REPORT_VERSION:
        return None
    mode = value.get("mode")
    count = value.get("broken_relationship_count")
    flags = value.get("blocking_flags")
    if mode not in ("preserve_template", "override", "no_template") or type(count) is not int or count < 0 or not isinstance(flags, list):
        return None
    booleans = {}
    for field in (*BOOLEAN_FAILURES, *PRESERVATION_FAILURES, "header_override", "footer_override"):
        if field in value:
            item = value[field]
            if item is not None and type(item) is not bool:
                return None
            booleans[field] = item
    safe_flags = [flag for flag in flags if isinstance(flag, str) and flag in TEMPLATE_CONFORMANCE_FLAGS]
    if len(safe_flags) != len(flags):
        safe_flags.append(REPORT_INVALID)
    safe_flags = _blocking_flags(value, safe_flags)
    return {
        "schema_version": REPORT_VERSION, "mode": mode, "status": "blocked" if safe_flags else "passed",
        "broken_relationship_count": count, "blocking_flags": safe_flags, **booleans,
    }


def _evaluate_output(
    word_content: bytes, expected: TemplateDecorationContract | None, template_package_valid: bool | None,
    header_override: bool, footer_override: bool,
) -> dict:
    flags = []
    if template_package_valid is False:
        flags.append("template_conformance:template_package_invalid")
    try:
        output = inspect_docx_package(word_content)
    except DocxPackageError:
        flags.append("template_conformance:output_package_invalid")
        output = None
    broken_relationship_count = sum(
        issue.code in {"docx_relationship_broken", "docx_media_invalid"} for issue in output.issues
    ) if output is not None else 0
    if broken_relationship_count:
        flags.append("template_conformance:relationship_broken")
    section_settings_preserved = None
    if expected is not None:
        section_settings_preserved = output is not None and (
            output.even_and_odd_headers == expected.even_and_odd_headers
            and all(section.title_page == expected.title_page for section in output.sections)
        )
        if not section_settings_preserved:
            flags.append("template_conformance:section_settings_changed")
    header = _assess_decoration(output, expected.header if expected is not None else None, "header", header_override)
    footer = _assess_decoration(output, expected.footer if expected is not None else None, "footer", footer_override)
    return {
        "header_parts_preserved": header.parts_preserved,
        "footer_parts_preserved": footer.parts_preserved,
        "header_media_preserved": header.media_preserved,
        "footer_media_preserved": footer.media_preserved,
        "section_header_references_valid": header.references_valid,
        "section_footer_references_valid": footer.references_valid,
        "section_settings_preserved": section_settings_preserved,
        "broken_relationship_count": broken_relationship_count,
        "missing_header_media_sha256": header.missing_media,
        "missing_footer_media_sha256": footer.missing_media,
        "blocking_flags": [*flags, *header.flags, *footer.flags],
    }


def _assess_decoration(
    output: DocxPackageInspection | None, expected: dict[str, DecorationFingerprint] | None,
    kind: DecorationKind, override: bool,
) -> _DecorationAssessment:
    sections = (
        [section.header if kind == "header" else section.footer for section in output.sections]
        if output is not None else []
    )
    references_valid = output is not None and all(
        issue.code != "docx_section_reference_invalid" or issue.path != f"docx.{kind}.references"
        for issue in output.issues
    )
    parts_preserved = media_preserved = None
    missing_media: set[str] = set()
    flags: list[str] = []
    if override:
        references_valid = references_valid and all("default" in section for section in sections)
    elif expected is not None:
        references_valid = references_valid and all(section.keys() == expected.keys() for section in sections)
        parts_preserved = bool(sections)
        media_preserved = bool(sections)
        part_missing = False
        for section in sections or [{}]:
            for role, wanted in expected.items():
                found = section.get(role)
                if found is None:
                    parts_preserved = False
                    part_missing = True
                elif wanted.markup_sha256 != found.markup_sha256:
                    parts_preserved = False
                actual_media = found.media_sha256 if found is not None else []
                if wanted.media_sha256 != actual_media:
                    media_preserved = False
                    missing_media.update(Counter(wanted.media_sha256) - Counter(actual_media))
        if not parts_preserved:
            flags.append(f"template_conformance:{kind}_part_{'missing' if part_missing else 'changed'}")
        if not media_preserved:
            flags.append(f"template_conformance:{kind}_media_{'missing' if missing_media else 'changed'}")
    if not references_valid:
        flags.append(f"template_conformance:section_{kind}_reference_invalid")
    return _DecorationAssessment(parts_preserved, media_preserved, references_valid, sorted(missing_media), tuple(flags))
