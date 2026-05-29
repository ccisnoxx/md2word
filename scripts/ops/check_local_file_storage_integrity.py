from __future__ import annotations

# scripts/ops/check_local_file_storage_integrity.py: 只读校验 local file jobs 存储的迁移前完整性。

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.core.config import Settings
from app.core.job_models import JobEvent, JobFile, JobRecord, JobStageMessage
from app.core.job_paths import build_job_paths
from app.services.jobs.artifact_integrity import ArtifactFingerprintMismatch, validate_artifact_fingerprint
from app.services.jobs.artifact_storage import LocalArtifactStorageAdapter
from app.services.jobs.artifacts import JobArtifactService


IssueSeverity = Literal["warning", "blocker"]


@dataclass(frozen=True, slots=True)
class IntegrityIssue:
    code: str
    path: str
    message: str
    severity: IssueSeverity = "blocker"
    job_id: str | None = None
    file_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "severity": self.severity,
            "job_id": self.job_id,
            "file_type": self.file_type,
        }


@dataclass(slots=True)
class LocalFileStorageIntegrityReport:
    data_dir: str
    totals: dict[str, int]
    stage_messages_by_status: dict[str, int]
    missing_artifacts: list[IntegrityIssue] = field(default_factory=list)
    non_migratable_items: list[IntegrityIssue] = field(default_factory=list)
    warnings: list[IntegrityIssue] = field(default_factory=list)
    read_only: bool = True

    @property
    def blocker_count(self) -> int:
        return len(self.missing_artifacts) + len(self.non_migratable_items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_dir": self.data_dir,
            "read_only": self.read_only,
            "blocker_count": self.blocker_count,
            "totals": self.totals,
            "stage_messages_by_status": self.stage_messages_by_status,
            "missing_artifacts": [item.to_dict() for item in self.missing_artifacts],
            "non_migratable_items": [item.to_dict() for item in self.non_migratable_items],
            "warnings": [item.to_dict() for item in self.warnings],
        }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _add_issue(items: list[IntegrityIssue], *, code: str, path: Path, message: str, job_id: str | None = None, file_type: str | None = None) -> None:
    items.append(
        IntegrityIssue(
            code=code,
            path=str(path),
            message=message,
            job_id=job_id,
            file_type=file_type,
        )
    )


def _build_empty_totals() -> dict[str, int]:
    return {
        "job_directories": 0,
        "job_records": 0,
        "job_files": 0,
        "job_events": 0,
        "stage_messages": 0,
        "registered_local_artifacts": 0,
        "artifacts_missing_fingerprint": 0,
        "artifacts_fingerprint_mismatch": 0,
    }


def check_local_file_storage_integrity(data_dir: Path) -> LocalFileStorageIntegrityReport:
    """只读扫描 local file backend，产出迁移前完整性报告。"""

    resolved_data_dir = data_dir.resolve()
    totals = _build_empty_totals()
    stage_messages_by_status = {"pending": 0, "running": 0, "failed": 0}
    missing_artifacts: list[IntegrityIssue] = []
    non_migratable_items: list[IntegrityIssue] = []
    warnings: list[IntegrityIssue] = []
    valid_job_ids: set[str] = set()
    artifact_storage = LocalArtifactStorageAdapter(JobArtifactService())

    jobs_dir = resolved_data_dir / "jobs"
    if jobs_dir.exists():
        for job_dir in sorted(path for path in jobs_dir.iterdir() if path.is_dir()):
            totals["job_directories"] += 1
            job_json = job_dir / "job.json"
            if not job_json.exists():
                _add_issue(
                    non_migratable_items,
                    code="job_snapshot_missing",
                    path=job_json,
                    message="job 目录缺少 job.json，无法迁移 metadata snapshot。",
                    job_id=job_dir.name,
                )
                continue

            try:
                job = JobRecord.model_validate(_read_json(job_json))
            except Exception as exc:
                _add_issue(
                    non_migratable_items,
                    code="job_snapshot_invalid",
                    path=job_json,
                    message=f"job.json 无法按 JobRecord 解析: {exc}",
                    job_id=job_dir.name,
                )
                continue

            totals["job_records"] += 1
            valid_job_ids.add(job.id)
            if job.id != job_dir.name:
                _add_issue(
                    non_migratable_items,
                    code="job_id_directory_mismatch",
                    path=job_json,
                    message=f"job.json id={job.id} 与目录名 {job_dir.name} 不一致。",
                    job_id=job.id,
                )

            _scan_job_files(
                data_dir=resolved_data_dir,
                job=job,
                totals=totals,
                missing_artifacts=missing_artifacts,
                non_migratable_items=non_migratable_items,
                warnings=warnings,
                artifact_storage=artifact_storage,
            )
            _scan_job_events(
                data_dir=resolved_data_dir,
                job=job,
                totals=totals,
                non_migratable_items=non_migratable_items,
            )

    _scan_stage_messages(
        data_dir=resolved_data_dir,
        valid_job_ids=valid_job_ids,
        totals=totals,
        stage_messages_by_status=stage_messages_by_status,
        non_migratable_items=non_migratable_items,
    )

    return LocalFileStorageIntegrityReport(
        data_dir=str(resolved_data_dir),
        totals=totals,
        stage_messages_by_status=stage_messages_by_status,
        missing_artifacts=missing_artifacts,
        non_migratable_items=non_migratable_items,
        warnings=warnings,
    )


