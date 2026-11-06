"""双表回填的真实 SQLite 事务、恢复游标和原始数据保真合同。"""
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.config import Settings
from app.domains.document_jobs.list_query import (
    DocumentJobListProjectionUnavailable, DocumentJobListQuery, document_job_list_storage_from_raw,
)
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.infrastructure.persistence.sqlite.document_jobs import SqliteDocumentJobRepository
from scripts.ops import migrate_document_job_list_query as migration
from scripts.ops.migrate_document_job_reviews import migrate_document_job_reviews
from scripts.ops.migrate_document_job_state import migrate_document_job_state
from tests.test_document_job_delivery_state_migration import _legacy, _settings


def _file(file_id="word", *, file_type="generated_word"):
    raw = deepcopy(_legacy()["prepared_result"]["file"])
    raw.update(id=file_id, file_type=file_type, unknown_raw={"保留": [1, True]})
    return raw


def _old_database(path, jobs, files):
    with sqlite3.connect(path) as connection:
        for table, identity, records in (("document_jobs", "job_id", jobs), ("document_files", "file_id", files)):
            connection.execute(f"CREATE TABLE {table} ({identity} TEXT PRIMARY KEY, payload TEXT NOT NULL, "
                "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, unknown_column TEXT)")
            for key, raw in records.items():
                payload = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False, indent=2)
                connection.execute(f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?)",
                    (key, payload, "原始列创建时间", "原始列更新时间", "原始额外列"))
        connection.execute("CREATE TABLE unrelated_audit (payload TEXT)")
        connection.execute("INSERT INTO unrelated_audit VALUES ('原有审计')")
        connection.execute("CREATE TABLE job_events (event_id TEXT PRIMARY KEY, payload TEXT)")
        connection.execute("INSERT INTO job_events VALUES ('event-before', '原有事件')")
        for table in ("job_events", "unrelated_audit"):
            for operation in ("INSERT", "UPDATE", "DELETE"):
                connection.execute(f"CREATE TRIGGER protect_{table}_{operation} BEFORE {operation} ON {table} "
                                   "BEGIN SELECT RAISE(ABORT, '迁移不得写其他表'); END")


class DocumentJobListQueryMigrationTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "metadata.sqlite3"
        self.settings = _settings(self.root, "database")

    def migrate(self, **kwargs):
        return migration.migrate_document_job_list_query(self.settings, **kwargs)

    def rows(self, table):
        order = " ORDER BY file_id" if table == "document_files" else " ORDER BY job_id" if table == "document_jobs" else ""
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(f"SELECT * FROM {table}{order}")]

    def test_default_dry_run_reports_both_versions_and_missing_schema_without_writes(self):
        _old_database(self.path, {"job-a": _legacy()}, {"word": _file()})
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        report = self.migrate()
        self.assertEqual(report["exit_code"], 0)
        self.assertFalse(report["all_ready"])
        self.assertNotIn("last_successful_job_id", report)
        for table, identity, column, version in (("document_files", "file_id", "review_query_json", 2),
                ("document_jobs", "job_id", "list_query_json", 3)):
            row = report["tables"][table]
            self.assertEqual((row["projection_version"], row["schema_missing"], row["committed_rows"]),
                             (version, list(next(target[2] for target in migration.TABLES if target[0] == table)), 0))
            self.assertEqual(row["last_successful_" + identity], "")
            self.assertEqual(row["scanned_rows"], 1)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})
        self.assertFalse(self.migrate(mode="verify")["all_ready"])

    def test_preflight_reports_both_tables_and_checks_identity_before_models(self):
        missing = _legacy("job-b")
        missing["prepared_result"]["file"].pop("updated_at")
        _old_database(self.path, {"job-a": '{bad', "job-b": missing, "job-c": _legacy("other")},
            {"a": _file("wrong"), "b": {**_file("b"), "file_type": "invalid"}})
        report = self.migrate()
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["tables"]["document_jobs"]["errors"], [
            {"job_id": "job-a", "category": "invalid_json"},
            {"job_id": "job-b", "category": "missing_time_key"},
            {"job_id": "job-c", "category": "job_id_mismatch"}])
        self.assertEqual(report["tables"]["document_files"]["errors"], [
            {"file_id": "a", "category": "file_id_mismatch"},
            {"file_id": "b", "category": "invalid_document_file"}])

    def test_raw_time_applicability_does_not_freeze_dynamic_defaults(self):
        for field, nested in (("created_at", False), ("updated_at", False),
                              ("created_at", True), ("updated_at", True)):
            with self.subTest(field=field, nested=nested), TemporaryDirectory() as directory:
                path = Path(directory) / "metadata.sqlite3"
                raw = _legacy()
                (raw["prepared_result"]["file"] if nested else raw).pop(field)
                _old_database(path, {"job-a": raw}, {})
                report = migration.migrate_document_job_list_query(_settings(Path(directory), "database"))
                self.assertEqual(report["tables"]["document_jobs"]["errors"],
                    [{"job_id": "job-a", "category": "missing_time_key"}])
        bad = _file("bad"); bad.pop("created_at")
        updated_missing = _file("allowed-word"); updated_missing.pop("updated_at")
        source = _file("source", file_type="source_pdf")
        source.pop("created_at"); source.pop("updated_at")
        _old_database(self.path, {}, {"bad": bad, "allowed-word": updated_missing, "source": source})
        report = self.migrate()
        self.assertEqual(report["tables"]["document_files"]["errors"],
                         [{"file_id": "bad", "category": "missing_time_key"}])
        with sqlite3.connect(self.path) as connection:
            connection.execute("DELETE FROM document_files WHERE file_id = 'bad'")
        self.assertEqual(self.migrate(mode="apply")["exit_code"], 0)
        for row in self.rows("document_files"):
            stored = json.loads(row["payload"])
            self.assertNotIn("updated_at", stored)
            if row["file_id"] == "source":
                self.assertNotIn("created_at", stored)
                projection = json.loads(row["review_query_json"])
                self.assertEqual(projection["file_type"], "source_pdf")
        self.assertTrue(self.migrate(mode="verify")["all_ready"])

    def test_files_finish_before_jobs_and_each_committed_cursor_is_independent(self):
        _old_database(self.path, {"job-a": _legacy(), "job-b": _legacy("job-b")},
                      {"file-a": _file("file-a"), "file-b": _file("file-b")})
        before = {table: self.rows(table) for table in ("document_jobs", "document_files", "unrelated_audit")}
        first = self.migrate(mode="apply", batch_size=1)
        files, jobs = first["tables"]["document_files"], first["tables"]["document_jobs"]
        self.assertEqual((files["last_successful_file_id"], files["committed_rows"], files["has_more"]), ("file-a", 1, True))
        self.assertEqual((jobs["status"], jobs["last_successful_job_id"], jobs["committed_rows"]), ("pending", "", 0))
        second = self.migrate(mode="apply", batch_size=1, after_file_id=files["last_successful_file_id"])
        self.assertEqual(second["tables"]["document_files"]["last_successful_file_id"], "file-b")
        self.assertEqual(second["tables"]["document_jobs"]["last_successful_job_id"], "job-a")
        third = self.migrate(mode="apply", batch_size=1, after_file_id="file-b", after_job_id="job-a")
        self.assertEqual(third["tables"]["document_jobs"]["last_successful_job_id"], "job-b")
        self.assertTrue(self.migrate(mode="verify", batch_size=1)["all_ready"])
        for table in ("document_jobs", "document_files"):
            for old, new in zip(before[table], self.rows(table), strict=True):
                self.assertEqual({key: new[key] for key in old}, old)
                if table == "document_jobs":
                    projection = json.loads(new["list_query_json"])
                    self.assertEqual(projection, json.loads(document_job_list_storage_from_raw(old["payload"])[0]))
                    self.assertEqual((projection["version"], projection["review_status"]), (3, "unreviewed"))
        self.assertEqual(before["unrelated_audit"], self.rows("unrelated_audit"))

    def test_dry_run_preserves_database_bytes_and_reports_missing_time_and_bad_payload(self):
        missing = _legacy("job-b"); missing.pop("created_at")
        _old_database(self.path, {"job-a": _legacy(), "job-b": missing, "job-c": '{bad'}, {})
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        report = self.migrate()
        jobs = report["tables"]["document_jobs"]
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(jobs["schema_missing"], list(migration.TABLES[1][2]))
        self.assertEqual(jobs["errors"], [{"job_id": "job-b", "category": "missing_time_key"},
                                          {"job_id": "job-c", "category": "invalid_json"}])
        self.assertEqual(jobs["last_successful_job_id"], "")
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})

    def test_storage_failure_after_first_update_does_not_advance_cursor(self):
        _old_database(self.path, {"job-a": _legacy(), "job-b": _legacy("job-b")}, {})
        with sqlite3.connect(self.path) as connection:
            connection.execute("ALTER TABLE document_jobs ADD COLUMN list_query_json TEXT")
            connection.execute("CREATE TRIGGER fail_projection BEFORE UPDATE ON document_jobs "
                               "WHEN new.job_id = 'job-b' BEGIN SELECT RAISE(ABORT, '模拟存储失败'); END")
        report = self.migrate(mode="apply")
        jobs = report["tables"]["document_jobs"]
        self.assertEqual(jobs["errors"], [{"job_id": "job-b", "category": "storage_error"}])
        self.assertEqual((jobs["committed_rows"], jobs["last_successful_job_id"]), (0, ""))
        self.assertTrue(all(row["list_query_json"] is None for row in self.rows("document_jobs")))
        with sqlite3.connect(self.path) as connection:
            connection.execute("DROP TRIGGER fail_projection")
        self.assertEqual(self.migrate(mode="apply")["tables"]["document_jobs"]["committed_rows"], 2)

    def test_invalid_job_batch_rolls_back_all_projection_writes_and_keeps_cursor(self):
        invalid = _legacy("job-b"); invalid.pop("updated_at")
        _old_database(self.path, {"job-a": _legacy(), "job-b": invalid}, {})
        report = self.migrate(mode="apply")
        jobs = report["tables"]["document_jobs"]
        self.assertEqual((report["exit_code"], jobs["processed_rows"], jobs["last_successful_job_id"]), (1, 0, ""))
        self.assertTrue(all(row["list_query_json"] is None for row in self.rows("document_jobs")))
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE document_jobs SET payload = ? WHERE job_id = 'job-b'", (json.dumps(_legacy("job-b")),))
        self.assertEqual(self.migrate(mode="apply")["tables"]["document_jobs"]["committed_rows"], 2)

    def test_state_migration_preserves_missing_times_and_leaves_projection_unavailable(self):
        from tests.test_document_job_delivery_state_migration import _MigrationMysqlDatabase
        missing = _legacy(); missing.pop("created_at")
        _old_database(self.path, {"job-a": missing}, {})
        report = migrate_document_job_state(self.settings, mode="apply")
        self.assertEqual(report["exit_code"], 0, report)
        row = self.rows("document_jobs")[0]
        self.assertNotIn("created_at", json.loads(row["payload"]))
        self.assertTrue(all(row[name] is None for name in migration.TABLES[1][2]))
        repository = SqliteDocumentJobRepository(SqlitePersistenceBackend(self.path, initialize=False))
        with self.assertRaises(DocumentJobListProjectionUnavailable):
            repository.query_document_jobs(DocumentJobListQuery("tenant", "company"))
        self.assertEqual(self.migrate()["tables"]["document_jobs"]["errors"],
                         [{"job_id": "job-a", "category": "missing_time_key"}])
        database = _MigrationMysqlDatabase({"job-a": missing})
        report = migrate_document_job_state(Settings(_env_file=None, jobs_repository_backend="mysql"),
                                             mode="apply", mysql_connect_factory=database.connect)
        self.assertEqual(report["exit_code"], 0, report)
        self.assertTrue(all(database.document_jobs["job-a"][name] is None for name in migration.TABLES[1][2]))
        self.assertNotIn("created_at", json.loads(database.document_jobs["job-a"]["payload"]))

    def test_mysql_migration_binds_both_projections_and_locks_batches_without_rewriting_payloads(self):
        from tests.test_document_job_delivery_state_migration import (
            _MigrationMysqlDatabase, _MigrationMysqlConnection, _MigrationMysqlCursor,
        )
        statements = []
        class Cursor(_MigrationMysqlCursor):
            def execute(cursor, sql, params=()):
                statements.append((sql, params))
                if sql.startswith(("SET TRANSACTION ", "START TRANSACTION ")):
                    cursor._rows = []
                    return
                if sql.startswith(("SELECT job_id, payload", "SELECT file_id, payload")):
                    table = sql.split(" FROM ", 1)[1].split()[0]
                    after, limit = params if len(params) == 2 else (None, params[0])
                    cursor._rows = [deepcopy(row) for key, row in sorted(getattr(cursor.database, table).items())
                                    if after is None or key > after][:limit]
                    return
                if sql.startswith(("ALTER TABLE document_files ADD COLUMN", "ALTER TABLE document_jobs ADD COLUMN")):
                    table, column = sql.split()[2], sql.split()[5]
                    cursor.database.table_columns[table].add(column)
                    for row in getattr(cursor.database, table).values():
                        row[column] = None
                    cursor._rows = []
                    return
                if sql.startswith(("UPDATE document_jobs SET list_query_json", "UPDATE document_files SET review_query_json")):
                    table = sql.split()[1]
                    assignments = sql.split(" SET ")[1].split(" WHERE ")[0].split(", ")
                    for assignment, value in zip(assignments, params[:-1], strict=True):
                        getattr(cursor.database, table)[params[-1]][assignment.split()[0]] = value
                    cursor._rows = []
                    return
                return super().execute(sql, params)
        class Connection(_MigrationMysqlConnection):
            def cursor(connection):
                return Cursor(connection.database)
        database = _MigrationMysqlDatabase({"job-a": _legacy()})
        database.table_columns["document_files"] = {"file_id", "payload", "created_at", "updated_at"}
        database.document_files["word"] = dict(file_id="word", payload=json.dumps(_file()), created_at="原创建", updated_at="原更新")
        before = {table: deepcopy(getattr(database, table)) for table in ("document_files", "document_jobs")}
        settings = Settings(_env_file=None, jobs_repository_backend="mysql")
        connect = lambda: Connection(database)
        dry = migration.migrate_document_job_list_query(settings, mysql_connect_factory=connect)
        self.assertEqual(dry["exit_code"], 0, dry)
        self.assertFalse(any(sql.startswith(("ALTER", "UPDATE")) for sql, _ in statements))
        statements.clear()
        applied = migration.migrate_document_job_list_query(settings, mode="apply", after_job_id="-", after_file_id="-", mysql_connect_factory=connect)
        self.assertEqual(applied["exit_code"], 0, applied)
        for table, identity, column, version in (("document_files", "file_id", "review_query_json", 2),
                ("document_jobs", "job_id", "list_query_json", 3)):
            stored = next(iter(getattr(database, table).values()))
            original = next(iter(before[table].values()))
            self.assertEqual({key: stored[key] for key in original}, original)
            self.assertEqual(json.loads(stored[column])["version"], version)
            select = next(sql for sql, _ in statements if sql.startswith("SELECT " + identity))
            self.assertIn(f"CAST({identity} AS BINARY) > %s", select)
            self.assertTrue(select.endswith("FOR UPDATE"))
            update, values = next((sql, params) for sql, params in statements if sql.startswith(f"UPDATE {table}"))
            columns = next(target[2] for target in migration.TABLES if target[0] == table)
            assignments = ", ".join(f"{name} = %s" for name in columns)
            self.assertEqual(update, f"UPDATE {table} SET {assignments} WHERE CAST({identity} AS BINARY) = %s")
            self.assertEqual(values[-1], stored[identity])
        statements.clear()
        verified = migration.migrate_document_job_list_query(settings, mode="verify", mysql_connect_factory=connect)
        self.assertTrue(verified["all_ready"], verified)
        self.assertEqual(sum(sql == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ" for sql, _ in statements), 1)
        self.assertEqual(sum(sql == "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY" for sql, _ in statements), 1)

    def test_bad_file_batch_rolls_back_all_data_but_keeps_explicit_schema_front_roll(self):
        bad = _file("file-b"); bad.pop("created_at")
        _old_database(self.path, {"job-a": _legacy()}, {"file-a": _file("file-a"), "file-b": bad})
        report = self.migrate(mode="apply")
        files = report["tables"]["document_files"]
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual((files["processed_rows"], files["committed_rows"], files["last_successful_file_id"]), (0, 0, ""))
        self.assertEqual(files["schema_added"], list(migration.TABLES[0][2]))
        self.assertTrue(all(row["review_query_json"] is None for row in self.rows("document_files")))
        self.assertIsNone(self.rows("document_jobs")[0]["list_query_json"])
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE document_files SET payload = ? WHERE file_id = 'file-b'", (json.dumps(_file("file-b")),))
        self.assertEqual(self.migrate(mode="apply")["tables"]["document_files"]["committed_rows"], 2)
        self.assertTrue(self.migrate(mode="verify")["all_ready"])

    def test_second_ddl_failure_reports_first_column_as_already_committed(self):
        _old_database(self.path, {"job-a": _legacy()}, {"word": _file()})
        execute = migration._execute
        def fail_second(connection, backend, statement, params=()):
            if statement.startswith("ALTER TABLE document_jobs"):
                raise sqlite3.OperationalError("模拟第二个 DDL 失败")
            return execute(connection, backend, statement, params)
        with patch.object(migration, "_execute", side_effect=fail_second):
            report = self.migrate(mode="apply")
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["tables"]["document_files"]["schema_added"], list(migration.TABLES[0][2]))
        self.assertEqual(report["tables"]["document_jobs"]["schema_added"], [])
        self.assertIsNone(self.rows("document_files")[0]["review_query_json"])
        self.assertNotIn("list_query_json", self.rows("document_jobs")[0])
        self.assertEqual(self.migrate(mode="apply")["exit_code"], 0)

    def test_interrupt_rolls_back_current_file_batch_without_advancing_committed_cursor(self):
        _old_database(self.path, {"job-a": _legacy()}, {"file-a": _file("file-a"), "file-b": _file("file-b")})
        execute = migration._execute
        def interrupt_second(connection, backend, statement, params=()):
            if statement.startswith("UPDATE document_files") and params[-1] == "file-b":
                raise KeyboardInterrupt
            return execute(connection, backend, statement, params)
        with patch.object(migration, "_execute", side_effect=interrupt_second):
            report = self.migrate(mode="apply")
        files = report["tables"]["document_files"]
        self.assertEqual((report["exit_code"], files["last_successful_file_id"], files["committed_rows"]), (1, "", 0))
        self.assertEqual(files["errors"], [{"file_id": "file-b", "category": "interrupted"}])
        self.assertTrue(all(row["review_query_json"] is None for row in self.rows("document_files")))

    def test_failed_job_batch_does_not_undo_committed_files_or_advance_job_cursor(self):
        _old_database(self.path, {"job-a": _legacy(), "job-b": _legacy("job-b")}, {"word": _file()})
        with sqlite3.connect(self.path) as connection:
            connection.execute("CREATE TRIGGER fail_job BEFORE UPDATE ON document_jobs WHEN new.job_id = 'job-b' "
                               "BEGIN SELECT RAISE(ABORT, '仅测试原始异常不得输出'); END")
        report = self.migrate(mode="apply")
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["tables"]["document_files"]["committed_rows"], 1)
        self.assertEqual(report["tables"]["document_jobs"]["committed_rows"], 0)
        self.assertEqual(report["tables"]["document_jobs"]["last_successful_job_id"], "")
        self.assertTrue(all(row["list_query_json"] is None for row in self.rows("document_jobs")))
        self.assertNotIn("仅测试", json.dumps(report))
        with sqlite3.connect(self.path) as connection:
            connection.execute("DROP TRIGGER fail_job")
        self.assertEqual(self.migrate(mode="apply", after_file_id="word")["tables"]["document_jobs"]["committed_rows"], 2)

    def test_verify_rejects_cursors_and_reads_all_batches_in_one_two_table_snapshot(self):
        _old_database(self.path, {"job-a": _legacy(), "job-b": _legacy("job-b")},
                      {"file-a": _file("file-a"), "file-b": _file("file-b")})
        self.assertEqual(self.migrate(mode="apply")["exit_code"], 0)
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE document_jobs SET list_query_json = '{\"version\":1}' WHERE job_id = 'job-a'")
            connection.execute("UPDATE document_files SET review_query_json = NULL WHERE file_id = 'file-a'")
        report = self.migrate(mode="verify", batch_size=1)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["tables"]["document_jobs"]["mismatches"], ["job-a"])
        self.assertEqual(report["tables"]["document_files"]["mismatches"], ["file-a"])
        self.assertEqual(report["tables"]["document_jobs"]["scanned_rows"], 2)
        self.assertEqual(report["tables"]["document_files"]["scanned_rows"], 2)
        self.assertEqual(report["verification_scope"], "full_two_table_snapshot")
        for cursor in ({"after_job_id": "job-a"}, {"after_file_id": "file-a"}):
            self.assertEqual(self.migrate(mode="verify", **cursor)["errors"][0]["category"], "verify_requires_full_scan")

    def test_verify_snapshot_excludes_midscan_commits_in_both_tables(self):
        _old_database(self.path, {"job-a": _legacy()}, {"word": _file()})
        self.assertEqual(self.migrate(mode="apply")["exit_code"], 0)
        keeper = sqlite3.connect(self.path)
        self.addCleanup(keeper.close)
        keeper.execute("PRAGMA journal_mode = WAL")
        keeper.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        original_scan = migration._scan_table
        seen_connections = []
        def scan(connection, backend, target, *args, **kwargs):
            seen_connections.append(id(connection))
            result = original_scan(connection, backend, target, *args, **kwargs)
            if target[0] == "document_files":
                with sqlite3.connect(self.path) as writer:
                    job = _legacy(); job["error_message"] = "另一连接已提交"
                    file = _file(); file["metadata"] = {"另一连接": "已提交"}
                    writer.execute("UPDATE document_jobs SET payload = ?", (json.dumps(job),))
                    writer.execute("UPDATE document_files SET payload = ?", (json.dumps(file),))
            return result
        with patch.object(migration, "_scan_table", side_effect=scan):
            report = self.migrate(mode="verify", batch_size=1)
        self.assertTrue(report["all_ready"], report)
        self.assertEqual(len(set(seen_connections)), 1)
        keeper.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        later = self.migrate(mode="verify")
        self.assertEqual(later["tables"]["document_jobs"]["mismatches"], ["job-a"])
        self.assertEqual(later["tables"]["document_files"]["mismatches"], ["word"])

    def test_either_legacy_writer_requires_full_rebuild_of_both_nonnull_projections(self):
        _old_database(self.path, {"job-a": _legacy()}, {"word": _file()})
        self.assertEqual(self.migrate(mode="apply")["exit_code"], 0)
        with sqlite3.connect(self.path) as connection:
            job = _legacy(); job["error_message"] = "旧 job writer"
            file = _file(); file["deletion_claim"] = "旧 file writer"
            connection.execute("UPDATE document_jobs SET payload = ?", (json.dumps(job),))
            connection.execute("UPDATE document_files SET payload = ?", (json.dumps(file),))
        self.assertFalse(self.migrate(mode="verify")["all_ready"])
        resumed = self.migrate(mode="apply", after_job_id="job-a", after_file_id="word")
        self.assertFalse(resumed["all_ready"])
        self.assertFalse(self.migrate(mode="verify")["all_ready"])
        self.assertEqual(self.migrate(mode="apply")["exit_code"], 0)
        self.assertTrue(self.migrate(mode="verify")["all_ready"])

    def test_review_import_bypass_refreshes_projection_with_history_in_same_transaction(self):
        SqlitePersistenceBackend(self.path)
        raw = _legacy(); raw.update(review_status="approved", delivery_status="internal_draft")
        serialized = json.dumps(raw, ensure_ascii=False, indent=2)
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO document_jobs (job_id, payload, created_at, updated_at, list_query_json) "
                "VALUES (?, ?, ?, ?, ?)", ("job-a", serialized, "原创建列", "原更新列", '{"version":1}'))
        report = migrate_document_job_reviews(self.settings, mode="apply")
        self.assertEqual((report["exit_code"], report["imported"]), (0, 1), report)
        row = self.rows("document_jobs")[0]
        after = json.loads(row["payload"])
        changed = {"review_sequence", "current_review_record_id", "current_review_binding", "review_status", "delivery_status"}
        self.assertEqual({key: value for key, value in after.items() if key not in changed},
                         {key: value for key, value in raw.items() if key not in changed})
        self.assertEqual((row["created_at"], row["updated_at"]), ("原创建列", "原更新列"))
        self.assertEqual(tuple(row[name] for name in migration.TABLES[1][2]),
                         document_job_list_storage_from_raw(row["payload"]))
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM document_job_review_records").fetchone()[0], 1)
        self.assertEqual(migrate_document_job_reviews(self.settings, mode="apply")["already_imported"], 1)

    def test_review_import_failure_rolls_back_history_payload_and_projection(self):
        SqlitePersistenceBackend(self.path)
        serialized = json.dumps(_legacy())
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO document_jobs (job_id, payload, created_at, updated_at, list_query_json) "
                "VALUES ('job-a', ?, 'created', 'updated', 'original')", (serialized,))
            connection.execute("UPDATE document_jobs SET list_descriptor_key = 'old-descriptor', "
                               "list_receipt_key = 'old-receipt', list_table_snapshot_key = 'old-table'")
            connection.execute("CREATE TRIGGER fail_import BEFORE UPDATE ON document_jobs "
                               "BEGIN SELECT RAISE(ABORT, '导入失败'); END")
        report = migrate_document_job_reviews(self.settings, mode="apply")
        self.assertEqual((report["exit_code"], report["imported"]), (1, 0))
        row = self.rows("document_jobs")[0]
        self.assertEqual((row["payload"], *(row[name] for name in migration.TABLES[1][2])),
                         (serialized, "original", "old-descriptor", "old-receipt", "old-table"))
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM document_job_review_records").fetchone()[0], 0)

    def test_review_import_requires_query_column_before_creating_history_or_writing_jobs(self):
        _old_database(self.path, {"job-a": _legacy()}, {})
        with sqlite3.connect(self.path) as connection:
            for definition in ("quality_status TEXT", "review_status TEXT", "delivery_status TEXT", "quality_summary_json TEXT"):
                connection.execute("ALTER TABLE document_jobs ADD COLUMN " + definition)
        before = self.rows("document_jobs")
        report = migrate_document_job_reviews(self.settings, mode="apply")
        self.assertEqual(report["errors"][0]["category"], "list_query_schema_missing")
        self.assertEqual(before, self.rows("document_jobs"))
        with sqlite3.connect(self.path) as connection:
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name = 'document_job_review_records'").fetchone())

    def test_review_import_keeps_missing_raw_time_and_unavailable_projection(self):
        SqlitePersistenceBackend(self.path)
        raw = _legacy(); raw.pop("created_at")
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO document_jobs (job_id, payload, created_at, updated_at, list_query_json) "
                "VALUES ('job-a', ?, 'created', 'updated', 'stale')", (json.dumps(raw),))
            connection.execute("UPDATE document_jobs SET list_descriptor_key = 'stale', "
                               "list_receipt_key = 'stale', list_table_snapshot_key = 'stale'")
        report = migrate_document_job_reviews(self.settings, mode="apply")
        self.assertEqual(report["exit_code"], 0, report)
        row = self.rows("document_jobs")[0]
        self.assertNotIn("created_at", json.loads(row["payload"]))
        self.assertTrue(all(row[name] is None for name in migration.TABLES[1][2]))

    def test_cli_default_and_explicit_file_cursor_do_not_create_missing_database(self):
        output = StringIO()
        with redirect_stdout(output):
            code = migration.main(["--backend", "database", "--database-path", str(self.path), "--after-file-id", "word"])
        self.assertEqual(code, 1)
        self.assertFalse(self.path.exists())
        self.assertEqual(json.loads(output.getvalue())["mode"], "dry-run")

    def test_partial_key_ddl_failure_resumes_only_missing_columns(self):
        _old_database(self.path, {"job-a": _legacy()}, {"word": _file()})
        execute = migration._execute
        def fail_key(connection, backend, statement, params=()):
            if statement.startswith("ALTER TABLE document_files ADD COLUMN review_receipt_key"):
                raise sqlite3.OperationalError("模拟第三列 DDL 失败")
            return execute(connection, backend, statement, params)
        with patch.object(migration, "_execute", side_effect=fail_key):
            failed = self.migrate(mode="apply")
        files = failed["tables"]["document_files"]
        self.assertEqual(failed["exit_code"], 1)
        self.assertEqual(files["schema_added"], ["review_query_json", "review_descriptor_key"])
        self.assertEqual(files["last_successful_file_id"], "")
        self.assertNotIn("review_receipt_key", self.rows("document_files")[0])
        resumed = self.migrate(mode="apply")
        self.assertEqual(resumed["tables"]["document_files"]["schema_added"], ["review_receipt_key"])
        self.assertTrue(self.migrate(mode="verify")["all_ready"])

    def test_verify_detects_each_key_with_current_json_and_reapply_repairs_only_changed_row(self):
        _old_database(self.path, {"job-a": _legacy()}, {"word": _file()})
        self.assertEqual(self.migrate(mode="apply")["exit_code"], 0)
        for table, identity, columns, _, _ in migration.TABLES:
            for column in columns[1:]:
                for stale in (None, "陈旧规范文本"):
                    with self.subTest(table=table, column=column, stale=stale):
                        with sqlite3.connect(self.path) as connection:
                            connection.execute(f"UPDATE {table} SET {column} = ?", (stale,))
                        before = self.path.read_bytes()
                        report = self.migrate(mode="verify", batch_size=1)
                        self.assertEqual(report["exit_code"], 1)
                        expected_id = "word" if identity == "file_id" else "job-a"
                        self.assertEqual(report["tables"][table]["mismatches"], [expected_id])
                        self.assertEqual(before, self.path.read_bytes())
                        with patch.object(migration, "_execute", wraps=migration._execute) as execute:
                            fixed = self.migrate(mode="apply")
                        self.assertEqual(fixed["exit_code"], 0)
                        updates = [call.args[2] for call in execute.call_args_list if call.args[2].startswith("UPDATE ")]
                        self.assertEqual(len(updates), 1)
                        self.assertTrue(updates[0].startswith(f"UPDATE {table} "))
        self.assertTrue(self.migrate(mode="verify")["all_ready"])

    def test_idempotent_apply_issues_no_dml_and_preserves_other_tables(self):
        _old_database(self.path, {"job-a": _legacy()}, {"word": _file()})
        protected = {name: self.rows(name) for name in ("job_events", "unrelated_audit")}
        self.assertEqual(self.migrate(mode="apply")["exit_code"], 0)
        before = self.path.read_bytes()
        with patch.object(migration, "_execute", wraps=migration._execute) as execute:
            report = self.migrate(mode="apply")
        self.assertEqual(report["exit_code"], 0)
        self.assertFalse(any(call.args[2].startswith(("ALTER ", "UPDATE ", "INSERT ", "DELETE "))
                             for call in execute.call_args_list))
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(protected, {name: self.rows(name) for name in protected})

    def test_review_import_requires_keys_even_with_query_json_before_any_write(self):
        _old_database(self.path, {"job-a": _legacy()}, {})
        with sqlite3.connect(self.path) as connection:
            for definition in ("quality_status TEXT", "review_status TEXT", "delivery_status TEXT", "quality_summary_json TEXT",
                               "list_query_json TEXT", "list_descriptor_key TEXT", "list_receipt_key TEXT"):
                connection.execute("ALTER TABLE document_jobs ADD COLUMN " + definition)
        before = self.path.read_bytes()
        report = migrate_document_job_reviews(self.settings, mode="apply")
        self.assertEqual(report["errors"][0]["category"], "list_query_schema_missing")
        self.assertEqual(before, self.path.read_bytes())

    def test_independent_cli_reuses_migration_and_disables_dotenv(self):
        from scripts.ops import migrate_document_job_list_keys as keys
        self.assertIs(keys.migrate_document_job_list_keys, migration.migrate_document_job_list_query)
        _old_database(self.path, {"job-a": _legacy()}, {"word": _file()})
        output = StringIO()
        with patch.object(migration, "Settings", wraps=Settings) as settings, redirect_stdout(output):
            code = keys.main(["--backend", "database", "--database-path", str(self.path)])
        self.assertEqual(code, 0)
        self.assertIsNone(settings.call_args.kwargs["_env_file"])
        self.assertEqual(json.loads(output.getvalue())["mode"], "dry-run")
        for args in ([], ["--backend", "database"], ["--backend", "mysql"]):
            with self.subTest(args=args), patch.dict(os.environ, {}, clear=True), redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as error:
                    keys.main(args)
                self.assertEqual(error.exception.code, 2)


    def test_independent_script_dry_run_is_readonly_without_pythonpath(self):
        _old_database(self.path, {"job-a": _legacy()}, {"word": _file()})
        before = self.path.read_bytes()
        environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        result = subprocess.run([sys.executable, str(migration.REPO_ROOT / "scripts/ops/migrate_document_job_list_keys.py"),
                                 "--backend", "database", "--database-path", str(self.path)],
                                cwd=self.root, env=environment, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["mode"], "dry-run")
        self.assertEqual(report["tables"]["document_jobs"]["projection_version"], 3)
        self.assertEqual(before, self.path.read_bytes())
