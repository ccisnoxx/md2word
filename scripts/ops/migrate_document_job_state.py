"""状态迁移：独立维护状态/查询列，按单批游标只补业务状态缺键。"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError

from app.core.config import Settings
from app.domains.document_jobs.delivery_state import (
    DOCUMENT_JOB_STATE_FIELDS,
    backfill_document_job_state_payload,
    document_job_state_columns,
)
from app.domains.document_jobs.models import DocumentJobRecord
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.infrastructure.persistence.file.document_jobs import FileDocumentJobRepository
from app.infrastructure.persistence.mysql.backend import (
    ConnectFactory, MysqlPersistenceBackend, MysqlPersistenceConfig,
)
from app.infrastructure.persistence.mysql.document_jobs import MysqlDocumentJobRepository
from app.infrastructure.persistence.mysql.schema import MYSQL_SCHEMA_COLUMN_MAINTENANCE
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.infrastructure.persistence.sqlite.document_jobs import SqliteDocumentJobRepository
from app.infrastructure.persistence.sqlite.schema import DOCUMENT_JOB_LIST_QUERY_COLUMNS, DOCUMENT_JOB_STATE_COLUMNS


STATE_COLUMNS = tuple(name for name, _ in DOCUMENT_JOB_STATE_COLUMNS)
SCHEMA_COLUMNS = STATE_COLUMNS + tuple(name for name, _ in DOCUMENT_JOB_LIST_QUERY_COLUMNS)
BASE_COLUMNS = {"job_id", "payload", "created_at", "updated_at"}
SAFE_JOB_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")


class MigrationError(Exception):
    """只携带固定错误类别，避免底层异常泄露 payload、路径或连接信息。"""


def _check_job_id(job_id: Any) -> str:
    if not isinstance(job_id, str) or not SAFE_JOB_ID.fullmatch(job_id) or job_id in {".", ".."}:
        raise MigrationError("unsafe_job_id")
    return job_id


def _file_path(root: Path, job_id: str) -> Path:
    _check_job_id(job_id)
    path = root / job_id / "job.json"
    # 迁移只接触原存储根中的普通文件；不能沿 job、payload 或旁路锁的符号链接写出边界。
    for candidate in (path.parent, path, path.with_suffix(".json.tmp"), path.with_name("job.lock")):
        if candidate.is_symlink() or not candidate.resolve().is_relative_to(root.resolve()):
            raise MigrationError("unsafe_file_path")
    if not path.is_file():
        raise MigrationError("missing_job_file")
    return path


@contextmanager
def _sqlite_connection(path: Path, *, readonly: bool) -> Iterator[sqlite3.Connection]:
    if readonly:
        # immutable 禁止 SQLite 写入共享内存等旁文件；有未合并日志时不能据此读旧快照。
        # 运维窗口须先停写并 checkpoint，而不是让预检修改目标来恢复日志。
        if any(Path(str(path) + suffix).exists() and Path(str(path) + suffix).stat().st_size
               for suffix in ("-wal", "-journal")):
            raise MigrationError("sqlite_requires_checkpoint")
    uri = path.resolve().as_uri() + ("?mode=ro&immutable=1" if readonly else "?mode=rw")
    connection = sqlite3.connect(uri, uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        if readonly:
            connection.execute("PRAGMA query_only = ON")
        yield connection
        if not readonly:
            connection.commit()
    except BaseException:
        if not readonly:
            connection.rollback()
        raise
    finally:
        connection.close()


def _schema_columns(connection: Any, backend: str) -> set[str]:
    if backend == "database":
        return {row["name"] for row in connection.execute("PRAGMA table_info(document_jobs)")}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COLUMN_NAME AS column_name FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s", ("document_jobs",),
        )
        return {row["column_name"] for row in cursor.fetchall()}


def _apply_schema(connection: Any, backend: str, missing: list[str], added: list[str]) -> None:
    definitions = dict((*DOCUMENT_JOB_STATE_COLUMNS, *DOCUMENT_JOB_LIST_QUERY_COLUMNS)) if backend == "database" else {
        name: definition for table, name, definition in MYSQL_SCHEMA_COLUMN_MAINTENANCE
        if table == "document_jobs"
    }
    for name in missing:
        definition = f"{name} {definitions[name]}" if backend == "database" else definitions[name]
        statement = f"ALTER TABLE document_jobs ADD COLUMN {definition}"
        if backend == "database":
            connection.execute(statement)
        else:
            with connection.cursor() as cursor:
                cursor.execute(statement)
        # 每列明确前滚；MySQL DDL 可能早已隐式提交，异常时绝不宣称整批撤销。
        connection.commit()
        added.append(name)


def _sql_batch(connection: Any, backend: str, columns: set[str], after: str, limit: int) -> list[Any]:
    selected = ", ".join(("job_id", "payload", *(name for name in STATE_COLUMNS if name in columns)))
    marker = "?" if backend == "database" else "%s"
    query = (f"SELECT {selected} FROM document_jobs WHERE job_id > {marker} "
             f"ORDER BY job_id LIMIT {marker}")
    if backend == "database":
        return connection.execute(query, (after, limit)).fetchall()
    with connection.cursor() as cursor:
        cursor.execute(query, (after, limit))
        return cursor.fetchall()


def _payload_and_differences(row: Any, columns: set[str], report: dict[str, Any]) -> None:
    payload = json.loads(row["payload"])
    if not isinstance(payload, dict):
        raise MigrationError("invalid_payload_type")
    if payload.get("id") != row["job_id"]:
        raise MigrationError("job_id_mismatch")
    updated = backfill_document_job_state_payload(payload)
    missing = [name for name in DOCUMENT_JOB_STATE_FIELDS if name not in payload]
    if missing:
        report["payload_missing"].append({"job_id": row["job_id"], "fields": missing})
        report["missing_field_count"] += len(missing)
    expected = document_job_state_columns(DocumentJobRecord.model_validate(updated))
    mismatches = []
    for name, value in zip(STATE_COLUMNS, expected, strict=True):
        if name not in columns:
            continue
        actual = row[name]
        if name == "quality_summary_json":
            try:
                # JSON 文本格式/键序差异不是数据分歧，NULL 和非法 JSON 则仍是分歧。
                equal = isinstance(actual, str) and json.dumps(json.loads(actual), sort_keys=True) == json.dumps(
                    json.loads(value), sort_keys=True,
                )
            except (ValueError, TypeError):
                equal = False
        else:
            equal = actual == value
        if not equal:
            mismatches.append(name)
    if mismatches:
        report["column_mismatches"].append({"job_id": row["job_id"], "columns": mismatches})


def _error_category(error: Exception) -> str:
    if isinstance(error, MigrationError):
        return str(error)
    if isinstance(error, (json.JSONDecodeError, UnicodeDecodeError)):
        return "invalid_json"
    if isinstance(error, ValidationError):
        return "invalid_document_job_state"
    if isinstance(error, FileNotFoundError):
        return "target_missing"
    return "storage_error"


def migrate_document_job_state(
    settings: Settings, *, mode: str = "dry-run", phase: str = "all", batch_size: int = 100,
    after_job_id: str = "", mysql_connect_factory: ConnectFactory | None = None,
) -> dict[str, Any]:
    """处理至多一批；返回可安全打印的报告，游标仅在该行校验/提交成功后推进。

    dry-run 差异只作预览；verify 遇差异或后续行返回 1；apply 成功处理一批返回 0，
    调用方须按 has_more 与 last_successful_job_id 续跑。错误返回 1，参数错误由 CLI 返回 2。
    """
    backend = settings.jobs_repository_backend
    report: dict[str, Any] = {
        "backend": backend, "mode": mode, "phase": phase,
        "schema_missing": [], "schema_added": [], "schema_remaining": [],
        "scanned_rows": 0, "processed_rows": 0, "payloads_backfilled": 0,
        "missing_field_count": 0, "payload_missing": [], "column_mismatches": [], "errors": [],
        "last_successful_job_id": "", "has_more": None, "exit_code": 0,
    }
    current_id: str | None = None
    try:
        if mode not in {"dry-run", "apply", "verify"} or phase not in {"schema", "backfill", "all"} or batch_size < 1:
            raise MigrationError("invalid_arguments")
        if after_job_id:
            _check_job_id(after_job_id)
        report["last_successful_job_id"] = after_job_id
        repository = None
        mysql_backend = None
        file_root = settings.data_path / "document_jobs"
        database_path = settings.jobs_metadata_database_file
        if backend == "file":
            if file_root.is_symlink() or not file_root.resolve().is_relative_to(settings.data_path.resolve()):
                raise MigrationError("unsafe_file_path")
            if not file_root.is_dir():
                raise MigrationError("target_missing")
        elif backend == "database":
            if not database_path.is_file():
                raise MigrationError("target_missing")
        elif backend == "mysql":
            mysql_backend = MysqlPersistenceBackend(MysqlPersistenceConfig(
                host=settings.jobs_mysql_host, port=settings.jobs_mysql_port,
                user=settings.jobs_mysql_user, password=settings.jobs_mysql_password,
                database=settings.jobs_mysql_database, charset=settings.jobs_mysql_charset,
                connect_timeout_seconds=settings.jobs_mysql_connect_timeout_seconds,
            ), connect_factory=mysql_connect_factory, initialize=False)
        else:
            raise MigrationError("invalid_backend")

        @contextmanager
        def sql_connection(*, readonly: bool) -> Iterator[Any]:
            if backend == "database":
                with _sqlite_connection(database_path, readonly=readonly) as connection:
                    yield connection
            else:
                with mysql_backend.connect() as connection:
                    if readonly:
                        with connection.cursor() as cursor:
                            cursor.execute("SET TRANSACTION READ ONLY")
                    yield connection

        columns: set[str] = set()
        if backend != "file":
            with sql_connection(readonly=mode != "apply") as connection:
                columns = _schema_columns(connection, backend)
                if not BASE_COLUMNS.issubset(columns):
                    raise MigrationError("document_jobs_schema_missing")
                missing = [name for name in SCHEMA_COLUMNS if name not in columns]
                report["schema_missing"] = missing
                report["schema_remaining"] = missing.copy()
                if mode == "apply" and phase in {"schema", "all"}:
                    _apply_schema(connection, backend, missing, report["schema_added"])
                    columns = _schema_columns(connection, backend)
                    report["schema_remaining"] = [name for name in SCHEMA_COLUMNS if name not in columns]
                if mode == "apply" and report["schema_remaining"]:
                    raise MigrationError("state_columns_missing")
        if phase != "schema":
            if backend == "file":
                ids = sorted(path.name for path in file_root.iterdir()
                             if path.name > after_job_id and (path / "job.json").exists())
                rows = [{"job_id": job_id} for job_id in ids[:batch_size + 1]]
            else:
                with sql_connection(readonly=True) as connection:
                    rows = _sql_batch(connection, backend, columns, after_job_id, batch_size + 1)
            report["has_more"] = len(rows) > batch_size
            for row in rows[:batch_size]:
                current_id = _check_job_id(row["job_id"])
                report["scanned_rows"] += 1
                if backend == "file":
                    row["payload"] = _file_path(file_root, current_id).read_text(encoding="utf-8")
                _payload_and_differences(row, columns, report)
                if mode == "apply":
                    if repository is None:
                        if backend == "file":
                            repository = FileDocumentJobRepository(FilePersistenceBackend(settings.data_path))
                        elif backend == "database":
                            repository = SqliteDocumentJobRepository(SqlitePersistenceBackend(database_path, initialize=False))
                        else:
                            repository = MysqlDocumentJobRepository(mysql_backend)
                    if repository.backfill_document_job_state_if_missing(current_id):
                        report["payloads_backfilled"] += 1
                report["processed_rows"] += 1
                report["last_successful_job_id"] = current_id
                current_id = None
    except KeyboardInterrupt:
        report["errors"].append({"job_id": current_id, "category": "interrupted"})
    except Exception as error:
        report["errors"].append({"job_id": current_id, "category": _error_category(error)})
    report["schema_remaining"] = [name for name in report["schema_remaining"]
                                  if name not in report["schema_added"]]
    if report["errors"]:
        if phase != "schema":
            report["has_more"] = True
        report["exit_code"] = 1
    elif mode == "verify" and (report["schema_remaining"] or report["payload_missing"]
                               or report["column_mismatches"] or report["has_more"]):
        report["exit_code"] = 1
    report["error_count"] = len(report["errors"])
    report["rows_missing_fields"] = len(report["payload_missing"])
    report["rows_with_column_mismatches"] = len(report["column_mismatches"])
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(
        "Migration A：暂停 DocumentJob 写者并备份后，单实例增量补列/回填。"
        "每次处理一批，按报告游标续跑；MySQL DDL 失败保留已加列，不自动回滚或删列。"))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", dest="mode", action="store_const", const="dry-run", help="只读预检（默认）")
    modes.add_argument("--apply", dest="mode", action="store_const", const="apply", help="显式执行所选阶段")
    modes.add_argument("--verify", dest="mode", action="store_const", const="verify", help="只读校验；差异或后续行返回 1")
    parser.set_defaults(mode="dry-run")
    parser.add_argument("--phase", choices=("schema", "backfill", "all"), default="all", help="迁移阶段（默认 all）")
    parser.add_argument("--batch-size", type=int, default=100, help="本次最多处理的行数（默认 100）")
    parser.add_argument("--after-job-id", default="", help="从最后成功 job ID 之后续跑")
    parser.add_argument("--backend", choices=("file", "database", "mysql"), help="覆盖 JOBS_REPOSITORY_BACKEND；database 表示 SQLite")
    parser.add_argument("--data-dir", help="覆盖 DATA_DIR，仅定位 metadata，不创建缺失目标")
    parser.add_argument("--database-path", help="覆盖 JOBS_METADATA_DATABASE_PATH；建议绝对路径")
    args = parser.parse_args(argv)
    if args.batch_size < 1:
        parser.error("--batch-size 必须大于 0")
    overrides = {key: value for key, value in {
        "jobs_repository_backend": args.backend, "data_dir": args.data_dir,
        "jobs_metadata_database_path": args.database_path,
    }.items() if value is not None}
    try:
        settings = Settings(**overrides)
    except Exception:
        print(json.dumps({"exit_code": 1, "errors": [{"job_id": None, "category": "invalid_configuration"}]}))
        return 1
    report = migrate_document_job_state(settings, mode=args.mode, phase=args.phase,
                                       batch_size=args.batch_size, after_job_id=args.after_job_id)
    print(json.dumps(report, ensure_ascii=False))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
