"""v2 派生事实共享写者：真实 SQLite 原子性与 fake MySQL 调用形状。"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from app.domains.document_jobs.list_query import (
    DocumentJobListQuery, document_job_list_projection_from_raw,
    document_file_review_projection_from_raw,
)
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.new_generation import NewGenerationSubmission, GENERATION_REQUESTS_ENVELOPE
from app.domains.document_jobs.review import ReviewBinding, ReviewSubmission, digest, observed_review_source
from app.domains.files.models import DocumentFileRecord
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.infrastructure.persistence.sqlite.document_jobs import SqliteDocumentJobRepository
from app.infrastructure.persistence.sqlite.files import SqliteDocumentFileRepository
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.document_jobs import MysqlDocumentJobRepository
from app.infrastructure.persistence.mysql.files import MysqlDocumentFileRepository

NOW = datetime.now(timezone.utc)


def job_record(job_id="job", **patches):
    return DocumentJobRecord.model_validate({"id": job_id, "tenant_id": "T", "company_id": "C", "created_by": "U",
        "source_file_id": "source", "template_version_id": "default@2", "created_at": NOW, "updated_at": NOW, **patches})


def file_record(file_id="word", **patches):
    values = dict(id=file_id, tenant_id="T", company_id="C", job_id="job", created_by="U",
        file_type="generated_word", storage_provider="local_file", bucket="local-file",
        object_key=f"document-files/T/{file_id}/result.docx", original_filename="result.docx", mime_type="application/docx",
        size_bytes=7, checksum_sha256="sha256:" + "a" * 64, etag="etag", status="uploaded",
        expires_at=NOW + timedelta(days=30), created_at=NOW, updated_at=NOW,
        metadata={"document_job_result_protocol": 1})
    values.update(patches)
    return DocumentFileRecord.model_validate(values)


class SqliteV2WriterTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backend = SqlitePersistenceBackend(Path(self.temp.name) / "metadata.sqlite")
        self.jobs = SqliteDocumentJobRepository(self.backend)
        self.files = SqliteDocumentFileRepository(self.backend)

    def row(self, table, key, identity):
        with self.backend.connect() as connection:
            return dict(connection.execute(f"SELECT * FROM {table} WHERE {key} = ?", (identity,)).fetchone())

    def assert_job_projection(self, identity="job"):
        row = self.row("document_jobs", "job_id", identity)
        self.assertEqual(json.loads(row["list_query_json"]), document_job_list_projection_from_raw(row["payload"]))
        self.assertEqual(json.loads(row["list_query_json"])["version"], 2)
        return row

    def assert_file_projection(self, identity="word"):
        row = self.row("document_files", "file_id", identity)
        self.assertEqual(json.loads(row["review_query_json"]), document_file_review_projection_from_raw(row["payload"]))
        self.assertEqual(json.loads(row["review_query_json"])["version"], 1)
        return row

    def test_all_file_writers_project_serialized_values_and_deletion_claim_without_revision(self):
        initial = file_record(status="pending_upload", etag=None, metadata={"document_job_result_protocol": 1, "tuple": (1, 2)})
        self.files.create_document_file(initial)
        first = self.assert_file_projection()
        self.assertEqual(json.loads(first["payload"])["metadata"]["tuple"], [1, 2])
        descriptor = self.files.get_document_file("word").model_copy(update={"status": "uploaded", "etag": "uploaded-etag"})
        self.files.materialize_prepared_result(descriptor)
        self.assert_file_projection()
        self.files.update_document_file("word", metadata={"document_job_result_protocol": 1, "changed": True})
        self.assert_file_projection()
        self.files.expire_document_file("word", now=NOW + timedelta(days=31))
        expired = self.assert_file_projection()
        self.files.reserve_document_file_deletion("word", claim_id="delete-1", now=NOW + timedelta(days=31))
        reserved = self.assert_file_projection()
        self.assertEqual(json.loads(expired["payload"])["review_source_revision"], json.loads(reserved["payload"])["review_source_revision"])
        self.assertNotEqual(expired["review_query_json"], reserved["review_query_json"])
        self.files.finish_document_file_deletion("word", claim_id="delete-1", now=NOW + timedelta(days=31))
        self.assertEqual(json.loads(self.assert_file_projection()["payload"])["status"], "deleted")

    def test_file_type_change_rebuilds_applicability_and_failed_write_rolls_back_both(self):
        self.files.create_document_file(file_record(file_type="source_pdf"))
        before = self.assert_file_projection()
        self.files.update_document_file("word", file_type="generated_word")
        after = self.assert_file_projection()
        self.assertNotEqual(before["review_query_json"], after["review_query_json"])
        with self.backend.connect() as connection:
            connection.execute("CREATE TRIGGER reject_file BEFORE UPDATE ON document_files BEGIN SELECT RAISE(ABORT, '拒绝测试写入'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.files.update_document_file("word", etag="cannot-commit")
        self.assertEqual(after, self.row("document_files", "file_id", "word"))

    def test_job_create_conditional_patch_review_and_lifecycle_keep_projection(self):
        self.jobs.create_document_job(job_record(status="running", stage="uploading"))
        self.assert_job_projection()
        self.jobs.update_document_job_if_current("job", allowed_statuses={"running"}, allowed_stages={"uploading"},
            error_message="Straße", updated_at=NOW + timedelta(seconds=1))
        self.assert_job_projection()
        self.jobs.update_document_job("job", status="failed", stage="failed", error_code="failure")
        self.assert_job_projection()
        submission = ReviewSubmission(record_id="review-1", status="needs_fix", reviewed_by="U", reviewed_at=NOW,
            reviewer_role="operator", binding=ReviewBinding(generation=0, result_file_id=None, binding_state="no_result"))
        self.jobs.update_document_job_review_if_current("job", submission=submission)
        self.assertEqual(json.loads(self.assert_job_projection()["payload"])["review_status"], "needs_fix")
        self.jobs.update_document_job_lifecycle_if_current("job", expected_retry_count=0, action="archive", actor_id="U", occurred_at=NOW)
        self.assert_job_projection()
        self.jobs.update_document_job_lifecycle_if_current("job", expected_retry_count=0, action="delete", actor_id="U", occurred_at=NOW)
        self.assert_job_projection()

    def test_state_backfill_preserves_raw_and_marks_unstable_projection_unavailable(self):
        self.jobs.create_document_job(job_record())
        with self.backend.connect() as connection:
            original = json.loads(connection.execute("SELECT payload FROM document_jobs").fetchone()[0])
            original.pop("created_at")
            original.pop("review_status")
            original["unknown_raw"] = {"keep": "原样"}
            connection.execute("UPDATE document_jobs SET payload = ?", (json.dumps(original, ensure_ascii=False),))
        self.assertTrue(self.jobs.backfill_document_job_state_if_missing("job"))
        row = self.row("document_jobs", "job_id", "job")
        raw = json.loads(row["payload"])
        self.assertNotIn("created_at", raw)
        self.assertEqual(raw["unknown_raw"], original["unknown_raw"])
        self.assertIsNone(row["list_query_json"])
        self.assertEqual(row["created_at"], NOW.isoformat())
        with self.backend.connect() as connection:
            raw["created_at"] = NOW.isoformat()
            connection.execute("UPDATE document_jobs SET payload = ?", (json.dumps(raw),))
        self.jobs.backfill_document_job_state_if_missing("job")
        self.assert_job_projection()

    def test_new_generation_preserves_unknown_fields_ledger_and_replay(self):
        source = self.files.create_document_file(file_record("source", file_type="source_pdf", mime_type="application/pdf"))
        current = self.jobs.create_document_job(job_record(status="succeeded", stage="completed", result_file_id="missing-result"))
        with self.backend.connect() as connection:
            raw = json.loads(connection.execute("SELECT payload FROM document_jobs").fetchone()[0])
            raw["unknown_raw"] = {"keep": True}
            connection.execute("UPDATE document_jobs SET payload = ?", (json.dumps(raw),))
        submission = NewGenerationSubmission(request_id=str(uuid4()), actor_id="U", note="再次处理",
            expected_source=observed_review_source(current, None), expected_request_snapshot_sha256=digest(current.request_snapshot),
            source_file=source, audit_id="audit-generation", trace_id="trace-generation")
        acceptance, updated, replayed = self.jobs.accept_document_job_new_generation("job", submission=submission, max_retries=3)
        self.assertFalse(replayed)
        self.assertEqual(updated.retry_count, 1)
        first = self.assert_job_projection()
        self.jobs.update_document_job("job", error_message="保留账本")
        raw = json.loads(self.assert_job_projection()["payload"])
        self.assertEqual(raw["unknown_raw"], {"keep": True})
        self.assertEqual(raw[GENERATION_REQUESTS_ENVELOPE], json.loads(first["payload"])[GENERATION_REQUESTS_ENVELOPE])
        replay, _, replayed = self.jobs.accept_document_job_new_generation("job", submission=submission, max_retries=3)
        self.assertTrue(replayed)
        self.assertEqual(acceptance, replay)
        with self.backend.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0], 1)

    def test_review_write_failure_rolls_back_history_payload_and_projection(self):
        self.jobs.create_document_job(job_record())
        before = self.assert_job_projection()
        with self.backend.connect() as connection:
            connection.execute("CREATE TRIGGER reject_job BEFORE UPDATE ON document_jobs BEGIN SELECT RAISE(ABORT, '拒绝测试写入'); END")
        submission = ReviewSubmission(record_id="review-fails", status="needs_fix", reviewed_by="U", reviewed_at=NOW,
            reviewer_role="operator", binding=ReviewBinding(generation=0, result_file_id=None, binding_state="no_result"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.jobs.update_document_job_review_if_current("job", submission=submission)
        self.assertEqual(before, self.row("document_jobs", "job_id", "job"))
        with self.backend.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM document_job_review_records").fetchone()[0], 0)

    def test_bootstrap_adds_two_columns_without_rewriting_legacy_data(self):
        path = Path(self.temp.name) / "legacy.sqlite"
        with sqlite3.connect(path) as connection:
            connection.executescript("CREATE TABLE document_jobs(job_id TEXT PRIMARY KEY,payload TEXT,created_at TEXT,updated_at TEXT);"
                                     "CREATE TABLE document_files(file_id TEXT PRIMARY KEY,payload TEXT,created_at TEXT,updated_at TEXT);")
            connection.execute("INSERT INTO document_jobs VALUES ('job','{}','c','u')")
            connection.execute("INSERT INTO document_files VALUES ('file','{}','c','u')")
        backend = SqlitePersistenceBackend(path)
        backend.initialize_schema()
        with backend.connect() as connection:
            self.assertEqual(tuple(connection.execute("SELECT payload,created_at,updated_at,list_query_json FROM document_jobs").fetchone()), ("{}", "c", "u", None))
            self.assertEqual(tuple(connection.execute("SELECT payload,created_at,updated_at,review_query_json FROM document_files").fetchone()), ("{}", "c", "u", None))

    def test_current_snapshot_port_opens_a_new_connection_at_each_guard(self):
        connections = []
        expected = job_record()
        def read(connection, observed, *, mysql):
            self.assertIs(observed, expected)
            self.assertFalse(mysql)
            connections.append(connection)
            return len(connections) == 1
        with patch("app.infrastructure.persistence.sqlite.document_jobs.is_document_job_table_evidence_snapshot_current_sql", side_effect=read):
            self.assertTrue(self.jobs.is_document_job_table_evidence_snapshot_current(expected))
            self.assertFalse(self.jobs.is_document_job_table_evidence_snapshot_current(expected))
        self.assertIsNot(connections[0], connections[1])


class FakeMysqlConnection:
    """只记录 SQL 和事务调用；不模拟 MySQL 执行或隔离语义。"""
    def __init__(self, payload=None):
        self.payload = payload
        self.sql = []
        self.commits = self.rollbacks = self.closes = 0
    def cursor(self): return self
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def execute(self, sql, params=()): self.sql.append((sql, params))
    def fetchone(self): return {"payload": self.payload} if self.payload else None
    def fetchall(self): return []
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def close(self): self.closes += 1


class MysqlV2WriterShapeTests(TestCase):
    def backend(self, connection):
        return MysqlPersistenceBackend(MysqlPersistenceConfig(host="unused", port=3306, user="unused", password="", database="unused"),
            initialize=False, connect_factory=lambda: connection)

    def test_job_and_file_statements_bind_payload_and_matching_projection(self):
        connection = FakeMysqlConnection()
        backend = self.backend(connection)
        repository = MysqlDocumentJobRepository(backend)
        repository.create_document_job(job_record())
        sql, params = connection.sql[-1]
        self.assertIn("list_query_json", sql)
        self.assertEqual(json.loads(params[-1]), document_job_list_projection_from_raw(params[1]))
        connection.payload = params[1]
        repository.update_document_job("job", error_message="changed")
        sql, params = connection.sql[-1]
        self.assertIn("list_query_json = %s", sql)
        self.assertEqual(json.loads(params[-2]), document_job_list_projection_from_raw(params[0]))
        connection.payload = None
        files = MysqlDocumentFileRepository(backend)
        files.create_document_file(file_record())
        sql, params = connection.sql[-1]
        self.assertIn("review_query_json", sql)
        self.assertEqual(json.loads(params[-1]), document_file_review_projection_from_raw(params[1]))

    def test_query_sets_repeatable_read_and_cleans_up_failure(self):
        connection = FakeMysqlConnection()
        repository = MysqlDocumentJobRepository(self.backend(connection))
        with patch("app.infrastructure.persistence.mysql.document_jobs.query_document_jobs_sql", side_effect=ValueError("测试查询失败")):
            with self.assertRaises(ValueError):
                repository.query_document_jobs(DocumentJobListQuery("T", "C", as_of=NOW))
        self.assertEqual([sql for sql, _ in connection.sql], ["SET TRANSACTION ISOLATION LEVEL REPEATABLE READ", "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY"])
        self.assertEqual((connection.commits, connection.rollbacks, connection.closes), (0, 1, 1))


class SqliteV2PublishedWriterTests(TestCase):
    def test_actual_prepare_preview_review_publish_writers_keep_same_row_facts(self):
        # 真实业务状态 owner 与 SQLite；只有夹具的外部转换/预览 provider 使用替身。
        from tests.document_job_list_query_v2_publication_fixtures import V2PublicationFixture
        class Fixture(V2PublicationFixture, TestCase):
            pass
        fixture = Fixture()
        original = SqliteDocumentJobRepository._write_job
        observed = set()
        def write(repository, connection, record, **kwargs):
            original(repository, connection, record, **kwargs)
            row = connection.execute("SELECT payload,list_query_json FROM document_jobs WHERE job_id = ?", (record.id,)).fetchone()
            self.assertEqual(json.loads(row["list_query_json"]), document_job_list_projection_from_raw(row["payload"]))
            if record.prepared_result is not None:
                observed.add("prepared")
            if record.word_preview_state is not None:
                observed.add("preview")
            if record.current_review_record_id is not None:
                observed.add("review")
            if record.current_publication_id is not None:
                observed.add("publication")
        with patch.object(SqliteDocumentJobRepository, "_write_job", new=write):
            with fixture.publication_runtime(kind="sqlite") as (runtime, job, admin, *_):
                fixture.publish(runtime, job, admin)
        self.assertEqual(observed, {"prepared", "preview", "review", "publication"})
