"""Migration A 的真实旧 file/SQLite 数据合同；MySQL fake 仅校验 SQL 和连接调用。"""

from copy import deepcopy
import io
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest import TestCase
from unittest.mock import patch

from app.core.config import Settings
from app.domains.document_jobs.delivery_state import DOCUMENT_JOB_STATE_FIELDS
from app.domains.document_jobs.models import DocumentJobRecord
from app.infrastructure.persistence.file.document_jobs import FileDocumentJobRepository
from app.infrastructure.persistence.sqlite.document_jobs import SqliteDocumentJobRepository
from scripts.ops import migrate_document_job_state as migration
from tests import test_database_job_repository as persistence


def _legacy(job_id="job-a"):
    record = DocumentJobRecord(
        id=job_id, tenant_id="tenant", company_id="company", created_by="operator",
        source_file_id="source", template_version_id="default@2", status="succeeded", stage="completed",
        result_file_id="word", document_ir_file_id="ir", created_at="2026-10-10T01:02:03Z",
        updated_at="2026-10-11T02:03:04Z", completed_at="2026-10-11T02:03:04Z",
        translation_qa_status="approved", translation_qa_note="迁移不能输出或删除的历史备注",
        translation_qa_reviewed_by="old-reviewer", translation_qa_reviewed_at="2026-10-11T02:03:04Z",
        request_snapshot={"resource_version": "original", "nested": [1, {"a": True}]},
        prepared_result={"generation": 0, "document_ir_file_id": "ir", "file": {
            "id": "word", "tenant_id": "tenant", "company_id": "company", "job_id": job_id,
            "file_type": "generated_word", "storage_provider": "local_file", "bucket": "local-file",
            "object_key": "document-files/tenant/word/result.docx", "original_filename": "result.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "size_bytes": 7, "status": "uploaded", "checksum_sha256": "sha256:" + "a" * 64,
            "expires_at": "2026-12-01T00:00:00Z", "created_at": "2026-10-11T02:03:04Z",
            "updated_at": "2026-10-11T02:03:04Z",
        }},
    )
    payload = record.model_dump(mode="json")
    for field in DOCUMENT_JOB_STATE_FIELDS:
        payload.pop(field)
    payload["unknown_raw"] = {"future_contract": ["retain", {"v": 3}]}
    return payload


def _snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
            for path in root.rglob("*")}


def _write_file(root, payload, job_id=None):
    job_id = job_id or payload["id"]
    directory = root / "document_jobs" / job_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "job.json"
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _old_sqlite(path, payloads, *, partial_schema=False):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE document_jobs (job_id TEXT PRIMARY KEY, payload TEXT NOT NULL, "
                           "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        connection.execute("CREATE TABLE unrelated_domain (value TEXT)")
        if partial_schema:
            connection.execute("ALTER TABLE document_jobs ADD COLUMN quality_status TEXT NOT NULL DEFAULT 'pending'")
        for job_id, payload in payloads.items():
            connection.execute("INSERT INTO document_jobs (job_id, payload, created_at, updated_at) VALUES (?, ?, ?, ?)",
                               (job_id, payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False),
                                "column-created-original", "column-updated-original"))


def _settings(root, backend):
    return Settings(_env_file=None, data_dir=str(root), jobs_repository_backend=backend,
                    jobs_metadata_database_path=str(root / "metadata.sqlite3"))


def _raw_payload(root, backend, job_id):
    if backend == "file":
        return (root / "document_jobs" / job_id / "job.json").read_text(encoding="utf-8")
    with sqlite3.connect(root / "metadata.sqlite3") as connection:
        return connection.execute("SELECT payload FROM document_jobs WHERE job_id = ?", (job_id,)).fetchone()[0]


def _stored(root, backend, job_id):
    return json.loads(_raw_payload(root, backend, job_id))


