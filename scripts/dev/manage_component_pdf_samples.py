#!/Users/sc/miniconda3/envs/md2word/bin/python
"""Manage electronic component PDF regression sample metadata and fixtures."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = ROOT / "tests" / "fixtures" / "component_pdf_samples" / "manifest.yaml"
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
IGNORED_COPY_NAMES = {"__pycache__", ".DS_Store"}


@dataclass(frozen=True, slots=True)
class ComponentSampleIssue:
    sample_id: str
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class ComponentSampleInventory:
    manifest_path: str
    sample_root: str
    sample_count: int
    enabled_count: int
    runnable_count: int
    brands: list[str]
    categories: list[str]
    missing_package_samples: list[str]
    issues: list[ComponentSampleIssue]

    @property
    def ok(self) -> bool:
        return not self.issues and not self.missing_package_samples


@dataclass(frozen=True, slots=True)
class AddSampleResult:
    manifest_path: str
    sample_id: str
    sample_dir: str
    package_path: str
    apply: bool
    copied_files: list[str]
    manifest_updated: bool


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage component PDF regression samples.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="Component sample manifest path.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate manifest metadata and local package paths.")
    validate_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    add_parser = subparsers.add_parser("add-mineru-sample", help="Copy a local MinerU package and append manifest metadata.")
    add_parser.add_argument("--sample-id", required=True)
    add_parser.add_argument("--brand", required=True)
    add_parser.add_argument("--category", required=True)
    add_parser.add_argument("--product", required=True)
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--source-pdf", required=True, help="PDF filename, external artifact id, or local reference.")
    add_parser.add_argument("--mineru-package", required=True, help="Local MinerU result directory to copy.")
    add_parser.add_argument("--tag", action="append", default=[], help="Tag to attach. May be repeated.")
    add_parser.add_argument(
        "--acceptance-focus",
        action="append",
        default=[],
        help="Manual review focus item. May be repeated.",
    )
    add_parser.add_argument("--document-language", default="en", choices=("auto", "zh", "en"))
    add_parser.add_argument("--translation-mode", default="direct", choices=("direct", "none", "en2zh", "llm_en_to_zh"))
    add_parser.add_argument("--apply", action="store_true", help="Write files and update the manifest.")
    add_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args(argv)


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Component sample manifest not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if data.get("schema_version") != 1:
        raise ValueError("Component sample manifest schema_version must be 1.")
    if not isinstance(data.get("samples"), list):
        raise ValueError("Component sample manifest must contain a samples list.")
    return data


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")


def resolve_sample_root(manifest_path: Path, manifest: dict[str, Any]) -> Path:
    raw_root = str(manifest.get("sample_root") or "tests/fixtures/component_pdf_samples/samples")
    candidate = Path(raw_root)
    if candidate.is_absolute():
        return candidate
    return (ROOT / candidate).resolve() if manifest_path.resolve() == DEFAULT_MANIFEST_PATH.resolve() else (manifest_path.parent / candidate).resolve()


def normalize_slug(value: str, field_name: str) -> str:
    normalized = value.strip().lower().replace(" ", "-")
    if not normalized or not ID_RE.match(normalized):
        raise ValueError(f"{field_name} must be lowercase kebab/snake case: {value!r}")
    return normalized


def sample_package_path(sample_root: Path, sample: dict[str, Any]) -> Path:
    mineru = sample.get("mineru") if isinstance(sample.get("mineru"), dict) else {}
    package_path = str(mineru.get("package_path") or "")
    if not package_path:
        return sample_root / "__missing__"
    candidate = Path(package_path)
    return candidate if candidate.is_absolute() else sample_root / candidate


def validate_manifest(path: Path) -> ComponentSampleInventory:
    manifest = load_manifest(path)
    sample_root = resolve_sample_root(path, manifest)
    samples = manifest.get("samples", [])
    issues: list[ComponentSampleIssue] = []
    missing_package_samples: list[str] = []
    seen_ids: set[str] = set()
    brands: set[str] = set()
    categories: set[str] = set()
    runnable_count = 0

    for sample in samples:
        sample_id = str(sample.get("id") or "")
        if not sample_id:
            sample_id = "<missing-id>"
            issues.append(ComponentSampleIssue(sample_id, "missing_id", "sample id is required"))
        elif sample_id in seen_ids:
            issues.append(ComponentSampleIssue(sample_id, "duplicate_id", "sample id must be unique"))
        else:
            seen_ids.add(sample_id)
        for field in ("brand", "category", "product", "title"):
            if not str(sample.get(field) or "").strip():
                issues.append(ComponentSampleIssue(sample_id, f"missing_{field}", f"{field} is required"))
        brand = str(sample.get("brand") or "").strip()
        category = str(sample.get("category") or "").strip()
        if brand:
            brands.add(brand)
        if category:
            categories.add(category)
        if not isinstance(sample.get("source_pdf"), dict):
            issues.append(ComponentSampleIssue(sample_id, "missing_source_pdf", "source_pdf mapping is required"))
        if not isinstance(sample.get("tags"), list) or not sample.get("tags"):
            issues.append(ComponentSampleIssue(sample_id, "missing_tags", "tags must be non-empty"))
        if not isinstance(sample.get("acceptance_focus"), list) or not sample.get("acceptance_focus"):
            issues.append(ComponentSampleIssue(sample_id, "missing_acceptance_focus", "acceptance_focus must be non-empty"))
        regression = sample.get("regression") if isinstance(sample.get("regression"), dict) else {}
        if "enabled" not in regression or not isinstance(regression.get("enabled"), bool):
            issues.append(ComponentSampleIssue(sample_id, "missing_regression_enabled", "regression.enabled must be true or false"))
        package_path = sample_package_path(sample_root, sample)
        enabled = _is_enabled(sample)
        if enabled and not _has_mineru_content_list(package_path):
            missing_package_samples.append(sample_id)
        elif enabled:
            runnable_count += 1

    return ComponentSampleInventory(
        manifest_path=str(path),
        sample_root=str(sample_root),
        sample_count=len(samples),
        enabled_count=len([sample for sample in samples if _is_enabled(sample)]),
        runnable_count=runnable_count,
        brands=sorted(brands),
        categories=sorted(categories),
        missing_package_samples=sorted(missing_package_samples),
        issues=issues,
    )


def add_mineru_sample(
    *,
    manifest_path: Path,
    sample_id: str,
    brand: str,
    category: str,
    product: str,
    title: str,
    source_pdf: str,
    mineru_package: Path,
    tags: Sequence[str],
    acceptance_focus: Sequence[str],
    document_language: str,
    translation_mode: str,
    apply: bool,
) -> AddSampleResult:
    manifest = load_manifest(manifest_path)
    sample_root = resolve_sample_root(manifest_path, manifest)
    sample_id = normalize_slug(sample_id, "sample_id")
    brand = normalize_slug(brand, "brand")
    category = normalize_slug(category, "category")
    if any(str(sample.get("id")) == sample_id for sample in manifest.get("samples", [])):
        raise ValueError(f"sample already exists in manifest: {sample_id}")
    source_package = mineru_package.expanduser().resolve()
    if not _has_mineru_content_list(source_package):
        raise FileNotFoundError(f"MinerU package missing *_content_list_v2.json or *_content_list.json: {source_package}")
    sample_dir = sample_root / brand / category / sample_id
    package_dir = sample_dir / "mineru"
    if package_dir.exists():
        raise FileExistsError(f"sample package already exists: {package_dir}")

    copied_files = sorted(
        path.relative_to(source_package).as_posix()
        for path in source_package.rglob("*")
        if path.is_file() and not _should_ignore_copy(path)
    )
    sample_entry = {
        "id": sample_id,
        "brand": brand,
        "category": category,
        "product": product,
        "title": title,
        "source_status": "local_mineru_import",
        "source_pdf": {
            "reference": source_pdf,
            "public": False,
            "committed": False,
        },
        "mineru": {
            "package_path": f"{brand}/{category}/{sample_id}/mineru",
            "source": "local_import",
        },
        "document_language": document_language,
        "translation_mode": translation_mode,
        "tags": sorted(set(tags)),
        "acceptance_focus": list(acceptance_focus)
        or ["Record the layout defect or regression that justified this sample."],
        "regression": {
            "enabled": True,
            "expected_min_pages": 1,
            "run_mode": "local_mineru_to_docx",
        },
    }

    if apply:
        package_dir.parent.mkdir(parents=True, exist_ok=True)
        _copy_package(source_package, package_dir)
        manifest.setdefault("samples", []).append(sample_entry)
        write_manifest(manifest_path, manifest)

    return AddSampleResult(
        manifest_path=str(manifest_path),
        sample_id=sample_id,
        sample_dir=str(sample_dir),
        package_path=str(package_dir),
        apply=apply,
        copied_files=copied_files,
        manifest_updated=apply,
    )


def format_inventory(report: ComponentSampleInventory) -> str:
    lines = [
        "Component PDF sample inventory",
        f"manifest_path: {report.manifest_path}",
        f"sample_root: {report.sample_root}",
        f"sample_count: {report.sample_count}",
        f"enabled_count: {report.enabled_count}",
        f"runnable_count: {report.runnable_count}",
        f"brands: {', '.join(report.brands) if report.brands else '-'}",
        f"categories: {', '.join(report.categories) if report.categories else '-'}",
        f"ok: {report.ok}",
    ]
    if report.missing_package_samples:
        lines.append("missing packages:")
        lines.extend(f"  - {sample_id}" for sample_id in report.missing_package_samples)
    if report.issues:
        lines.append("issues:")
        lines.extend(f"  - {issue.sample_id}: {issue.code}: {issue.detail}" for issue in report.issues)
    return "\n".join(lines)


def format_add_result(result: AddSampleResult) -> str:
    lines = [
        "Component PDF sample add report",
        f"manifest_path: {result.manifest_path}",
        f"sample_id: {result.sample_id}",
        f"sample_dir: {result.sample_dir}",
        f"package_path: {result.package_path}",
        f"apply: {result.apply}",
        f"copied_files: {len(result.copied_files)}",
        f"manifest_updated: {result.manifest_updated}",
    ]
    if result.copied_files:
        lines.append("files:")
        lines.extend(f"  - {path}" for path in result.copied_files[:20])
        if len(result.copied_files) > 20:
            lines.append(f"  - ... {len(result.copied_files) - 20} more")
    return "\n".join(lines)


def _is_enabled(sample: dict[str, Any]) -> bool:
    regression = sample.get("regression") if isinstance(sample.get("regression"), dict) else {}
    return regression.get("enabled", True) is not False


def _has_mineru_content_list(path: Path) -> bool:
    return path.is_dir() and (
        any(path.glob("*_content_list_v2.json"))
        or any(path.glob("*_content_list.json"))
        or (path / "content_list_v2.json").exists()
        or (path / "content_list.json").exists()
    )


def _should_ignore_copy(path: Path) -> bool:
    return any(part in IGNORED_COPY_NAMES for part in path.parts)


def _copy_package(source: Path, destination: Path) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in IGNORED_COPY_NAMES}

    shutil.copytree(source, destination, ignore=ignore)


def _json_ready(value: object) -> object:
    if isinstance(value, ComponentSampleInventory):
        payload = asdict(value)
        payload["issues"] = [asdict(issue) for issue in value.issues]
        payload["ok"] = value.ok
        return payload
    if isinstance(value, AddSampleResult):
        return asdict(value)
    return value


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    manifest_path = Path(args.manifest).expanduser().resolve()
    if args.command == "validate":
        report = validate_manifest(manifest_path)
        if args.json:
            print(json.dumps(_json_ready(report), ensure_ascii=False, indent=2))
        else:
            print(format_inventory(report))
        if not report.ok:
            raise SystemExit(1)
        return
    if args.command == "add-mineru-sample":
        result = add_mineru_sample(
            manifest_path=manifest_path,
            sample_id=args.sample_id,
            brand=args.brand,
            category=args.category,
            product=args.product,
            title=args.title,
            source_pdf=args.source_pdf,
            mineru_package=Path(args.mineru_package),
            tags=args.tag,
            acceptance_focus=args.acceptance_focus,
            document_language=args.document_language,
            translation_mode=args.translation_mode,
            apply=bool(args.apply),
        )
        if args.json:
            print(json.dumps(_json_ready(result), ensure_ascii=False, indent=2))
        else:
            print(format_add_result(result))
        return
    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