def _scan_job_files(
    *,
    data_dir: Path,
    job: JobRecord,
    totals: dict[str, int],
    missing_artifacts: list[IntegrityIssue],
    non_migratable_items: list[IntegrityIssue],
    warnings: list[IntegrityIssue],
    artifact_storage: LocalArtifactStorageAdapter,
) -> None:
    job_paths = build_job_paths(data_dir, job.id)
    files_json = job_paths.files_json
    if not files_json.exists():
        warnings.append(
            IntegrityIssue(
                code="job_files_manifest_missing",
                path=str(files_json),
                message="job 缺少 files.json，将按 0 个 artifact 记录处理。",
                severity="warning",
                job_id=job.id,
            )
        )
        return

    try:
        payload = _read_json(files_json)
    except Exception as exc:
        _add_issue(
            non_migratable_items,
            code="job_files_manifest_invalid_json",
            path=files_json,
            message=f"files.json 不是合法 JSON: {exc}",
            job_id=job.id,
        )
        return
    if not isinstance(payload, list):
        _add_issue(
            non_migratable_items,
            code="job_files_manifest_not_list",
            path=files_json,
            message="files.json 顶层必须是列表。",
            job_id=job.id,
        )
        return

    for index, item in enumerate(payload):
        item_path = files_json.with_name(f"{files_json.name}#{index}")
        try:
            file = JobFile.model_validate(item)
        except Exception as exc:
            _add_issue(
                non_migratable_items,
                code="job_file_invalid",
                path=item_path,
                message=f"JobFile 记录无法解析: {exc}",
                job_id=job.id,
            )
            continue

        totals["job_files"] += 1
        try:
            artifact_path = artifact_storage.resolve_download_path(job_paths, file, validate_integrity=False)
        except Exception as exc:
            _add_issue(
                non_migratable_items,
                code="job_file_path_invalid",
                path=files_json,
                message=f"JobFile.path 不能解析为当前 file_type 的本地 artifact 路径: {exc}",
                job_id=job.id,
                file_type=file.file_type,
            )
            continue

        totals["registered_local_artifacts"] += 1
        if not artifact_path.exists():
            _add_issue(
                missing_artifacts,
                code="registered_artifact_missing",
                path=artifact_path,
                message="files.json 中登记的本地 artifact 文件不存在。",
                job_id=job.id,
                file_type=file.file_type,
            )
            continue

        if file.size_bytes is None or file.sha256 is None:
            totals["artifacts_missing_fingerprint"] += 1
            warnings.append(
                IntegrityIssue(
                    code="artifact_fingerprint_missing",
                    path=str(files_json),
                    message="JobFile 缺少 size_bytes 或 sha256，按旧记录兼容但建议后续 backfill。",
                    severity="warning",
                    job_id=job.id,
                    file_type=file.file_type,
                )
            )
            continue

        try:
            validate_artifact_fingerprint(file, artifact_path)
        except ArtifactFingerprintMismatch as exc:
            totals["artifacts_fingerprint_mismatch"] += 1
            _add_issue(
                non_migratable_items,
                code=_fingerprint_mismatch_code(exc),
                path=files_json,
                message=str(exc),
                job_id=job.id,
                file_type=file.file_type,
            )


