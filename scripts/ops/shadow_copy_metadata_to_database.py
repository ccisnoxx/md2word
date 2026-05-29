from __future__ import annotations

# scripts/ops/shadow_copy_metadata_to_database.py: 离线复制 local file metadata 到 database 并校验一致性。

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.core.job_models import (
    JobEvent,
    JobFile,
    JobRecord,
    JobStageMessage,
    sync_source_pdf_compatibility_fields,
)
from app.repositories.database_job_repository import DatabaseJobRepository
from app.repositories.file_job_repository import FileJobRepository


@dataclass(frozen=True, slots=True)
class MetadataShadowCopyMismatch:
    code: str
    message: str
    job_id: str | None = None
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "job_id": self.job_id,
            "field": self.field,
        }


@dataclass(slots=True)
class MetadataShadowCopyReport:
    data_dir: str
    database_path: str
    target_replaced: bool
    source_totals: dict[str, int]
    target_totals: dict[str, int]
    mismatches: list[MetadataShadowCopyMismatch] = field(default_factory=list)
    temp_database_path: str | None = None

    @property
    def ok(self) -> bool:
        return not self.mismatches

    @property
    def mismatch_count(self) -> int:
        return len(self.mismatches)

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_dir": self.data_dir,
            "database_path": self.database_path,
            "temp_database_path": self.temp_database_path,
            "target_replaced": self.target_replaced,
            "ok": self.ok,
            "mismatch_count": self.mismatch_count,
            "source_totals": self.source_totals,
            "target_totals": self.target_totals,
            "mismatches": [item.to_dict() for item in self.mismatches],
        }


@dataclass(slots=True)
class _MetadataMirror:
    jobs: list[JobRecord]
    files_by_job: dict[str, list[JobFile]]
    events_by_job: dict[str, list[JobEvent]]
    stage_messages: list[JobStageMessage]

    def totals(self) -> dict[str, int]:
        counts = {
            "job_records": len(self.jobs),
            "job_files": sum(len(items) for items in self.files_by_job.values()),
            "job_events": sum(len(items) for items in self.events_by_job.values()),
            "stage_messages": len(self.stage_messages),
            "stage_messages_pending": 0,
            "stage_messages_running": 0,
            "stage_messages_failed": 0,
        }
        for message in self.stage_messages:
            counts[f"stage_messages_{message.status}"] = counts.get(f"stage_messages_{message.status}", 0) + 1
        return counts


def shadow_copy_metadata_to_database(data_dir: Path, database_path: Path) -> MetadataShadowCopyReport:
    """把 local file metadata 离线复制到 database；校验通过后才替换目标 database。"""

    resolved_data_dir = data_dir.resolve()
    resolved_database_path = database_path.resolve()
    temp_database_path = resolved_database_path.with_name(f"{resolved_database_path.name}.shadow-{uuid4().hex}.tmp")
    try:
        temp_repository = DatabaseJobRepository(temp_database_path)
        _copy_metadata(_collect_file_metadata(resolved_data_dir), temp_repository)
        temp_validation = _validate_metadata_shadow_copy(
            resolved_data_dir,
            temp_database_path,
            target_replaced=False,
            temp_database_path=temp_database_path,
        )
        if not temp_validation.ok:
            return temp_validation

        temp_database_path.replace(resolved_database_path)
        return _validate_metadata_shadow_copy(
            resolved_data_dir,
            resolved_database_path,
            target_replaced=True,
            temp_database_path=temp_database_path,
        )
    finally:
        temp_database_path.unlink(missing_ok=True)


def validate_metadata_shadow_copy(data_dir: Path, database_path: Path) -> MetadataShadowCopyReport:
    """只读校验 local file metadata 与 database metadata 是否一致。"""

    return _validate_metadata_shadow_copy(
        data_dir.resolve(),
        database_path.resolve(),
        target_replaced=False,
        temp_database_path=None,
    )


def _validate_metadata_shadow_copy(
    data_dir: Path,
    database_path: Path,
    *,
    target_replaced: bool,
    temp_database_path: Path | None,
) -> MetadataShadowCopyReport:
    source = _collect_file_metadata(data_dir)
    if not database_path.exists():
        return MetadataShadowCopyReport(
            data_dir=str(data_dir),
            database_path=str(database_path),
            temp_database_path=str(temp_database_path) if temp_database_path is not None else None,
            target_replaced=target_replaced,
            source_totals=source.totals(),
            target_totals=_MetadataMirror([], {}, {}, []).totals(),
            mismatches=[
                MetadataShadowCopyMismatch(
                    code="database_missing",
                    message="目标 database 文件不存在，无法校验 metadata shadow copy。",
                )
            ],
        )

    target = _collect_database_metadata(database_path)
    mismatches = _compare_mirrors(source, target)
    return MetadataShadowCopyReport(
        data_dir=str(data_dir),
        database_path=str(database_path),
        temp_database_path=str(temp_database_path) if temp_database_path is not None else None,
        target_replaced=target_replaced,
        source_totals=source.totals(),
        target_totals=target.totals(),
        mismatches=mismatches,
    )


def _copy_metadata(source: _MetadataMirror, target: DatabaseJobRepository) -> None:
    for job in source.jobs:
        target.create_job(job)
        for file in source.files_by_job[job.id]:
            target.upsert_file(job.id, file)
        for event in source.events_by_job[job.id]:
            target.append_event(job.id, event)
    for message in source.stage_messages:
        target.put_stage_message(message)


