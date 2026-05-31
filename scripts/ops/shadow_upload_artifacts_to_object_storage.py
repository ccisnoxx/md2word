from __future__ import annotations

# scripts/ops/shadow_upload_artifacts_to_object_storage.py: 上传本地 artifact 到对象目录并回填 JobFile object metadata。

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.core.config import Settings
from app.domains.jobs.paths import build_job_paths
from app.infrastructure.persistence import (
    PersistenceAdapters,
    build_file_persistence_adapters,
    build_sqlite_persistence_adapters,
)
from app.domains.jobs.artifacts import JobArtifactService
from app.domains.jobs.object_artifact_storage import ObjectArtifactStorageAdapter


MetadataBackend = Literal["file", "database"]


@dataclass(frozen=True, slots=True)
class ArtifactShadowUploadIssue:
    code: str
    message: str
    job_id: str
    file_type: str
    path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "job_id": self.job_id,
            "file_type": self.file_type,
            "path": self.path,
        }


@dataclass(slots=True)
class ArtifactShadowUploadReport:
    data_dir: str
    object_root: str
    metadata_backend: MetadataBackend
    totals: dict[str, int]
    uploaded_files: list[dict[str, str]] = field(default_factory=list)
    issues: list[ArtifactShadowUploadIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_dir": self.data_dir,
            "object_root": self.object_root,
            "metadata_backend": self.metadata_backend,
            "ok": self.ok,
            "issue_count": self.issue_count,
            "totals": self.totals,
            "uploaded_files": self.uploaded_files,
            "issues": [item.to_dict() for item in self.issues],
        }


def shadow_upload_artifacts_to_object_storage(
    data_dir: Path,
    object_root: Path,
    *,
    repository: PersistenceAdapters | None = None,
    metadata_backend: MetadataBackend = "file",
) -> ArtifactShadowUploadReport:
    """把已登记本地 artifact 复制到对象目录，并用 upsert 回填 object_key。"""

    resolved_data_dir = data_dir.resolve()
    resolved_object_root = object_root.resolve()
    artifact_storage = ObjectArtifactStorageAdapter(JobArtifactService(), resolved_object_root)
    target_adapters = repository or build_file_persistence_adapters(resolved_data_dir)
    totals = {
        "job_records": 0,
        "job_files": 0,
        "uploaded_artifacts": 0,
    }
    uploaded_files: list[dict[str, str]] = []
    issues: list[ArtifactShadowUploadIssue] = []

    for job in sorted(target_adapters.job_repository.list_jobs(), key=lambda item: item.id):
        totals["job_records"] += 1
        job_paths = build_job_paths(resolved_data_dir, job.id)
        for file in sorted(target_adapters.job_file_repository.list_files(job.id), key=lambda item: item.file_type):
            totals["job_files"] += 1
            try:
                updated_file = artifact_storage.shadow_upload_registered_file(job.id, job_paths, file)
            except Exception as exc:
                issues.append(
                    ArtifactShadowUploadIssue(
                        code="artifact_shadow_upload_failed",
                        message=str(exc),
                        job_id=job.id,
                        file_type=file.file_type,
                        path=file.path,
                    )
                )
                continue

            target_adapters.job_file_repository.upsert_file(job.id, updated_file)
            totals["uploaded_artifacts"] += 1
            uploaded_files.append(
                {
                    "job_id": job.id,
                    "file_type": updated_file.file_type,
                    "path": updated_file.path,
                    "object_key": updated_file.object_key or "",
                }
            )

    return ArtifactShadowUploadReport(
        data_dir=str(resolved_data_dir),
        object_root=str(resolved_object_root),
        metadata_backend=metadata_backend,
        totals=totals,
        uploaded_files=uploaded_files,
        issues=issues,
    )


def build_repository(settings: Settings, metadata_backend: MetadataBackend) -> PersistenceAdapters:
    """按 metadata backend 选择需要回填 JobFile 的 repository。"""

    if metadata_backend == "database":
        return build_sqlite_persistence_adapters(settings.jobs_metadata_database_file)
    return build_file_persistence_adapters(settings.data_path)


def format_pretty_report(report: ArtifactShadowUploadReport) -> str:
    lines = [
        "Artifact shadow upload report",
        f"data_dir: {report.data_dir}",
        f"object_root: {report.object_root}",
        f"metadata_backend: {report.metadata_backend}",
        f"ok: {report.ok}",
        f"issue_count: {report.issue_count}",
        "totals:",
    ]
    for key, value in report.totals.items():
        lines.append(f"  {key}: {value}")
    lines.append(f"uploaded_files: {len(report.uploaded_files)}")
    for item in report.uploaded_files:
        lines.append(
            f"  - job_id={item['job_id']} file_type={item['file_type']} "
            f"path={item['path']} object_key={item['object_key']}"
        )
    lines.append(f"issues: {len(report.issues)}")
    for issue in report.issues:
        lines.append(
            f"  - [{issue.code}] job_id={issue.job_id} file_type={issue.file_type} "
            f"path={issue.path} message={issue.message}"
        )
    return "\n".join(lines)


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(description="上传本地 jobs artifact 到对象目录并回填 JobFile object metadata。")
    parser.add_argument("--data-dir", default=str(settings.data_path), help="运行态 data 目录，默认读取当前 Settings.data_path。")
    parser.add_argument(
        "--object-root",
        default=str(settings.jobs_artifact_object_store_dir),
        help="对象 artifact 根目录，默认读取 Settings.jobs_artifact_object_store_dir。",
    )
    parser.add_argument(
        "--metadata-backend",
        choices=("file", "database"),
        default=settings.jobs_repository_backend,
        help="需要回填 JobFile metadata 的后端。",
    )
    parser.add_argument(
        "--database-path",
        default=str(settings.jobs_metadata_database_file),
        help="metadata-backend=database 时使用的 database 文件。",
    )
    parser.add_argument("--format", choices=("pretty", "json"), default="pretty", help="输出格式。")
    args = parser.parse_args()

    runtime_settings = Settings(
        _env_file=None,
        data_dir=args.data_dir,
        jobs_repository_backend=args.metadata_backend,
        jobs_metadata_database_path=args.database_path,
    )
    repository = build_repository(runtime_settings, args.metadata_backend)
    report = shadow_upload_artifacts_to_object_storage(
        Path(args.data_dir),
        Path(args.object_root),
        repository=repository,
        metadata_backend=args.metadata_backend,
    )
    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_pretty_report(report))
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
