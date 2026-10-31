"""QA-601 专用迁移：停旧 job/review/file metadata 写者后，按游标局部前滚。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import Settings
from app.domains.document_jobs.list_query import DocumentJobListProjectionUnstable, document_job_list_projection_from_raw
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.review import (
    REVIEW_ENVELOPE, ReviewRecord, decode_file_history, legacy_review_import, review_validity,
)
from app.domains.document_jobs.delivery_state import document_job_state_columns
from app.domains.resources.models import utc_now
from app.domains.files.models import DocumentFileRecord
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.infrastructure.persistence.file.document_jobs import FileDocumentJobRepository
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.infrastructure.persistence.sqlite.document_jobs import SqliteDocumentJobRepository
from app.infrastructure.persistence.sqlite.schema import SQLITE_SCHEMA_STATEMENTS
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.document_jobs import MysqlDocumentJobRepository
from app.infrastructure.persistence.mysql.schema import MYSQL_SCHEMA_STATEMENTS
from scripts.ops.migrate_document_job_state import (
    MigrationError, _check_job_id, _file_path, _sqlite_connection, _schema_columns, _error_category,
)


def _execute(connection, backend, query, params=()):
    if backend == "database":
        return connection.execute(query, params).fetchall() if query.lstrip().upper().startswith("SELECT") else connection.execute(query, params)
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall() if query.lstrip().upper().startswith("SELECT") else None


def _has_table(connection, backend):
    if backend == "database":
        return bool(connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                                       ("document_job_review_records",)).fetchall())
    return bool(_execute(connection, backend,
        "SELECT TABLE_NAME AS table_name FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        ("document_job_review_records",)))


def _history(connection, backend, job_id):
    marker = "?" if backend == "database" else "%s"
    rows = _execute(connection, backend,
        f"SELECT payload FROM document_job_review_records WHERE job_id = {marker} AND sequence > {marker} ORDER BY sequence LIMIT {marker}",
        (job_id, 0, 9223372036854775807))
    return [ReviewRecord.model_validate_json(row["payload"]) for row in rows]


def _check_published_source(job, backend, connection, data_path):
    """已发布快照不自动降级；矛盾必须在任何导入写入前停止。"""
    if job.delivery_status != "published":
        return
    file = None
    if job.result_file_id:
        _check_job_id(job.result_file_id)
        if backend == "file":
            root = data_path / "document_files"
            path = root / (job.result_file_id + ".json")
            if root.is_symlink() or path.is_symlink():
                raise MigrationError("unsafe_file_path")
            if path.exists():
                file = DocumentFileRecord.model_validate_json(path.read_text(encoding="utf-8"))
        else:
            marker = "?" if backend == "database" else "%s"
            rows = _execute(connection, backend, f"SELECT payload FROM document_files WHERE file_id = {marker}", (job.result_file_id,))
            if rows:
                file = DocumentFileRecord.model_validate_json(rows[0]["payload"])
    if review_validity(job, file, now=utc_now()) is not None:
        raise MigrationError("published_review_integrity_conflict")


def _commit_import(repository, connection, payload, updated, record, backend):
    repository._insert_review(connection, record)
    # 保留 raw QA、未知键及原始时间编码；仅改变正式引用和必要的批准失效投影。
    fields = ("review_sequence", "current_review_record_id", "current_review_binding", "review_status", "delivery_status")
    dumped = updated.model_dump(mode="json")
    raw = {**payload, **{key: dumped[key] for key in fields}}
    if backend == "file":
        raw[REVIEW_ENVELOPE] = connection[REVIEW_ENVELOPE]
        repository.backend.write_json(repository.backend.document_jobs_dir / updated.id / "job.json", raw)
    else:
        marker = "?" if backend == "database" else "%s"
        serialized = json.dumps(raw, ensure_ascii=False)
        try:
            projection = json.dumps(document_job_list_projection_from_raw(serialized), ensure_ascii=False)
        except DocumentJobListProjectionUnstable:
            # 保留原导入对缺时间 raw 的处理；动态默认值不能冻结成可查询事实。
            projection = None
        _execute(connection, backend,
            f"UPDATE document_jobs SET payload = {marker}, quality_status = {marker}, review_status = {marker}, "
            f"delivery_status = {marker}, quality_summary_json = {marker}, list_query_json = {marker} "
            f"WHERE job_id = {marker}",
            (serialized, *document_job_state_columns(updated), projection, updated.id))


def migrate_document_job_reviews(settings: Settings, *, mode="dry-run", phase="all", batch_size=100,
                                after_job_id="", mysql_connect_factory=None) -> dict[str, Any]:
    """只读模式不构造会 bootstrap 的仓储；apply 每 job 在原锁/事务内重新读取。

    MySQL DDL 可已提交，失败只报告阶段后前滚。导入后回退必须停写并保留历史、引用、
    来源计数及兼容 writer；缺失 file revision=0 仅是监控起点，不构成历史批准证据。
    """
    backend = settings.jobs_repository_backend
    report = {"backend": backend, "mode": mode, "phase": phase, "schema_missing": False,
        "schema_applied": False, "scanned_rows": 0, "imported": 0, "would_import": 0,
        "already_imported": 0, "live_skipped": 0, "last_successful_job_id": "",
        "has_more": False, "errors": [], "exit_code": 0}
    current_id = None
    try:
        if mode not in {"inspect", "dry-run", "verify", "apply"} or phase not in {"schema", "import", "all"} or not 1 <= batch_size <= 10000:
            raise MigrationError("invalid_arguments")
        if after_job_id:
            _check_job_id(after_job_id)
        report["last_successful_job_id"] = after_job_id
        root = settings.data_path / "document_jobs"
        path = settings.jobs_metadata_database_file
        mysql = None
        if backend == "file":
            if root.is_symlink() or not root.is_dir():
                raise MigrationError("target_missing")
        elif backend == "database":
            if not path.is_file():
                raise MigrationError("target_missing")
        elif backend == "mysql":
            mysql = MysqlPersistenceBackend(MysqlPersistenceConfig(host=settings.jobs_mysql_host,
                port=settings.jobs_mysql_port, user=settings.jobs_mysql_user, password=settings.jobs_mysql_password,
                database=settings.jobs_mysql_database, charset=settings.jobs_mysql_charset,
                connect_timeout_seconds=settings.jobs_mysql_connect_timeout_seconds),
                connect_factory=mysql_connect_factory, initialize=False)
        else:
            raise MigrationError("invalid_backend")

        @contextmanager
        def connect(readonly=True):
            if backend == "database":
                with _sqlite_connection(path, readonly=readonly) as connection:
                    yield connection
            else:
                with mysql.connect() as connection:
                    if readonly:
                        _execute(connection, backend, "SET TRANSACTION READ ONLY")
                    yield connection

        has_table = backend == "file"
        if backend != "file":
            with connect(readonly=mode != "apply") as connection:
                columns = _schema_columns(connection, backend)
                if not {"job_id", "payload", "quality_status", "review_status", "delivery_status", "quality_summary_json"}.issubset(columns):
                    raise MigrationError("state_migration_required")
                if mode == "apply" and phase != "schema" and "list_query_json" not in columns:
                    raise MigrationError("list_query_schema_missing")
                has_table = _has_table(connection, backend)
                report["schema_missing"] = not has_table
                if mode == "apply" and phase in {"schema", "all"}:
                    statements = SQLITE_SCHEMA_STATEMENTS if backend == "database" else MYSQL_SCHEMA_STATEMENTS
                    for statement in statements:
                        if "document_job_review_records" in statement:
                            _execute(connection, backend, statement)
                            connection.commit()
                    has_table = True
                    report["schema_applied"] = True
                if mode == "apply" and not has_table:
                    raise MigrationError("review_schema_missing")
        if phase != "schema":
            if backend == "file":
                ids = sorted(p.name for p in root.iterdir() if p.name > after_job_id and (p / "job.json").exists())[:batch_size + 1]
            else:
                marker = "?" if backend == "database" else "%s"
                with connect() as connection:
                    ids = [row["job_id"] for row in _execute(connection, backend,
                        f"SELECT job_id, payload FROM document_jobs WHERE job_id > {marker} ORDER BY job_id LIMIT {marker}",
                        (after_job_id, batch_size + 1))]
            report["has_more"] = len(ids) > batch_size
            repository = None
            for candidate_id in ids[:batch_size]:
                current_id = _check_job_id(candidate_id)
                report["scanned_rows"] += 1
                if backend == "file":
                    _file_path(root, current_id)
                if mode == "apply":
                    if repository is None:
                        if backend == "file":
                            repository = FileDocumentJobRepository(FilePersistenceBackend(settings.data_path))
                        elif backend == "database":
                            repository = SqliteDocumentJobRepository(SqlitePersistenceBackend(path, initialize=False))
                        else:
                            repository = MysqlDocumentJobRepository(mysql)
                    with repository._locked_payload(current_id) as (connection, payload):
                        records = decode_file_history(payload) if backend == "file" else _history(connection, backend, current_id)
                        job = DocumentJobRecord.model_validate(payload)
                        if job.id != current_id:
                            raise MigrationError("job_id_mismatch")
                        _check_published_source(job, backend, connection, settings.data_path)
                        updated, record, outcome = legacy_review_import(job, payload, records, now=utc_now())
                        if record is not None:
                            _commit_import(repository, connection, payload, updated, record, backend)
                    # 只统计已正常退出提交边界的对象；失败游标由确定 import ID 安全恢复。
                    report["imported" if record is not None else outcome] += 1
                else:
                    if backend == "file":
                        payload = json.loads(_file_path(root, current_id).read_text(encoding="utf-8"))
                        records = decode_file_history(payload)
                    else:
                        marker = "?" if backend == "database" else "%s"
                        with connect() as connection:
                            rows = _execute(connection, backend, f"SELECT payload FROM document_jobs WHERE job_id = {marker}", (current_id,))
                            payload = json.loads(rows[0]["payload"])
                            records = _history(connection, backend, current_id) if has_table else []
                            _check_published_source(DocumentJobRecord.model_validate(payload), backend, connection, settings.data_path)
                    job = DocumentJobRecord.model_validate(payload)
                    if job.id != current_id:
                        raise MigrationError("job_id_mismatch")
                    if backend == "file":
                        _check_published_source(job, backend, None, settings.data_path)
                    _, record, outcome = legacy_review_import(job, payload, records, now=utc_now())
                    report["would_import" if record is not None else outcome] += 1
                report["last_successful_job_id"] = current_id
                current_id = None
    except KeyboardInterrupt:
        report["errors"].append({"job_id": current_id, "category": "interrupted"})
    except Exception as exc:
        # ValueError 可能含备注/底层路径，仅输出固定类别。
        category = "review_integrity_conflict" if isinstance(exc, ValueError) and not isinstance(exc, MigrationError) else _error_category(exc)
        report["errors"].append({"job_id": current_id, "category": category})
    if report["errors"] or (mode == "verify" and (report["would_import"] or report["schema_missing"] or report["has_more"])):
        report["exit_code"] = 1
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="QA-601 专用迁移；先停旧 job/review/generated_word metadata 写者并备份。回退保留历史与来源序号，禁止 DROP 或恢复旧批准。")
    modes = parser.add_mutually_exclusive_group()
    for name in ("inspect", "dry-run", "verify", "apply"):
        modes.add_argument("--" + name, dest="mode", action="store_const", const=name)
    parser.set_defaults(mode="dry-run")
    parser.add_argument("--phase", choices=("schema", "import", "all"), default="all")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--after-job-id", default="")
    parser.add_argument("--backend", choices=("file", "database", "mysql"))
    parser.add_argument("--data-dir")
    parser.add_argument("--database-path")
    args = parser.parse_args(argv)
    overrides = {key: val for key, val in {"jobs_repository_backend": args.backend, "data_dir": args.data_dir,
                 "jobs_metadata_database_path": args.database_path}.items() if val is not None}
    try:
        settings = Settings(**overrides)
    except Exception:
        print(json.dumps({"exit_code": 1, "errors": [{"category": "invalid_configuration"}]}))
        return 1
    report = migrate_document_job_reviews(settings, mode=args.mode, phase=args.phase, batch_size=args.batch_size,
                                         after_job_id=args.after_job_id)
    print(json.dumps(report, ensure_ascii=False))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