def _collect_file_metadata(data_dir: Path) -> _MetadataMirror:
    repository = FileJobRepository(data_dir)
    jobs = sorted(
        [sync_source_pdf_compatibility_fields(job) for job in repository.list_jobs()],
        key=lambda item: item.id,
    )
    files_by_job = {
        job.id: sorted(repository.list_files(job.id), key=lambda item: item.file_type)
        for job in jobs
    }
    events_by_job = {job.id: repository.list_events(job.id) for job in jobs}
    return _MetadataMirror(
        jobs=jobs,
        files_by_job=files_by_job,
        events_by_job=events_by_job,
        stage_messages=_load_local_stage_messages(data_dir),
    )


def _collect_database_metadata(database_path: Path) -> _MetadataMirror:
    repository = DatabaseJobRepository(database_path)
    jobs = sorted(repository.list_jobs(), key=lambda item: item.id)
    files_by_job = {
        job.id: sorted(repository.list_files(job.id), key=lambda item: item.file_type)
        for job in jobs
    }
    events_by_job = {job.id: repository.list_events(job.id) for job in jobs}
    return _MetadataMirror(
        jobs=jobs,
        files_by_job=files_by_job,
        events_by_job=events_by_job,
        stage_messages=sorted(repository.list_stage_messages(), key=lambda item: item.id),
    )


def _load_local_stage_messages(data_dir: Path) -> list[JobStageMessage]:
    stage_messages_dir = data_dir / "stage_messages"
    if not stage_messages_dir.exists():
        return []
    return sorted(
        [
            JobStageMessage.model_validate(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(stage_messages_dir.glob("*.json"))
        ],
        key=lambda item: item.id,
    )


def _compare_mirrors(source: _MetadataMirror, target: _MetadataMirror) -> list[MetadataShadowCopyMismatch]:
    mismatches: list[MetadataShadowCopyMismatch] = []
    if source.totals() != target.totals():
        mismatches.append(
            MetadataShadowCopyMismatch(
                code="totals_mismatch",
                message=f"metadata 总数不一致: source={source.totals()} target={target.totals()}",
            )
        )

    source_job_ids = [job.id for job in source.jobs]
    target_job_ids = [job.id for job in target.jobs]
    if source_job_ids != target_job_ids:
        mismatches.append(
            MetadataShadowCopyMismatch(
                code="job_ids_mismatch",
                message=f"job id 列表不一致: source={source_job_ids} target={target_job_ids}",
                field="jobs",
            )
        )

    for source_job in source.jobs:
        target_job = next((job for job in target.jobs if job.id == source_job.id), None)
        if target_job is None:
            continue
        _compare_payloads(mismatches, source_job.id, "job", source_job, target_job)
        _compare_payloads(
            mismatches,
            source_job.id,
            "files",
            source.files_by_job[source_job.id],
            target.files_by_job.get(source_job.id, []),
        )
        _compare_payloads(
            mismatches,
            source_job.id,
            "events",
            source.events_by_job[source_job.id],
            target.events_by_job.get(source_job.id, []),
        )

    _compare_payloads(mismatches, None, "stage_messages", source.stage_messages, target.stage_messages)
    return mismatches


def _compare_payloads(
    mismatches: list[MetadataShadowCopyMismatch],
    job_id: str | None,
    field: str,
    source_payload: Any,
    target_payload: Any,
) -> None:
    if _dump_payload(source_payload) == _dump_payload(target_payload):
        return
    mismatches.append(
        MetadataShadowCopyMismatch(
            code=f"{field}_mismatch",
            message=f"{field} payload 不一致。",
            job_id=job_id,
            field=field,
        )
    )


def _dump_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_dump_payload(item) for item in payload]
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return payload


def format_pretty_report(report: MetadataShadowCopyReport) -> str:
    lines = [
        "Metadata shadow copy report",
        f"data_dir: {report.data_dir}",
        f"database_path: {report.database_path}",
        f"target_replaced: {report.target_replaced}",
        f"ok: {report.ok}",
        f"mismatch_count: {report.mismatch_count}",
        "source_totals:",
    ]
    for key, value in report.source_totals.items():
        lines.append(f"  {key}: {value}")
    lines.append("target_totals:")
    for key, value in report.target_totals.items():
        lines.append(f"  {key}: {value}")
    lines.append(f"mismatches: {len(report.mismatches)}")
    for mismatch in report.mismatches:
        lines.append(f"  - [{mismatch.code}] job_id={mismatch.job_id} field={mismatch.field} message={mismatch.message}")
    return "\n".join(lines)


def main() -> None:
    default_data_dir = Settings().data_path
    parser = argparse.ArgumentParser(description="离线复制 local file metadata 到 database 并校验一致性。")
    parser.add_argument("--data-dir", default=str(default_data_dir), help="运行态 data 目录，默认读取当前 Settings.data_path。")
    parser.add_argument(
        "--database-path",
        default=str(default_data_dir / "metadata-shadow.sqlite3"),
        help="目标 shadow database 文件，默认写入 data/metadata-shadow.sqlite3。",
    )
    parser.add_argument("--validate-only", action="store_true", help="只校验，不执行 shadow copy。")
    parser.add_argument("--format", choices=("pretty", "json"), default="pretty", help="输出格式。")
    args = parser.parse_args()

    if args.validate_only:
        report = validate_metadata_shadow_copy(Path(args.data_dir), Path(args.database_path))
    else:
        report = shadow_copy_metadata_to_database(Path(args.data_dir), Path(args.database_path))

    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_pretty_report(report))
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