def _fingerprint_mismatch_code(exc: ArtifactFingerprintMismatch) -> str:
    message = str(exc)
    if "大小不匹配" in message:
        return "artifact_size_mismatch"
    if "sha256 不匹配" in message:
        return "artifact_sha256_mismatch"
    return "artifact_fingerprint_mismatch"


def _scan_job_events(
    *,
    data_dir: Path,
    job: JobRecord,
    totals: dict[str, int],
    non_migratable_items: list[IntegrityIssue],
) -> None:
    events_jsonl = build_job_paths(data_dir, job.id).events_jsonl
    if not events_jsonl.exists():
        return
    for line_number, line in enumerate(events_jsonl.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            JobEvent.model_validate_json(line)
        except Exception as exc:
            _add_issue(
                non_migratable_items,
                code="job_event_invalid",
                path=events_jsonl,
                message=f"events.jsonl 第 {line_number} 行无法按 JobEvent 解析: {exc}",
                job_id=job.id,
            )
            continue
        totals["job_events"] += 1


def _scan_stage_messages(
    *,
    data_dir: Path,
    valid_job_ids: set[str],
    totals: dict[str, int],
    stage_messages_by_status: dict[str, int],
    non_migratable_items: list[IntegrityIssue],
) -> None:
    stage_messages_dir = data_dir / "stage_messages"
    if not stage_messages_dir.exists():
        return
    for path in sorted(stage_messages_dir.glob("*.json")):
        try:
            message = JobStageMessage.model_validate(_read_json(path))
        except Exception as exc:
            _add_issue(
                non_migratable_items,
                code="stage_message_invalid",
                path=path,
                message=f"stage message 无法解析: {exc}",
            )
            continue

        totals["stage_messages"] += 1
        stage_messages_by_status[message.status] = stage_messages_by_status.get(message.status, 0) + 1
        if message.job_id not in valid_job_ids:
            _add_issue(
                non_migratable_items,
                code="stage_message_job_missing",
                path=path,
                message=f"stage message 引用的 job_id={message.job_id} 没有可迁移的 job snapshot。",
                job_id=message.job_id,
            )


def format_pretty_report(report: LocalFileStorageIntegrityReport) -> str:
    lines = [
        "Local file storage integrity report",
        f"data_dir: {report.data_dir}",
        f"read_only: {report.read_only}",
        f"blocker_count: {report.blocker_count}",
        "totals:",
    ]
    for key, value in report.totals.items():
        lines.append(f"  {key}: {value}")
    lines.append("stage_messages_by_status:")
    for key, value in report.stage_messages_by_status.items():
        lines.append(f"  {key}: {value}")
    lines.append(f"missing_artifacts: {len(report.missing_artifacts)}")
    for issue in report.missing_artifacts:
        lines.append(f"  - [{issue.code}] job_id={issue.job_id} file_type={issue.file_type} path={issue.path}")
    lines.append(f"non_migratable_items: {len(report.non_migratable_items)}")
    for issue in report.non_migratable_items:
        lines.append(f"  - [{issue.code}] job_id={issue.job_id} path={issue.path} message={issue.message}")
    lines.append(f"warnings: {len(report.warnings)}")
    for issue in report.warnings:
        lines.append(f"  - [{issue.code}] job_id={issue.job_id} path={issue.path} message={issue.message}")
    return "\n".join(lines)


def main() -> None:
    default_data_dir = Settings().data_path
    parser = argparse.ArgumentParser(description="只读校验 local file jobs 存储的迁移前完整性。")
    parser.add_argument("--data-dir", default=str(default_data_dir), help="运行态 data 目录，默认读取当前 Settings.data_path。")
    parser.add_argument("--format", choices=("pretty", "json"), default="pretty", help="输出格式。")
    args = parser.parse_args()

    report = check_local_file_storage_integrity(Path(args.data_dir))
    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_pretty_report(report))
    raise SystemExit(1 if report.blocker_count else 0)


if __name__ == "__main__":
    main()
