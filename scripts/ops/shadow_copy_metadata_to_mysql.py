from __future__ import annotations

# scripts/ops/shadow_copy_metadata_to_mysql.py: 离线复制 local file metadata 到 MySQL 并校验一致性。

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.repositories.mysql_job_repository import ConnectFactory, MysqlJobRepository, MysqlJobRepositoryConfig
from scripts.ops.shadow_copy_metadata_to_database import (
    MetadataShadowCopyMismatch,
    _MetadataMirror,
    _collect_file_metadata,
    _compare_mirrors,
    _copy_metadata,
)


@dataclass(slots=True)
class MysqlMetadataMigrationReport:
    data_dir: str
    mysql_database: str
    target_empty_before_copy: bool
    source_totals: dict[str, int]
    target_totals: dict[str, int]
    mismatches: list[MetadataShadowCopyMismatch] = field(default_factory=list)
    validate_only: bool = False

    @property
    def ok(self) -> bool:
        return not self.mismatches

    @property
    def mismatch_count(self) -> int:
        return len(self.mismatches)

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_dir": self.data_dir,
            "mysql_database": self.mysql_database,
            "target_empty_before_copy": self.target_empty_before_copy,
            "validate_only": self.validate_only,
            "ok": self.ok,
            "mismatch_count": self.mismatch_count,
            "source_totals": self.source_totals,
            "target_totals": self.target_totals,
            "mismatches": [item.to_dict() for item in self.mismatches],
        }


def shadow_copy_metadata_to_mysql(
    data_dir: Path,
    config: MysqlJobRepositoryConfig,
    *,
    connect_factory: ConnectFactory | None = None,
) -> MysqlMetadataMigrationReport:
    """把 local file metadata 复制到空 MySQL metadata store 后校验一致性。"""

    resolved_data_dir = data_dir.resolve()
    source = _collect_file_metadata(resolved_data_dir)
    target_repository = MysqlJobRepository(config, connect_factory=connect_factory)
    before = _collect_mysql_metadata(target_repository)
    if not _mirror_is_empty(before):
        return MysqlMetadataMigrationReport(
            data_dir=str(resolved_data_dir),
            mysql_database=config.database,
            target_empty_before_copy=False,
            source_totals=source.totals(),
            target_totals=before.totals(),
            mismatches=[
                MetadataShadowCopyMismatch(
                    code="target_not_empty",
                    message="目标 MySQL metadata store 已有数据；默认拒绝写入以避免 append-only metadata 重复。",
                )
            ],
        )

    _copy_metadata(source, target_repository)
    return _validate_metadata_shadow_copy_to_mysql(
        resolved_data_dir,
        config,
        connect_factory=connect_factory,
        target_empty_before_copy=True,
        validate_only=False,
    )


def validate_metadata_shadow_copy_to_mysql(
    data_dir: Path,
    config: MysqlJobRepositoryConfig,
    *,
    connect_factory: ConnectFactory | None = None,
) -> MysqlMetadataMigrationReport:
    """只读校验 local file metadata 与 MySQL metadata 是否一致。"""

    return _validate_metadata_shadow_copy_to_mysql(
        data_dir.resolve(),
        config,
        connect_factory=connect_factory,
        target_empty_before_copy=False,
        validate_only=True,
    )


def _validate_metadata_shadow_copy_to_mysql(
    data_dir: Path,
    config: MysqlJobRepositoryConfig,
    *,
    connect_factory: ConnectFactory | None,
    target_empty_before_copy: bool,
    validate_only: bool,
) -> MysqlMetadataMigrationReport:
    source = _collect_file_metadata(data_dir)
    target_repository = MysqlJobRepository(config, connect_factory=connect_factory)
    target = _collect_mysql_metadata(target_repository)
    return MysqlMetadataMigrationReport(
        data_dir=str(data_dir),
        mysql_database=config.database,
        target_empty_before_copy=target_empty_before_copy,
        validate_only=validate_only,
        source_totals=source.totals(),
        target_totals=target.totals(),
        mismatches=_compare_mirrors(source, target),
    )


def _collect_mysql_metadata(repository: MysqlJobRepository) -> _MetadataMirror:
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


def _mirror_is_empty(mirror: _MetadataMirror) -> bool:
    return all(value == 0 for value in mirror.totals().values())


def format_pretty_report(report: MysqlMetadataMigrationReport) -> str:
    lines = [
        "MySQL metadata migration report",
        f"data_dir: {report.data_dir}",
        f"mysql_database: {report.mysql_database}",
        f"validate_only: {report.validate_only}",
        f"target_empty_before_copy: {report.target_empty_before_copy}",
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


def _config_from_settings(settings: Settings, args: argparse.Namespace) -> MysqlJobRepositoryConfig:
    return MysqlJobRepositoryConfig(
        host=args.host or settings.jobs_mysql_host,
        port=args.port or settings.jobs_mysql_port,
        user=args.user or settings.jobs_mysql_user,
        password=args.password if args.password is not None else settings.jobs_mysql_password,
        database=args.database or settings.jobs_mysql_database,
        charset=args.charset or settings.jobs_mysql_charset,
        connect_timeout_seconds=args.connect_timeout_seconds or settings.jobs_mysql_connect_timeout_seconds,
    )


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(description="离线复制 local file metadata 到 MySQL 并校验一致性。")
    parser.add_argument("--data-dir", default=str(settings.data_path), help="运行态 data 目录，默认读取当前 Settings.data_path。")
    parser.add_argument("--host", default=None, help="MySQL host，默认读取 JOBS_MYSQL_HOST。")
    parser.add_argument("--port", type=int, default=None, help="MySQL port，默认读取 JOBS_MYSQL_PORT。")
    parser.add_argument("--user", default=None, help="MySQL user，默认读取 JOBS_MYSQL_USER。")
    parser.add_argument("--password", default=None, help="MySQL password，默认读取 JOBS_MYSQL_PASSWORD。")
    parser.add_argument("--database", default=None, help="MySQL database，默认读取 JOBS_MYSQL_DATABASE。")
    parser.add_argument("--charset", default=None, help="MySQL charset，默认读取 JOBS_MYSQL_CHARSET。")
    parser.add_argument("--connect-timeout-seconds", type=int, default=None, help="MySQL connect timeout，默认读取配置。")
    parser.add_argument("--validate-only", action="store_true", help="只校验，不执行 shadow copy。")
    parser.add_argument("--format", choices=("pretty", "json"), default="pretty", help="输出格式。")
    args = parser.parse_args()

    config = _config_from_settings(settings, args)
    if args.validate_only:
        report = validate_metadata_shadow_copy_to_mysql(Path(args.data_dir), config)
    else:
        report = shadow_copy_metadata_to_mysql(Path(args.data_dir), config)

    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_pretty_report(report))
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