class _MigrationMysqlCursor(persistence._FakeMysqlCursor):
    def execute(self, sql, params=()):
        normalized = " ".join(sql.lower().split())
        if normalized == "set transaction read only":
            self.database.executed_sql.append(normalized)
            self._rows = []
            return
        if normalized.startswith("select column_name as column_name from information_schema.columns"):
            self.database.executed_sql.append(normalized)
            self._rows = [{"column_name": name} for name in self.database.table_columns.get(params[0], set())]
            return
        if normalized.startswith("select job_id, payload"):
            self.database.executed_sql.append(normalized)
            after, limit = params
            self._rows = [deepcopy(row) for key, row in sorted(self.database.document_jobs.items()) if key > after][:limit]
            return
        if normalized.startswith("alter table document_jobs add column") and normalized.split()[5] == self.database.fail_column:
            self.database.executed_sql.append(normalized)
            raise RuntimeError("模拟 DDL 失败，底层消息不得输出")
        if normalized.startswith("update document_jobs set payload") and params[-1] == self.database.fail_job:
            self.database.executed_sql.append(normalized)
            raise RuntimeError("模拟存储失败，底层消息不得输出")
        if normalized.startswith("alter table document_jobs add column"):
            super().execute(sql, params)
            name = normalized.split()[5]
            defaults = {"quality_status": "pending", "review_status": "unreviewed",
                        "delivery_status": "internal_draft", "quality_summary_json": None, "list_query_json": None}
            for row in self.database.document_jobs.values():
                row.setdefault(name, defaults[name])
            return
        return super().execute(sql, params)


class _MigrationMysqlConnection(persistence._FakeMysqlConnection):
    def cursor(self):
        return _MigrationMysqlCursor(self.database)


class _MigrationMysqlDatabase(persistence._FakeMysqlDatabase):
    def __init__(self, payloads):
        super().__init__()
        self.fail_column = None
        self.fail_job = None
        self.table_columns["document_jobs"] = migration.BASE_COLUMNS.copy()
        for job_id, payload in payloads.items():
            self.document_jobs[job_id] = {"job_id": job_id, "payload": json.dumps(payload, ensure_ascii=False),
                                          "created_at": "original-created", "updated_at": "original-updated"}

    def connect(self):
        return _MigrationMysqlConnection(self)


