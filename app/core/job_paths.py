from __future__ import annotations

# app/core/job_paths.py: 定义单个 job 的本地目录布局和 artifact 逻辑路径解析。

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class JobPaths:
    root: Path
    input_dir: Path
    work_dir: Path
    output_dir: Path
    translation_dir: Path
    source_package: Path
    source_pdf: Path
    parsed_result_package: Path
    result_docx: Path
    translation_request: Path
    job_json: Path
    files_json: Path
    events_jsonl: Path


def build_job_paths(data_dir: Path, job_id: str) -> JobPaths:
    job_root = data_dir / "jobs" / job_id
    input_dir = job_root / "input"
    work_dir = job_root / "work"
    output_dir = job_root / "output"
    translation_dir = job_root / "translation"
    return JobPaths(
        root=job_root,
        input_dir=input_dir,
        work_dir=work_dir,
        output_dir=output_dir,
        translation_dir=translation_dir,
        source_package=input_dir / "source.zip",
        source_pdf=input_dir / "source.pdf",
        parsed_result_package=input_dir / "parsed-result.zip",
        result_docx=output_dir / "result.docx",
        translation_request=translation_dir / "request.json",
        job_json=job_root / "job.json",
        files_json=job_root / "files.json",
        events_jsonl=job_root / "events.jsonl",
    )


def ensure_job_dirs(paths: JobPaths) -> None:
    for directory in (paths.input_dir, paths.work_dir, paths.output_dir, paths.translation_dir):
        directory.mkdir(parents=True, exist_ok=True)


def resolve_artifact_path(paths: JobPaths, logical_path: str) -> Path:
    resolved_root = paths.root.resolve()
    candidate = (paths.root / logical_path).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError(f"产物路径越界: {logical_path}")
    return candidate
