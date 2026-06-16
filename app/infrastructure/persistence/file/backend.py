from __future__ import annotations

# app/infrastructure/persistence/file/backend.py: file metadata backend 的路径和 JSON 辅助能力。

import json
from pathlib import Path
from typing import Any

from app.domains.jobs.paths import JobPaths, build_job_paths


class FilePersistenceBackend:
    """保存 file backend 的稳定目录布局和原子 JSON 写入规则。"""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.jobs_dir = data_dir / "jobs"
        self.document_files_dir = data_dir / "document_files"
        self.document_jobs_dir = data_dir / "document_jobs"
        self.document_job_callback_messages_dir = data_dir / "document_job_callback_messages"
        self.stage_messages_dir = data_dir / "stage_messages"
        self.tmp_dir = data_dir / "tmp"
        self.audit_events_jsonl = data_dir / "audit_events.jsonl"
        for path in (
            self.jobs_dir,
            self.document_files_dir,
            self.document_jobs_dir,
            self.document_job_callback_messages_dir,
            self.stage_messages_dir,
            self.tmp_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def job_paths(self, job_id: str) -> JobPaths:
        return build_job_paths(self.data_dir, job_id)

    def write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def append_json_line(self, path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")

    def read_json_lines(self, path: Path) -> list[str]:
        if not path.exists():
            return []
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
