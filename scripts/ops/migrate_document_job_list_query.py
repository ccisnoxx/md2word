"""停全部旧 job/file 写者后分表回填；全量 verify 在同一只读快照中完成。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError

from app.core.config import Settings
from app.domains.document_jobs.list_query import (
    DocumentJobListProjectionUnstable, document_file_review_projection_from_raw,
    document_job_list_projection_from_raw,
)
from app.infrastructure.persistence.mysql.backend import ConnectFactory, MysqlPersistenceBackend, MysqlPersistenceConfig
from scripts.ops.migrate_document_job_state import MigrationError, _error_category


# 表名、列名和版本只来自本工具的固定目标，不能接受请求中的 SQL 标识符。
TABLES = (
    ("document_files", "file_id", "review_query_json", 1, document_file_review_projection_from_raw),
    ("document_jobs", "job_id", "list_query_json", 2, document_job_list_projection_from_raw),
)


def _execute(connection: Any, backend: str, statement: str, params: tuple = ()) -> list[Any]:
    if backend == "database":
        return connection.execute(statement, params).fetchall()
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchall()


def _columns(connection: Any, backend: str, table: str) -> set[str]:
    if backend == "database":
        return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    return {row["column_name"] for row in _execute(connection, backend,
        "SELECT COLUMN_NAME AS column_name FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s", (table,))}


@contextmanager
def _sqlite_query_connection(path: Path, *, readonly: bool) -> Iterator[sqlite3.Connection]:
    """只读连接参与真实读事务；停写窗口仍须事先 checkpoint 未合并日志。

    不使用 immutable：它会绕过锁，不能证明两表来自同一事务快照。WAL 模式下
    SQLite 可能维护共享内存旁文件；零业务写入不等同于文件系统完全零变动。
    """
    if readonly and any(Path(str(path) + suffix).exists() and Path(str(path) + suffix).stat().st_size
                        for suffix in ("-wal", "-journal")):
        raise MigrationError("sqlite_requires_checkpoint")
    connection = sqlite3.connect(path.resolve().as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
                                 uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        if readonly:
            connection.execute("PRAGMA query_only = ON")
            connection.execute("BEGIN")
        yield connection
        if not readonly:
            connection.commit()
    except BaseException:
        if not readonly:
            connection.rollback()
        raise
    finally:
        connection.close()


def _table_report(table: str, identity: str, column: str, version: int, after: str) -> dict[str, Any]:
    return dict(table=table, projection_column=column, projection_version=version,
        schema_missing=[], schema_added=[], scanned_rows=0, processed_rows=0, committed_rows=0,
        mismatches=[], errors=[], has_more=None, status="pending",
        **{"last_successful_" + identity: after, "last_scanned_" + identity: after})


def _scan_table(connection: Any, backend: str, target: tuple, columns: set[str], report: dict[str, Any],
                *, mode: str, batch_size: int, after: str) -> None:
    table, identity, column, _, build_projection = target
    marker = "?" if backend == "database" else "%s"
    key = identity + " COLLATE BINARY" if backend == "database" else f"CAST({identity} AS BINARY)"
    selected = f"{identity}, payload" + (f", {column}" if column in columns else "")
    cursor_id = after if after else None
    while True:
        where = f" WHERE {key} > {marker}" if cursor_id is not None else ""
        params = (cursor_id, batch_size + 1) if cursor_id is not None else (batch_size + 1,)
        rows = _execute(connection, backend,
            f"SELECT {selected} FROM {table}{where} ORDER BY {key} LIMIT {marker}"
            + (" FOR UPDATE" if backend == "mysql" and mode == "apply" else ""), params)
        report["has_more"] = len(rows) > batch_size
        for row in rows[:batch_size]:
            current_id = row[identity]
            report["scanned_rows"] += 1
            report["last_scanned_" + identity] = current_id
            try:
                raw = json.loads(row["payload"])
                if not isinstance(raw, dict):
                    raise MigrationError("invalid_payload_type")
                if raw.get("id") != current_id:
                    raise MigrationError(identity + "_mismatch")
                # 共享入口在模型动态默认值生效前校验稳定时间；保留原始 JSON 读取语义。
                projection = build_projection(row["payload"])
            except (ValueError, MigrationError) as error:
                category = ("missing_time_key" if isinstance(error, DocumentJobListProjectionUnstable)
                    else "invalid_document_file" if isinstance(error, ValidationError) and table == "document_files"
                    else _error_category(error))
                report["errors"].append({identity: current_id, "category": category})
                continue
            stored = row[column] if column in columns else None
            try:
                equal = stored is not None and json.dumps(json.loads(stored), sort_keys=True) == json.dumps(
                    projection, sort_keys=True)
            except (ValueError, TypeError):
                equal = False
            if not equal:
                report["mismatches"].append(current_id)
            if mode == "apply":
                _execute(connection, backend,
                    f"UPDATE {table} SET {column} = {marker} WHERE {key} = {marker}",
                    (json.dumps(projection, ensure_ascii=False), current_id))
            report["processed_rows"] += 1
        if mode == "apply" and report["errors"]:
            raise MigrationError("batch_invalid")
        if mode != "verify" or not report["has_more"]:
            break
        cursor_id = rows[batch_size - 1][identity]
    report["status"] = "scanned" if report["has_more"] else "complete"


def migrate_document_job_list_query(
    settings: Settings, *, mode: str = "dry-run", batch_size: int = 100,
    after_job_id: str = "", after_file_id: str = "", mysql_connect_factory: ConnectFactory | None = None,
) -> dict[str, Any]:
    """dry-run/apply 各表至多一批；先完成 files，再写 jobs，游标只在提交后推进。

    verify 拒绝恢复游标，按 batch_size 分块但在单一事务内从头验证两表全量；只有
    该模式的 all_ready 才能表示事实完整就绪。任一旧写者恢复后须清空两个游标重建。
    """
    backend = settings.jobs_repository_backend
    cursors = {"document_files": after_file_id, "document_jobs": after_job_id}
    reports = {table: _table_report(table, identity, column, version, cursors[table])
               for table, identity, column, version, _ in TABLES}
    report: dict[str, Any] = dict(backend=backend, mode=mode, tables=reports, errors=[],
        verification_scope="full_two_table_snapshot" if mode == "verify" else "table_batches",
        all_ready=False, exit_code=0)
    current_table = None
    try:
        if mode not in {"dry-run", "apply", "verify"} or batch_size < 1:
            raise MigrationError("invalid_arguments")
        if mode == "verify" and (after_job_id or after_file_id):
            raise MigrationError("verify_requires_full_scan")
        if backend not in {"database", "mysql"}:
            raise MigrationError("sql_backend_required")
        mysql_backend = None
        if backend == "mysql":
            mysql_backend = MysqlPersistenceBackend(MysqlPersistenceConfig(
                host=settings.jobs_mysql_host, port=settings.jobs_mysql_port, user=settings.jobs_mysql_user,
                password=settings.jobs_mysql_password, database=settings.jobs_mysql_database,
                charset=settings.jobs_mysql_charset,
                connect_timeout_seconds=settings.jobs_mysql_connect_timeout_seconds,
            ), connect_factory=mysql_connect_factory, initialize=False)

        @contextmanager
        def connect(*, readonly: bool) -> Iterator[Any]:
            if backend == "database":
                with _sqlite_query_connection(settings.jobs_metadata_database_file, readonly=readonly) as connection:
                    yield connection
            else:
                with mysql_backend.connect() as connection:
                    if readonly:
                        _execute(connection, backend, "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                        _execute(connection, backend, "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
                    yield connection

        columns_by_table = {}
        with connect(readonly=mode != "apply") as connection:
            for table, identity, column, _, _ in TABLES:
                current_table = table
                columns = _columns(connection, backend, table)
                if not {identity, "payload", "created_at", "updated_at"}.issubset(columns):
                    raise MigrationError(table + "_schema_missing")
                columns_by_table[table] = columns
                if column not in columns:
                    reports[table]["schema_missing"] = [column]
                    if mode == "apply":
                        definition = "TEXT" if backend == "database" else "LONGTEXT"
                        _execute(connection, backend, f"ALTER TABLE {table} ADD COLUMN {column} {definition} NULL")
                        # 两个 DDL 分别前滚；后续批次失败不能宣称撤销已提交的列。
                        connection.commit()
                        reports[table]["schema_added"] = [column]
                        columns.add(column)
            if mode != "apply":
                for target in TABLES:
                    current_table = target[0]
                    _scan_table(connection, backend, target, columns_by_table[current_table], reports[current_table],
                                mode=mode, batch_size=batch_size, after=cursors[current_table])
        if mode == "apply":
            for target in TABLES:
                current_table, identity = target[:2]
                table_report = reports[current_table]
                with connect(readonly=False) as connection:
                    if backend == "database":
                        _execute(connection, backend, "BEGIN IMMEDIATE")
                    _scan_table(connection, backend, target, columns_by_table[current_table], table_report,
                                mode=mode, batch_size=batch_size, after=cursors[current_table])
                table_report["committed_rows"] = table_report["processed_rows"]
                table_report["last_successful_" + identity] = table_report["last_scanned_" + identity]
                if table_report["has_more"]:
                    break
        current_table = None
    except (Exception, KeyboardInterrupt) as error:
        target_report = reports[current_table] if current_table else report
        if not (isinstance(error, MigrationError) and str(error) == "batch_invalid"):
            identity = "file_id" if current_table == "document_files" else "job_id"
            target_report["errors"].append({identity: target_report.get("last_scanned_" + identity),
                "category": "interrupted" if isinstance(error, KeyboardInterrupt) else _error_category(error)})
        if current_table and mode == "apply":
            target_report["processed_rows"] = 0
            target_report["status"] = "failed"
    failed = bool(report["errors"]) or any(row["errors"] for row in reports.values())
    if mode == "verify":
        report["all_ready"] = not failed and all(row["status"] == "complete" and not row["schema_missing"]
            and not row["mismatches"] for row in reports.values())
        failed = not report["all_ready"]
    report["exit_code"] = int(failed)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", dest="mode", action="store_const", const="dry-run", help="只读检查各表一批（默认）")
    modes.add_argument("--apply", dest="mode", action="store_const", const="apply", help="补两列，按 files→jobs 提交批次")
    modes.add_argument("--verify", dest="mode", action="store_const", const="verify", help="同一快照从头校验两表全量")
    parser.set_defaults(mode="dry-run")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--after-job-id", default="")
    parser.add_argument("--after-file-id", default="")
    parser.add_argument("--backend", choices=("database", "mysql"))
    parser.add_argument("--database-path")
    args = parser.parse_args(argv)
    if args.batch_size < 1:
        parser.error("--batch-size 必须大于 0")
    if args.mode == "verify" and (args.after_job_id or args.after_file_id):
        parser.error("--verify 必须从头校验两表，不能指定恢复游标")
    try:
        settings = Settings(**{key: value for key, value in {
            "jobs_repository_backend": args.backend, "jobs_metadata_database_path": args.database_path,
        }.items() if value is not None})
    except Exception:
        print(json.dumps({"exit_code": 1, "errors": [{"category": "invalid_configuration"}]}))
        return 1
    report = migrate_document_job_list_query(settings, mode=args.mode, batch_size=args.batch_size,
        after_job_id=args.after_job_id, after_file_id=args.after_file_id)
    print(json.dumps(report, ensure_ascii=False))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
