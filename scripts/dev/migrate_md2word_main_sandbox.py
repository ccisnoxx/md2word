#!/usr/bin/env python3
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

import sys

DEPRECATED_MESSAGE = """md2word_main/mineru_to_docx.py 已废弃，不再作为转换运行入口。

请在正式项目中运行本地 MinerU 调试：
  项目：{official_root}
  PyCharm Script path: {official_root}/scripts/dev/run_local_mineru_debug_config.py
  配置文件：{official_root}/scripts/dev/local_mineru_debug_config.json

md2word_main 只保留 test_pdf/、mineru_result/、out/ 等历史样例资产。
"""


def main(argv: list[str] | None = None) -> None:
    _ = argv
    print(DEPRECATED_MESSAGE, file=sys.stderr)
    raise SystemExit(2)


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
        "notes": "Deprecated historical config. Run scripts/dev/run_local_mineru_debug_config.py in the official md2word project instead.",
    }
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def build_readme(official_root: Path) -> str:
    return f'''# md2word_main

`md2word_main` 已不再作为转换代码运行入口。这个目录只保留历史样例资产和输出资产，例如 `test_pdf/`、`mineru_result/`、`out/`。

## 正式运行入口

所有本地 MinerU 转 DOCX 调试都在正式项目中运行：

- 正式项目：`{official_root}`
- PyCharm Script path: `{official_root}/scripts/dev/run_local_mineru_debug_config.py`
- 默认配置文件：`{official_root}/scripts/dev/local_mineru_debug_config.json`
- Python 解释器：在 PyCharm 中选择正式项目的 Python 3.11 解释器。

配置文件里的 `input_path` 可以使用绝对路径指向本目录下的 `mineru_result/`，例如：

```json
{{
  "input_path": "/Users/sc/PycharmProjects/PythonProject/md2word_main/mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4",
  "output_path": "tests/tmp/local_mineru_debug/OPA228_P1.docx",
  "document_language": "en",
  "translation_mode": "direct"
}}
```

## 废弃入口

`mineru_to_docx.py` 已标记为 deprecated。直接运行它只会打印迁移提示并以非零状态退出，不会再代理调用正式项目转换代码。

## 资产说明

- `test_pdf/`：历史测试 PDF。
- `mineru_result/`：历史 MinerU 解析结果包，可作为正式项目配置文件中的输入。
- `out/`：历史本地输出目录。
- `{ARCHIVE_DIR_NAME}/`：历史复制代码归档，不能作为新修复入口。

所有转换行为修复必须先进入 `{official_root}/app/conversion`，再用正式项目测试和样例回归验证。
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

    def test_mineru_to_docx_is_deprecated(self) -> None:
        text = (ROOT / "mineru_to_docx.py").read_text(encoding="utf-8")

        self.assertIn("已废弃", text)
        self.assertIn("run_local_mineru_debug_config.py", text)
        self.assertNotIn("run_local_mineru_conversion", text)
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
