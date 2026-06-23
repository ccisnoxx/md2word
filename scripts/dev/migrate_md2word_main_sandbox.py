#!/Users/sc/miniconda3/envs/md2word/bin/python
"""Convert the legacy md2word_main project into a thin local debug sandbox."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


DEFAULT_SANDBOX_ROOT = Path("/Users/sc/PycharmProjects/PythonProject/md2word_main")
SANDBOX_ENV = "MD2WORD_SANDBOX_ROOT"
ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR_NAME = "_legacy_duplicate_core"
ACTIVE_DUPLICATE_PATHS = ("app", "cli_core", "resources")
ARCHIVED_TEST_DIR_NAME = "tests"
THIN_TEST_PATH = "test_thin_shell.py"


@dataclass(frozen=True, slots=True)
class MigrationResult:
    sandbox_root: str
    official_root: str
    archive_root: str
    apply: bool
    moved_paths: list[str]
    written_paths: list[str]
    kept_paths: list[str]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate md2word_main into a thin local debug shell.")
    parser.add_argument(
        "--sandbox-root",
        default=os.environ.get(SANDBOX_ENV, str(DEFAULT_SANDBOX_ROOT)),
        help=f"md2word_main root. Defaults to {SANDBOX_ENV} or {DEFAULT_SANDBOX_ROOT}.",
    )
    parser.add_argument("--official-root", default=str(ROOT), help="Official md2word repository root.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Without this, only report planned changes.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args(argv)


def migrate_sandbox(*, sandbox_root: Path, official_root: Path, apply: bool) -> MigrationResult:
    sandbox_root = sandbox_root.expanduser().resolve()
    official_root = official_root.expanduser().resolve()
    _validate_roots(sandbox_root, official_root)

    archive_root = sandbox_root / ARCHIVE_DIR_NAME
    moved_paths: list[str] = []
    written_paths: list[str] = []
    kept_paths: list[str] = []

    if apply:
        archive_root.mkdir(parents=True, exist_ok=True)

    for relative_path in (*ACTIVE_DUPLICATE_PATHS, ARCHIVED_TEST_DIR_NAME):
        source = sandbox_root / relative_path
        if not source.exists():
            kept_paths.append(relative_path)
            continue
        if relative_path == ARCHIVED_TEST_DIR_NAME and _is_thin_shell_tests_dir(source):
            kept_paths.append(relative_path)
            continue
        destination = _next_archive_destination(archive_root / relative_path)
        moved_paths.append(f"{relative_path} -> {destination.relative_to(sandbox_root).as_posix()}")
        if apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))

    files = {
        "mineru_to_docx.py": build_thin_entrypoint(official_root),
        "config.py": build_compat_config(official_root),
        "sandbox_config.json": build_sandbox_config(sandbox_root, official_root),
        "README.md": build_readme(official_root),
        "tests/test_thin_shell.py": build_thin_shell_test(),
    }
    for relative_path, content in files.items():
        written_paths.append(relative_path)
        if apply:
            target = sandbox_root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    return MigrationResult(
        sandbox_root=str(sandbox_root),
        official_root=str(official_root),
        archive_root=str(archive_root),
        apply=apply,
        moved_paths=moved_paths,
        written_paths=written_paths,
        kept_paths=kept_paths,
    )


def _validate_roots(sandbox_root: Path, official_root: Path) -> None:
    if not sandbox_root.exists():
        raise FileNotFoundError(f"Sandbox root does not exist: {sandbox_root}")
    if not (official_root / "app" / "conversion").is_dir():
        raise FileNotFoundError(f"Official app/conversion does not exist: {official_root}")


def _next_archive_destination(path: Path) -> Path:
    if not path.exists():
        return path
    parent = path.parent
    stem = path.name
    index = 2
    while True:
        candidate = parent / f"{stem}.{index}"
        if not candidate.exists():
            return candidate
        index += 1


def _is_thin_shell_tests_dir(path: Path) -> bool:
    py_files = sorted(
        item.relative_to(path).as_posix()
        for item in path.rglob("*.py")
        if "__pycache__" not in item.parts
    )
    return py_files == [THIN_TEST_PATH]


def build_thin_entrypoint(official_root: Path) -> str:
    return f'''#!/usr/bin/env python3
from __future__ import annotations

# mineru_to_docx.py: Thin compatibility entrypoint that delegates to the official md2word runtime.

import json
import os
import sys
from pathlib import Path


SANDBOX_ROOT = Path(__file__).resolve().parent
DEFAULT_OFFICIAL_REPO = Path({str(official_root)!r})
CONFIG_PATH = SANDBOX_ROOT / "sandbox_config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {{}}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def resolve_official_repo(config: dict) -> Path:
    raw_value = os.environ.get("MD2WORD_OFFICIAL_REPO") or config.get("official_repo") or str(DEFAULT_OFFICIAL_REPO)
    official_repo = Path(raw_value).expanduser().resolve()
    if not (official_repo / "app" / "conversion").is_dir():
        raise SystemExit(f"Official md2word app/conversion not found: {{official_repo}}")
    return official_repo


def resolve_sandbox_path(value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = SANDBOX_ROOT / path
    return str(path.resolve())


def build_config_argv(config: dict) -> list[str]:
    argv: list[str] = []
    input_path = resolve_sandbox_path(config.get("input_path"))
    if input_path:
        argv.append(input_path)
    option_map = {{
        "output_path": "--output",
        "template_path": "--template",
        "layout_config_path": "--layout-config",
        "subscript_config": "--subscript-config",
        "document_language": "--document-language",
        "translation_mode": "--translation-mode",
        "translation_request_output": "--translation-request-output",
        "translation_response": "--translation-response",
        "translation_trace_output": "--translation-trace-output",
        "translation_model": "--translation-model",
        "translation_api_key": "--translation-api-key",
        "translation_base_url": "--translation-base-url",
        "translation_max_pages": "--translation-max-pages",
        "translation_max_chars": "--translation-max-chars",
        "log_level": "--log-level",
    }}
    path_keys = {{"output_path", "template_path", "layout_config_path", "subscript_config", "translation_request_output", "translation_response", "translation_trace_output"}}
    for key, option in option_map.items():
        value = config.get(key)
        if value in (None, ""):
            continue
        if key in path_keys:
            value = resolve_sandbox_path(str(value))
        argv.extend([option, str(value)])
    if config.get("no_template"):
        argv.append("--no-template")
    if config.get("use_mineru_header_footer"):
        argv.append("--use-mineru-header-footer")
    return argv


def main(argv: list[str] | None = None) -> None:
    config = load_config()
    official_repo = resolve_official_repo(config)
    sandbox_text = str(SANDBOX_ROOT)
    sys.path = [str(official_repo)] + [
        value for value in sys.path
        if value and str(Path(value).resolve()) != sandbox_text
    ]
    from scripts.dev.run_local_mineru_conversion import main as official_main

    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if not effective_argv:
        effective_argv = build_config_argv(config)
    official_main(effective_argv)


if __name__ == "__main__":
    main()
'''


def build_compat_config(official_root: Path) -> str:
    return f'''from __future__ import annotations

# config.py: Thin compatibility config that reads md2word's official conversion runtime config.

import os
import sys
from pathlib import Path


DEFAULT_OFFICIAL_REPO = Path({str(official_root)!r})
official_repo = Path(os.environ.get("MD2WORD_OFFICIAL_REPO", str(DEFAULT_OFFICIAL_REPO))).expanduser().resolve()
if str(official_repo) not in sys.path:
    sys.path.insert(0, str(official_repo))

from app.conversion.runtime_config import APP_CONFIG, ROOT_DIR

__all__ = ["APP_CONFIG", "ROOT_DIR"]
'''


def build_sandbox_config(sandbox_root: Path, official_root: Path) -> str:
    config = {
        "official_repo": str(official_root),
        "input_path": "mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4",
        "output_path": "out/OPA228_P1_standalone.docx",
        "document_language": "en",
        "translation_mode": "direct",
        "log_level": "INFO",
        "notes": "Relative paths are resolved from the md2word_main sandbox root.",
    }
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def build_readme(official_root: Path) -> str:
    return f'''# md2word_main

Thin local debug shell for running MinerU result directories through the official md2word conversion runtime.

## Source Of Truth

- Official conversion code: `{official_root}/app/conversion`
- This directory keeps only the debug entrypoint, sample inputs/outputs, run configuration, and this documentation.
- Previous copied conversion code is archived under `{ARCHIVE_DIR_NAME}/` and must not be imported or edited for new fixes.

## Run A Local Sample

```bash
python3 mineru_to_docx.py \\
  mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4 \\
  --output out/OPA228_P1_standalone.docx \\
  --document-language en \\
  --translation-mode direct
```

If no CLI arguments are provided, `mineru_to_docx.py` reads `sandbox_config.json`.

Use `MD2WORD_OFFICIAL_REPO=/path/to/md2word` only when the official repository moves.

## Validate The Thin Shell

```bash
python3 -m unittest tests.test_thin_shell
python3 mineru_to_docx.py
python3 mineru_to_docx.py \\
  mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4 \\
  --output out/smoke.docx \\
  --document-language en \\
  --translation-mode direct
```

Run the official repository checks from `{official_root}` before promoting any conversion behavior change.
'''


def build_thin_shell_test() -> str:
    return '''from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class ThinShellTests(TestCase):
    def test_no_active_duplicate_conversion_sources(self) -> None:
        self.assertFalse((ROOT / "app").exists())
        self.assertFalse((ROOT / "cli_core").exists())
        self.assertFalse((ROOT / "resources").exists())

    def test_sandbox_config_points_to_official_conversion_source(self) -> None:
        config = json.loads((ROOT / "sandbox_config.json").read_text(encoding="utf-8"))
        official_repo = Path(config["official_repo"])

        self.assertTrue((official_repo / "app" / "conversion").is_dir())
        self.assertTrue((ROOT / config["input_path"]).exists())
        self.assertTrue((ROOT / "mineru_to_docx.py").exists())
'''


def format_result(result: MigrationResult) -> str:
    lines = [
        "md2word_main migration report",
        f"sandbox_root: {result.sandbox_root}",
        f"official_root: {result.official_root}",
        f"archive_root: {result.archive_root}",
        f"apply: {result.apply}",
        f"moved_paths: {len(result.moved_paths)}",
        f"written_paths: {len(result.written_paths)}",
        f"kept_paths: {len(result.kept_paths)}",
    ]
    if result.moved_paths:
        lines.append("moved:")
        lines.extend(f"  - {path}" for path in result.moved_paths)
    if result.written_paths:
        lines.append("written:")
        lines.extend(f"  - {path}" for path in result.written_paths)
    if result.kept_paths:
        lines.append("kept:")
        lines.extend(f"  - {path}" for path in result.kept_paths)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    result = migrate_sandbox(
        sandbox_root=Path(args.sandbox_root),
        official_root=Path(args.official_root),
        apply=bool(args.apply),
    )
    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(format_result(result))


if __name__ == "__main__":
    main()
