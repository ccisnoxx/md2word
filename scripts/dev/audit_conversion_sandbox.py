#!/Users/sc/miniconda3/envs/md2word/bin/python
"""Inspect local conversion sandbox drift, sample assets, and thin-shell state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
root_path = str(ROOT)
if root_path not in sys.path:
    sys.path.insert(0, root_path)


DEFAULT_SANDBOX_ROOT = Path("/Users/sc/PycharmProjects/PythonProject/md2word_main")
SANDBOX_ENV = "MD2WORD_SANDBOX_ROOT"
DEFAULT_COMPARE_PATHS = ("app/conversion", "resources")
IGNORED_DIR_NAMES = {"__pycache__", ".git", ".idea", ".pytest_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


@dataclass(frozen=True, slots=True)
class DriftReport:
    official_root: str
    sandbox_root: str
    compare_paths: list[str]
    same_files: list[str]
    changed_files: list[str]
    official_only_files: list[str]
    sandbox_only_files: list[str]

    @property
    def has_drift(self) -> bool:
        return bool(self.changed_files or self.official_only_files or self.sandbox_only_files)


@dataclass(frozen=True, slots=True)
class MinerUPackageInventory:
    path: str
    candidate_pdf: str
    has_content_list_v2: bool
    has_content_list: bool
    has_model_json: bool
    has_layout_json: bool
    has_block_list_json: bool
    has_full_markdown: bool
    image_count: int


@dataclass(frozen=True, slots=True)
class SampleInventoryReport:
    sandbox_root: str
    pdfs: list[str]
    mineru_packages: list[MinerUPackageInventory]


@dataclass(frozen=True, slots=True)
class ThinShellReport:
    sandbox_root: str
    active_duplicate_paths: list[str]
    missing_expected_paths: list[str]
    archived_duplicate_paths: list[str]

    @property
    def ok(self) -> bool:
        return not self.active_duplicate_paths and not self.missing_expected_paths


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit md2word_main as a local sandbox while md2word remains the official conversion source."
    )
    parser.add_argument(
        "--sandbox-root",
        default=os.environ.get(SANDBOX_ENV, str(DEFAULT_SANDBOX_ROOT)),
        help=f"Local sandbox root. Defaults to {SANDBOX_ENV} or {DEFAULT_SANDBOX_ROOT}.",
    )
    parser.add_argument("--official-root", default=str(ROOT), help="Official md2word repository root.")

    subparsers = parser.add_subparsers(dest="command", required=True)
    drift_parser = subparsers.add_parser("drift", help="Compare official conversion files with a sandbox copy.")
    drift_parser.add_argument(
        "--path",
        action="append",
        dest="compare_paths",
        help="Relative path to compare. May be repeated. Defaults to app/conversion and resources.",
    )
    drift_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    drift_parser.add_argument(
        "--allow-drift",
        action="store_true",
        help="Exit 0 even when drift is found. Useful for inventory-only local runs.",
    )

    samples_parser = subparsers.add_parser("samples", help="Inventory local test PDFs and MinerU result packages.")
    samples_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    thin_parser = subparsers.add_parser("thin", help="Validate that the sandbox is an inactive thin shell.")
    thin_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args(argv)


def _should_ignore(path: Path) -> bool:
    if any(part in IGNORED_DIR_NAMES for part in path.parts):
        return True
    return path.suffix in IGNORED_SUFFIXES


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(root: Path, relative_base: str) -> Iterable[tuple[str, Path]]:
    base = root / relative_base
    if not base.exists():
        return
    if base.is_file():
        if not _should_ignore(Path(relative_base)):
            yield relative_base, base
        return
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        if _should_ignore(relative_path):
            continue
        yield relative_path.as_posix(), path


def collect_hashes(root: Path, compare_paths: Sequence[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative_base in compare_paths:
        for relative_path, path in _iter_files(root, relative_base):
            hashes[relative_path] = _sha256(path)
    return hashes


def build_drift_report(official_root: Path, sandbox_root: Path, compare_paths: Sequence[str]) -> DriftReport:
    official_hashes = collect_hashes(official_root, compare_paths)
    sandbox_hashes = collect_hashes(sandbox_root, compare_paths)
    all_paths = sorted(set(official_hashes) | set(sandbox_hashes))
    same_files: list[str] = []
    changed_files: list[str] = []
    official_only_files: list[str] = []
    sandbox_only_files: list[str] = []
    for relative_path in all_paths:
        official_hash = official_hashes.get(relative_path)
        sandbox_hash = sandbox_hashes.get(relative_path)
        if official_hash is None:
            sandbox_only_files.append(relative_path)
        elif sandbox_hash is None:
            official_only_files.append(relative_path)
        elif official_hash == sandbox_hash:
            same_files.append(relative_path)
        else:
            changed_files.append(relative_path)
    return DriftReport(
        official_root=str(official_root),
        sandbox_root=str(sandbox_root),
        compare_paths=list(compare_paths),
        same_files=same_files,
        changed_files=changed_files,
        official_only_files=official_only_files,
        sandbox_only_files=sandbox_only_files,
    )


def _infer_candidate_pdf(package_path: Path) -> str:
    name = package_path.name
    if ".pdf-" in name:
        return f"{name.split('.pdf-', 1)[0]}.pdf"
    return ""


def _has_glob(root: Path, pattern: str) -> bool:
    return any(root.glob(pattern))


def build_sample_inventory(sandbox_root: Path) -> SampleInventoryReport:
    pdf_root = sandbox_root / "test_pdf"
    pdfs = sorted(path.name for path in pdf_root.glob("*.pdf")) if pdf_root.exists() else []
    mineru_root = sandbox_root / "mineru_result"
    packages: list[MinerUPackageInventory] = []
    if mineru_root.exists():
        for package_path in sorted(path for path in mineru_root.iterdir() if path.is_dir()):
            images_dir = package_path / "images"
            image_count = (
                len([path for path in images_dir.iterdir() if path.is_file()])
                if images_dir.exists()
                else 0
            )
            packages.append(
                MinerUPackageInventory(
                    path=str(package_path),
                    candidate_pdf=_infer_candidate_pdf(package_path),
                    has_content_list_v2=_has_glob(package_path, "*_content_list_v2.json"),
                    has_content_list=_has_glob(package_path, "*_content_list.json"),
                    has_model_json=_has_glob(package_path, "*_model.json"),
                    has_layout_json=(package_path / "layout.json").exists(),
                    has_block_list_json=(package_path / "block_list.json").exists(),
                    has_full_markdown=(package_path / "full.md").exists(),
                    image_count=image_count,
                )
            )
    return SampleInventoryReport(
        sandbox_root=str(sandbox_root),
        pdfs=pdfs,
        mineru_packages=packages,
    )


def build_thin_shell_report(sandbox_root: Path) -> ThinShellReport:
    active_duplicate_paths = [
        relative_path
        for relative_path in ("app", "cli_core", "resources")
        if (sandbox_root / relative_path).exists()
    ]
    missing_expected_paths = [
        relative_path
        for relative_path in ("mineru_to_docx.py", "sandbox_config.json", "README.md", "test_pdf", "mineru_result", "out")
        if not (sandbox_root / relative_path).exists()
    ]
    archive_root = sandbox_root / "_legacy_duplicate_core"
    archived_duplicate_paths = (
        sorted(path.name for path in archive_root.iterdir())
        if archive_root.exists()
        else []
    )
    return ThinShellReport(
        sandbox_root=str(sandbox_root),
        active_duplicate_paths=active_duplicate_paths,
        missing_expected_paths=missing_expected_paths,
        archived_duplicate_paths=archived_duplicate_paths,
    )


def format_drift_report(report: DriftReport) -> str:
    lines = [
        "Conversion sandbox drift report",
        f"official_root: {report.official_root}",
        f"sandbox_root: {report.sandbox_root}",
        f"compare_paths: {', '.join(report.compare_paths)}",
        f"same_files: {len(report.same_files)}",
        f"changed_files: {len(report.changed_files)}",
        f"official_only_files: {len(report.official_only_files)}",
        f"sandbox_only_files: {len(report.sandbox_only_files)}",
    ]
    for title, values in (
        ("changed", report.changed_files),
        ("official_only", report.official_only_files),
        ("sandbox_only", report.sandbox_only_files),
    ):
        if values:
            lines.append(f"{title}:")
            lines.extend(f"  - {value}" for value in values)
    return "\n".join(lines)


def format_sample_inventory(report: SampleInventoryReport) -> str:
    lines = [
        "Conversion sandbox sample inventory",
        f"sandbox_root: {report.sandbox_root}",
        f"pdfs: {len(report.pdfs)}",
        f"mineru_packages: {len(report.mineru_packages)}",
    ]
    if report.pdfs:
        lines.append("test_pdf:")
        lines.extend(f"  - {pdf}" for pdf in report.pdfs)
    if report.mineru_packages:
        lines.append("mineru_result:")
        for package in report.mineru_packages:
            lines.append(
                "  - "
                f"{Path(package.path).name} "
                f"pdf={package.candidate_pdf or 'unknown'} "
                f"v2={package.has_content_list_v2} "
                f"legacy={package.has_content_list} "
                f"images={package.image_count}"
            )
    return "\n".join(lines)


def format_thin_shell_report(report: ThinShellReport) -> str:
    lines = [
        "Conversion sandbox thin-shell report",
        f"sandbox_root: {report.sandbox_root}",
        f"ok: {report.ok}",
        f"active_duplicate_paths: {len(report.active_duplicate_paths)}",
        f"missing_expected_paths: {len(report.missing_expected_paths)}",
        f"archived_duplicate_paths: {len(report.archived_duplicate_paths)}",
    ]
    if report.active_duplicate_paths:
        lines.append("active duplicates:")
        lines.extend(f"  - {path}" for path in report.active_duplicate_paths)
    if report.missing_expected_paths:
        lines.append("missing expected paths:")
        lines.extend(f"  - {path}" for path in report.missing_expected_paths)
    if report.archived_duplicate_paths:
        lines.append("archived duplicates:")
        lines.extend(f"  - {path}" for path in report.archived_duplicate_paths)
    return "\n".join(lines)


def _json_ready(value: object) -> object:
    if isinstance(value, SampleInventoryReport):
        payload = asdict(value)
        payload["mineru_packages"] = [asdict(item) for item in value.mineru_packages]
        return payload
    if isinstance(value, DriftReport):
        payload = asdict(value)
        payload["has_drift"] = value.has_drift
        return payload
    if isinstance(value, ThinShellReport):
        payload = asdict(value)
        payload["ok"] = value.ok
        return payload
    return value


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    official_root = Path(args.official_root).expanduser().resolve()
    sandbox_root = Path(args.sandbox_root).expanduser().resolve()

    if args.command == "drift":
        compare_paths = args.compare_paths or list(DEFAULT_COMPARE_PATHS)
        report = build_drift_report(official_root, sandbox_root, compare_paths)
        if args.json:
            print(json.dumps(_json_ready(report), ensure_ascii=False, indent=2))
        else:
            print(format_drift_report(report))
        if report.has_drift and not args.allow_drift:
            raise SystemExit(1)
        return

    if args.command == "samples":
        report = build_sample_inventory(sandbox_root)
        if args.json:
            print(json.dumps(_json_ready(report), ensure_ascii=False, indent=2))
        else:
            print(format_sample_inventory(report))
        return

    if args.command == "thin":
        report = build_thin_shell_report(sandbox_root)
        if args.json:
            print(json.dumps(_json_ready(report), ensure_ascii=False, indent=2))
        else:
            print(format_thin_shell_report(report))
        if not report.ok:
            raise SystemExit(1)
        return

    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
