from __future__ import annotations

# scripts/ops/export_openapi.py: 导出 FastAPI OpenAPI 快照并提供发布前一致性检查。

import argparse
import difflib
import importlib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = REPO_ROOT / "docs" / "api" / "openapi.json"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass(frozen=True, slots=True)
class OpenAPIExportReport:
    output_path: str
    check_only: bool
    ok: bool
    changed: bool
    path_count: int
    schema_count: int
    diff: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": self.output_path,
            "check_only": self.check_only,
            "ok": self.ok,
            "changed": self.changed,
            "path_count": self.path_count,
            "schema_count": self.schema_count,
            "diff": self.diff,
        }


@contextmanager
def _openapi_export_environment(data_dir: Path) -> Iterator[None]:
    """隔离运行态路径，避免导出 schema 时写入真实 jobs 数据目录。"""

    overrides = {
        "APP_NAME": "md2word_file",
        "APP_ENV": "test",
        "PUBLIC_DEPLOYMENT_MODE": "internal",
        "DATA_DIR": str(data_dir),
        "JOBS_REPOSITORY_BACKEND": "file",
        "JOBS_ARTIFACT_STORAGE_BACKEND": "local_file",
        "JOBS_ARTIFACT_OBJECT_STORE_PATH": "var/object_artifacts",
        "JOBS_WORKER_MODE": "external",
        "JOBS_ACCESS_MODE": "open",
        "JOBS_OPS_ACCESS_MODE": "admin",
        "ADMIN_TOKEN": "",
        "AUTH_INTERNAL_USERS_FILE": "",
        "AUTH_INTERNAL_USERS_JSON": "",
        "MINERU_API_TOKEN": "",
        "OPENAI_API_KEY": "",
        "TEMPLATES_MANIFEST_PATH": "resources/template_configs/templates_manifest.yaml",
        "TEMPLATES_STORAGE_PATH": "var/config/templates",
        "TEMPLATE_STATE_PATH": "var/config/template_state.json",
        "TERM_RULES_SEED_PATH": "resources/term_rules/term_rules.v2.yaml",
        "TERM_RULES_STORE_PATH": "var/config/term_rules_store.json",
        "TERM_RULES_RUNTIME_YAML_PATH": "var/config/runtime_subscripts_dictionary.yaml",
        "TRANSLATION_TERMS_PATH": "resources/term_rules/translation_terms.csv",
    }
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def generate_openapi_schema() -> dict[str, Any]:
    """生成当前 FastAPI app 的 OpenAPI schema，不启动 API 服务。"""

    with tempfile.TemporaryDirectory() as temp_dir:
        with _openapi_export_environment(Path(temp_dir)):
            app_module = importlib.import_module("app.main")
            app = app_module.create_app()
            return app.openapi()


def export_openapi(output_path: Path = DEFAULT_OUTPUT_PATH) -> OpenAPIExportReport:
    """写入当前 OpenAPI 快照，供发布检查后续比对。"""

    schema = generate_openapi_schema()
    output_text = _dump_openapi(schema)
    resolved_output_path = output_path.resolve()
    previous_text = resolved_output_path.read_text(encoding="utf-8") if resolved_output_path.exists() else ""
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(output_text, encoding="utf-8")
    return _build_report(
        output_path=resolved_output_path,
        schema=schema,
        check_only=False,
        changed=previous_text != output_text,
        diff="",
    )


def check_openapi_export(output_path: Path = DEFAULT_OUTPUT_PATH, *, include_diff: bool = True) -> OpenAPIExportReport:
    """只读比对 OpenAPI 快照；发布检查应调用此函数或 CLI 的 `--check`。"""

    schema = generate_openapi_schema()
    output_text = _dump_openapi(schema)
    resolved_output_path = output_path.resolve()
    previous_text = resolved_output_path.read_text(encoding="utf-8") if resolved_output_path.exists() else ""
    changed = previous_text != output_text
    return _build_report(
        output_path=resolved_output_path,
        schema=schema,
        check_only=True,
        changed=changed,
        diff=_build_diff(previous_text, output_text, resolved_output_path) if changed and include_diff else "",
    )


def _dump_openapi(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _build_report(
    *,
    output_path: Path,
    schema: dict[str, Any],
    check_only: bool,
    changed: bool,
    diff: str,
) -> OpenAPIExportReport:
    return OpenAPIExportReport(
        output_path=str(output_path),
        check_only=check_only,
        ok=not changed if check_only else True,
        changed=changed,
        path_count=len(schema.get("paths", {})),
        schema_count=len(schema.get("components", {}).get("schemas", {})),
        diff=diff,
    )


def _build_diff(previous_text: str, output_text: str, output_path: Path) -> str:
    return "\n".join(
        difflib.unified_diff(
            previous_text.splitlines(),
            output_text.splitlines(),
            fromfile=str(output_path),
            tofile="generated-openapi",
            lineterm="",
        )
    )


def format_pretty_report(report: OpenAPIExportReport) -> str:
    mode = "check" if report.check_only else "export"
    lines = [
        f"OpenAPI {mode} report",
        f"output_path: {report.output_path}",
        f"ok: {report.ok}",
        f"changed: {report.changed}",
        f"path_count: {report.path_count}",
        f"schema_count: {report.schema_count}",
    ]
    if report.diff:
        lines.extend(["diff:", report.diff])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="导出 FastAPI OpenAPI 快照，或在发布前检查快照是否最新。")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="OpenAPI JSON 输出路径，默认 docs/api/openapi.json。")
    parser.add_argument("--check", action="store_true", help="只比对不写入；快照过期时返回非零。")
    parser.add_argument("--no-diff", action="store_true", help="check 模式下不打印 unified diff。")
    parser.add_argument("--format", choices=("pretty", "json"), default="pretty", help="输出格式。")
    args = parser.parse_args()

    output_path = Path(args.output)
    if args.check:
        report = check_openapi_export(output_path, include_diff=not args.no_diff)
    else:
        report = export_openapi(output_path)

    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_pretty_report(report))
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