class DocumentJobDeliveryStateMigrationTests(TestCase):
    def test_file_dry_run_and_verify_are_byte_and_directory_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_file(root, _legacy())
            before = _snapshot(root)
            with patch.object(migration, "FilePersistenceBackend", side_effect=AssertionError("只读不能初始化 backend")):
                dry = migration.migrate_document_job_state(_settings(root, "file"))
                verify = migration.migrate_document_job_state(_settings(root, "file"), mode="verify")
            self.assertEqual(dry["exit_code"], 0)
            self.assertEqual(dry["missing_field_count"], 4)
            self.assertEqual(verify["exit_code"], 1)
            self.assertEqual(before, _snapshot(root))
            self.assertFalse(dry["has_more"])
            self.assertEqual(dry["last_successful_job_id"], "job-a")

    def test_sqlite_dry_run_and_verify_do_not_bootstrap_or_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _old_sqlite(root / "metadata.sqlite3", {"job-a": _legacy()})
            before = _snapshot(root)
            with patch.object(migration, "SqlitePersistenceBackend", side_effect=AssertionError("只读不能初始化 backend")):
                dry = migration.migrate_document_job_state(_settings(root, "database"))
                verify = migration.migrate_document_job_state(_settings(root, "database"), mode="verify")
            self.assertEqual(dry["schema_missing"], list(migration.SCHEMA_COLUMNS))
            self.assertEqual(verify["exit_code"], 1)
            self.assertEqual(before, _snapshot(root))

    def test_missing_targets_fail_without_creating_any_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "absent" / "nested"
            for backend in ("file", "database"):
                for mode in ("dry-run", "verify", "apply"):
                    with self.subTest(backend=backend, mode=mode):
                        report = migration.migrate_document_job_state(_settings(root, backend), mode=mode)
                        self.assertEqual(report["exit_code"], 1)
                        self.assertEqual(report["errors"][0]["category"], "target_missing")
                        self.assertFalse(root.parent.exists())

    def test_schema_apply_only_adds_missing_document_job_columns_and_resumes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _old_sqlite(root / "metadata.sqlite3", {"job-a": _legacy()}, partial_schema=True)
            before = _stored(root, "database", "job-a")
            report = migration.migrate_document_job_state(_settings(root, "database"), mode="apply", phase="schema")
            self.assertEqual(report["exit_code"], 0)
            self.assertEqual(report["schema_added"], list(migration.SCHEMA_COLUMNS[1:]))
            self.assertEqual(report["scanned_rows"], 0)
            self.assertEqual(_stored(root, "database", "job-a"), before)
            with sqlite3.connect(root / "metadata.sqlite3") as connection:
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
                self.assertEqual(tables, {"document_jobs", "unrelated_domain"})
                self.assertEqual({row[1] for row in connection.execute("PRAGMA table_info(document_jobs)")},
                                 migration.BASE_COLUMNS | set(migration.SCHEMA_COLUMNS))
            again = migration.migrate_document_job_state(_settings(root, "database"), mode="apply", phase="schema")
            self.assertEqual(again["schema_added"], [])

    def test_backfill_preserves_partial_fields_raw_data_and_resumes_by_keyset(self):
        for backend in ("file", "database"):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                first, second = _legacy("job-a"), _legacy("job-b")
                first.update(quality_status="warning", quality_summary={"count": 2, "nested": {"ok": True}})
                if backend == "file":
                    _write_file(root, second)
                    _write_file(root, first)
                else:
                    _old_sqlite(root / "metadata.sqlite3", {"job-b": second, "job-a": first})
                settings = _settings(root, backend)
                batch = migration.migrate_document_job_state(settings, mode="apply", batch_size=1)
                self.assertEqual(batch["exit_code"], 0)
                self.assertEqual(batch["last_successful_job_id"], "job-a")
                self.assertTrue(batch["has_more"])
                self.assertNotIn("review_status", _stored(root, backend, "job-b"))
                rest = migration.migrate_document_job_state(settings, mode="apply", batch_size=1, after_job_id="job-a")
                self.assertEqual(rest["exit_code"], 0)
                self.assertFalse(rest["has_more"])
                for original in (first, second):
                    stored = _stored(root, backend, original["id"])
                    for key, value in original.items():
                        self.assertEqual(stored[key], value, key)
                    self.assertEqual(stored["review_status"], "unreviewed")
                    self.assertEqual(stored["delivery_status"], "internal_draft")
                before = [_stored(root, backend, job_id) for job_id in ("job-a", "job-b")]
                again = migration.migrate_document_job_state(settings, mode="apply")
                self.assertEqual(again["payloads_backfilled"], 0)
                self.assertEqual(before, [_stored(root, backend, job_id) for job_id in ("job-a", "job-b")])
                self.assertEqual(migration.migrate_document_job_state(settings, mode="verify")["exit_code"], 0)
                if backend == "database":
                    with sqlite3.connect(root / "metadata.sqlite3") as connection:
                        self.assertEqual(connection.execute("SELECT created_at, updated_at FROM document_jobs WHERE job_id='job-a'").fetchone(),
                                         ("column-created-original", "column-updated-original"))

    def test_invalid_rows_stop_apply_without_skipping_the_failed_cursor(self):
        invalids = {
            "invalid_json": '{"note":"不应外泄的原始内容",',
            "invalid_payload_type": '["不应外泄的原始内容"]',
            "unknown_enum": {**_legacy("job-b"), "quality_status": "unavailable"},
            "invalid_combination": {**_legacy("job-b"), "delivery_status": "published"},
        }
        for backend in ("file", "database"):
            for kind, invalid in invalids.items():
                with self.subTest(backend=backend, kind=kind), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    payloads = {"job-a": _legacy("job-a"), "job-b": invalid, "job-c": _legacy("job-c")}
                    if backend == "file":
                        for job_id, payload in payloads.items():
                            _write_file(root, payload, job_id)
                    else:
                        _old_sqlite(root / "metadata.sqlite3", payloads)
                    invalid_before = _raw_payload(root, backend, "job-b")
                    report = migration.migrate_document_job_state(_settings(root, backend), mode="apply")
                    self.assertEqual(report["exit_code"], 1)
                    self.assertEqual(report["last_successful_job_id"], "job-a")
                    self.assertEqual(report["processed_rows"], 1)
                    self.assertEqual(report["scanned_rows"], 2)
                    self.assertEqual(report["errors"][0]["job_id"], "job-b")
                    self.assertTrue(report["has_more"])
                    self.assertNotIn("不应外泄", json.dumps(report, ensure_ascii=False))
                    self.assertEqual(_raw_payload(root, backend, "job-b"), invalid_before)
                    self.assertNotIn("review_status", _stored(root, backend, "job-c"))
                    self.assertIn("review_status", _stored(root, backend, "job-a"))

    def test_verify_detects_column_drift_and_apply_calibrates_even_without_missing_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _old_sqlite(root / "metadata.sqlite3", {"job-a": _legacy()})
            settings = _settings(root, "database")
            self.assertEqual(migration.migrate_document_job_state(settings, mode="apply")["exit_code"], 0)
            original = _stored(root, "database", "job-a")
            with sqlite3.connect(root / "metadata.sqlite3") as connection:
                connection.execute("UPDATE document_jobs SET review_status='blocked', quality_summary_json='[]'")
            before = _snapshot(root)
            verify = migration.migrate_document_job_state(settings, mode="verify")
            self.assertEqual(verify["exit_code"], 1)
            self.assertEqual(verify["column_mismatches"], [{"job_id": "job-a", "columns": ["review_status", "quality_summary_json"]}])
            self.assertEqual(before, _snapshot(root))
            applied = migration.migrate_document_job_state(settings, mode="apply", phase="backfill")
            self.assertEqual(applied["exit_code"], 0)
            self.assertEqual(applied["payloads_backfilled"], 0)
            self.assertEqual(_stored(root, "database", "job-a"), original)
            self.assertEqual(migration.migrate_document_job_state(settings, mode="verify")["exit_code"], 0)

    def test_backfill_requires_schema_and_verify_marks_unvisited_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _old_sqlite(root / "metadata.sqlite3", {"job-a": _legacy(), "job-b": _legacy("job-b")})
            settings = _settings(root, "database")
            before = _snapshot(root)
            report = migration.migrate_document_job_state(settings, mode="apply", phase="backfill")
            self.assertEqual(report["errors"][0]["category"], "state_columns_missing")
            self.assertEqual(before, _snapshot(root))
            migration.migrate_document_job_state(settings, mode="apply")
            verify = migration.migrate_document_job_state(settings, mode="verify", batch_size=1)
            self.assertEqual(verify["payload_missing"], [])
            self.assertEqual(verify["column_mismatches"], [])
            self.assertTrue(verify["has_more"])
            self.assertEqual(verify["exit_code"], 1)

    def test_interruption_reports_only_committed_cursor_and_can_resume(self):
        for backend, adapter in (("file", FileDocumentJobRepository), ("database", SqliteDocumentJobRepository)):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if backend == "file":
                    _write_file(root, _legacy())
                    _write_file(root, _legacy("job-b"))
                else:
                    _old_sqlite(root / "metadata.sqlite3", {"job-a": _legacy(), "job-b": _legacy("job-b")})
                original = adapter.backfill_document_job_state_if_missing

                def interrupt(repository, job_id):
                    if job_id == "job-b":
                        raise KeyboardInterrupt
                    return original(repository, job_id)

                settings = _settings(root, backend)
                with patch.object(adapter, "backfill_document_job_state_if_missing", interrupt):
                    report = migration.migrate_document_job_state(settings, mode="apply")
                self.assertEqual(report["errors"], [{"job_id": "job-b", "category": "interrupted"}])
                self.assertEqual(report["last_successful_job_id"], "job-a")
                resumed = migration.migrate_document_job_state(settings, mode="apply", after_job_id="job-a")
                self.assertEqual(resumed["exit_code"], 0)
                self.assertEqual(resumed["last_successful_job_id"], "job-b")

    def test_locked_backfill_uses_latest_raw_instead_of_scanned_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = _write_file(root, _legacy())
            original = FileDocumentJobRepository.backfill_document_job_state_if_missing

            def new_writer_first(repository, job_id):
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload.update(quality_status="warning", quality_summary={"new_evidence": True},
                               review_status="approved", delivery_status="internal_draft")
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                return original(repository, job_id)

            with patch.object(FileDocumentJobRepository, "backfill_document_job_state_if_missing", new_writer_first):
                report = migration.migrate_document_job_state(_settings(root, "file"), mode="apply")
            self.assertEqual(report["exit_code"], 0)
            self.assertEqual(report["payloads_backfilled"], 0)
            self.assertEqual(_stored(root, "file", "job-a")["quality_summary"], {"new_evidence": True})
            self.assertEqual(_stored(root, "file", "job-a")["review_status"], "approved")

    def test_file_path_boundary_and_id_mismatch_fail_without_external_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.mkdir()
            external = outside / "job.json"
            external.write_text(json.dumps(_legacy()), encoding="utf-8")
            storage = root / "data"
            (storage / "document_jobs").mkdir(parents=True)
            (storage / "document_jobs" / "job-a").symlink_to(outside, target_is_directory=True)
            before = external.read_bytes()
            report = migration.migrate_document_job_state(_settings(storage, "file"), mode="apply")
            self.assertEqual(report["errors"][0]["category"], "unsafe_file_path")
            self.assertEqual(external.read_bytes(), before)
            (storage / "document_jobs" / "job-a").unlink()
            _write_file(storage, _legacy("other-job"), "job-a")
            report = migration.migrate_document_job_state(_settings(storage, "file"), mode="apply")
            self.assertEqual(report["errors"][0]["category"], "job_id_mismatch")

    def test_sqlite_uncheckpointed_log_is_rejected_without_read_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _old_sqlite(root / "metadata.sqlite3", {"job-a": _legacy()})
            (root / "metadata.sqlite3-wal").write_bytes(b"uncheckpointed")
            before = _snapshot(root)
            report = migration.migrate_document_job_state(_settings(root, "database"))
            self.assertEqual(report["errors"][0]["category"], "sqlite_requires_checkpoint")
            self.assertEqual(before, _snapshot(root))

    def test_fake_mysql_schema_partial_forward_and_payload_projection(self):
        database = _MigrationMysqlDatabase({"job-a": _legacy()})
        settings = Settings(_env_file=None, jobs_repository_backend="mysql")
        before = deepcopy(database.document_jobs)
        dry = migration.migrate_document_job_state(settings, mysql_connect_factory=database.connect)
        self.assertEqual(dry["schema_missing"], list(migration.SCHEMA_COLUMNS))
        self.assertEqual(database.document_jobs, before)
        self.assertFalse(any(sql.startswith(("alter", "create", "update")) for sql in database.executed_sql))
        database.fail_column = "review_status"
        failed = migration.migrate_document_job_state(settings, mode="apply", phase="schema", mysql_connect_factory=database.connect)
        self.assertEqual(failed["exit_code"], 1)
        self.assertEqual(failed["schema_added"], ["quality_status"])
        self.assertNotIn("quality_status", failed["schema_remaining"])
        self.assertIn("quality_status", database.table_columns["document_jobs"])
        self.assertGreater(database.rollback_count, 0)
        database.fail_column = None
        applied = migration.migrate_document_job_state(settings, mode="apply", mysql_connect_factory=database.connect)
        self.assertEqual(applied["exit_code"], 0)
        self.assertEqual(applied["schema_added"], list(migration.SCHEMA_COLUMNS[1:]))
        payload = json.loads(database.document_jobs["job-a"]["payload"])
        for key, value in _legacy().items():
            self.assertEqual(payload[key], value, key)
        self.assertEqual(database.document_jobs["job-a"]["quality_status"], "pending")
        self.assertEqual(database.document_jobs["job-a"]["review_status"], "unreviewed")
        self.assertEqual(database.document_jobs["job-a"]["created_at"], "original-created")
        self.assertEqual(database.document_jobs["job-a"]["updated_at"], "original-updated")
        self.assertIn("select payload from document_jobs where job_id = %s for update", database.executed_sql)
        self.assertTrue(any(sql.startswith("select job_id, payload") and "where job_id > %s order by job_id limit %s" in sql for sql in database.executed_sql))
        self.assertFalse(any(sql.startswith(("create", "drop")) for sql in database.executed_sql))
        self.assertEqual(migration.migrate_document_job_state(settings, mode="verify", mysql_connect_factory=database.connect)["exit_code"], 0)

    def test_fake_mysql_write_failure_calls_rollback_and_keeps_last_success_cursor(self):
        database = _MigrationMysqlDatabase({"job-a": _legacy(), "job-b": _legacy("job-b")})
        database.fail_job = "job-b"
        report = migration.migrate_document_job_state(Settings(_env_file=None, jobs_repository_backend="mysql"),
                                                     mode="apply", mysql_connect_factory=database.connect)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["last_successful_job_id"], "job-a")
        self.assertEqual(report["processed_rows"], 1)
        self.assertGreater(database.rollback_count, 0)
        self.assertNotIn("底层消息", json.dumps(report, ensure_ascii=False))
        self.assertNotIn("review_status", json.loads(database.document_jobs["job-b"]["payload"]))

    def test_cli_defaults_to_dry_run_and_does_not_print_private_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_file(root, _legacy())
            output = io.StringIO()
            settings = _settings(root, "file").model_copy(update={"jobs_mysql_password": "private-password"})
            with patch.object(migration, "Settings", return_value=settings), patch("sys.stdout", output):
                code = migration.main(["--backend", "file", "--data-dir", str(root)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["mode"], "dry-run")
            self.assertNotIn("private-password", output.getvalue())
            self.assertNotIn("历史备注", output.getvalue())
