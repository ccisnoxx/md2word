"""线上有效复核基线、file/SQLite 语义与 SQL 有界读取合同。"""
from collections import Counter
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.domains.document_jobs.list_query import (
    DocumentJobListQuery, DocumentJobListProjectionUnavailable, DocumentJobListResult,
    document_job_list_projection,
)
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.review import effective_review_job
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.infrastructure.persistence.file.document_jobs import FileDocumentJobRepository
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.infrastructure.persistence.sqlite.document_jobs import SqliteDocumentJobRepository
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.document_jobs import MysqlDocumentJobRepository

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
MYSQL_TEST_CONFIG = MysqlPersistenceConfig("127.0.0.1", 3306, "test", "", "unused")


def job(job_id="a", **values):
    return DocumentJobRecord.model_validate({"id": job_id, "tenant_id": "T", "company_id": "C", "created_by": "U",
        "source_file_id": "source", "template_version_id": "default@2", "created_at": NOW, "updated_at": NOW, **values})


def baseline(jobs, query):
    """本模块不种文件；先由线上 owner 计算缺件时的有效复核，再独立筛选。"""
    def visible(item):
        return (item.tenant_id == query.tenant_id and item.company_id == query.company_id
                and (query.created_by is None or item.created_by == query.created_by)
                and item.deleted_at is None and (query.include_archived or item.archived_at is None))
    def matches(item):
        if query.statuses is not None and item.status not in query.statuses:
            return False
        source = item.request_snapshot.get("source_file")
        filename = source.get("original_filename") if isinstance(source, dict) else None
        values = [item.id, item.source_file_id, filename if isinstance(filename, str) else None,
                  item.error_code, item.error_message]
        if query.q is not None and not any(query.q in value.casefold() for value in values if value):
            return False
        if query.created_from is not None and item.created_at < query.created_from:
            return False
        if query.created_to is not None and item.created_at > query.created_to:
            return False
        return True
    visible_jobs = [item for item in jobs if visible(item)]
    views = [effective_review_job(item, None, now=query.as_of) for item in visible_jobs]
    base = [item for item in views if matches(item)]
    qa = Counter(item.review_status for item in base if item.mode != "direct_pdf_to_word")
    filtered = [item for item in base if query.translation_qa_status is None or (
        item.mode != "direct_pdf_to_word" and (query.translation_qa_status == "all"
                                             or item.review_status == query.translation_qa_status))]
    filtered.sort(key=lambda item: (getattr(item, query.sort.rsplit("_", 1)[0]), item.id),
                  reverse=query.sort.endswith("_desc"))
    start = (query.page - 1) * query.page_size
    page = filtered[start:start + query.page_size]
    raw = {item.id: item for item in visible_jobs}
    return DocumentJobListResult([raw[item.id] for item in page], len(filtered),
        dict(Counter(item.status for item in visible_jobs)), dict(Counter(item.status for item in filtered)),
        {key: qa.get(key, 0) for key in ("unreviewed", "approved", "needs_fix", "blocked")},
        {item.id: None for item in page})


class DocumentJobListQueryTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.sqlite = SqliteDocumentJobRepository(SqlitePersistenceBackend(root / "jobs.sqlite"))
        self.file = FileDocumentJobRepository(FilePersistenceBackend(root / "file"))
        self.query = DocumentJobListQuery("T", "C", as_of=NOW)

    def seed(self, jobs):
        for repository in (self.file, self.sqlite):
            for item in jobs:
                repository.create_document_job(item)

    def test_filters_unicode_permissions_summaries_and_pagination_match_effective_owner(self):
        jobs = [job("a", request_snapshot={"source_file": {"original_filename": "Straße Σς İ 中文 %_\\"}}),
                job("b", mode="en2zh_pdf_to_word", review_status="approved", status="succeeded", stage="completed", result_file_id="word"),
                job("c", mode="ru2zh_pdf_to_word", review_status="needs_fix", status="failed", stage="failed"),
                job("d", archived_at=NOW), job("e", deleted_at=NOW),
                job("f", tenant_id="t"), job("g", company_id="c"), job("h", created_by="u"),
                job("i", tenant_id="Ť"), job("j", company_id="Ć"), job("k", created_by="Ú"),
                job("l", request_snapshot={"source_file": {"original_filename": 12345}}),
                job("m", error_code="alpha", error_message="beta")]
        self.seed(jobs)
        queries = [self.query, replace(self.query, created_by="U"), replace(self.query, include_archived=True),
            replace(self.query, page=99, page_size=2), replace(self.query, statuses=("failed",)),
            replace(self.query, statuses=("pending", "failed"), q="source", created_from=NOW, created_to=NOW)]
        queries += [replace(self.query, translation_qa_status=value) for value in (
            "all", "approved", "unreviewed", "needs_fix", "blocked")]
        queries += [replace(self.query, q=value) for value in (
            "strasse", "σσ", "i\u0307", "%_\\", "中文", "12345", "alphabeta", "alpha", "source")]
        for query in queries:
            for repository in (self.file, self.sqlite):
                with self.subTest(query=query, backend=type(repository).__name__):
                    self.assertEqual(repository.query_document_jobs(query), baseline(jobs, query))

    def test_precise_time_offsets_and_all_sorts(self):
        jobs = [job("a"), job("b"), job("c"), job("d")]
        jobs[1].created_at = NOW.astimezone(timezone(timedelta(hours=8)))
        jobs[2].created_at = NOW + timedelta(microseconds=1)
        jobs[3].created_at = datetime(1960, 1, 1, tzinfo=timezone.utc)
        for index, item in enumerate(jobs):
            item.updated_at = NOW + timedelta(microseconds=3 - index)
        self.seed(jobs)
        for sort in ("created_at_asc", "created_at_desc", "updated_at_asc", "updated_at_desc"):
            for dates in ({}, dict(created_from=NOW, created_to=NOW)):
                query = replace(self.query, sort=sort, **dates)
                self.assertEqual(self.sqlite.query_document_jobs(query), baseline(jobs, query))

    def test_datetime_kinds_follow_actual_comparisons(self):
        item = job(); item.created_at = NOW.replace(tzinfo=None)
        self.seed([item])
        for repository in (self.file, self.sqlite):
            self.assertEqual(repository.query_document_jobs(self.query).total, 1)
            self.assertEqual(repository.query_document_jobs(replace(self.query, created_from=item.created_at)).total, 1)
            # direct 行也先参加日期检查，即使最终 QA 过滤将它排除。
            with self.assertRaises(TypeError):
                repository.query_document_jobs(replace(self.query, translation_qa_status="all", created_from=NOW))
            # 下界已排除该行，上界不应再拒绝其不同类型。
            self.assertEqual(repository.query_document_jobs(replace(self.query,
                created_from=item.created_at + timedelta(days=1), created_to=NOW)).total, 0)
        second = job("b")
        self.file.create_document_job(second); self.sqlite.create_document_job(second)
        with self.assertRaises(TypeError):
            self.sqlite.query_document_jobs(self.query)
        self.assertEqual(self.sqlite.query_document_jobs(replace(self.query, sort="updated_at_desc")).total, 2)
        self.assertEqual(self.sqlite.query_document_jobs(replace(self.query, q="nonexistent")).total, 0)
        # 线上 file 入口先按 created_at 排序，早于查询过滤和选定的排序字段。
        for query in (self.query, replace(self.query, sort="updated_at_desc"), replace(self.query, q="nonexistent")):
            with self.assertRaises(TypeError):
                self.file.query_document_jobs(query)

    def test_sql_models_are_page_bounded_and_full_list_is_unused(self):
        self.seed([job(str(i)) for i in range(9)])
        with patch.object(self.sqlite, "list_document_jobs", side_effect=AssertionError("不得全量读取")), patch.object(
            DocumentJobRecord, "model_validate_json", wraps=DocumentJobRecord.model_validate_json) as decode:
            result = self.sqlite.query_document_jobs(replace(self.query, page_size=2))
        self.assertEqual(result.total, 9)
        self.assertEqual(decode.call_count, 2)

    def test_projection_missing_or_old_version_fails_without_get_time_writes(self):
        self.seed([job()])
        old_projection = json.dumps({**document_job_list_projection(job()), "version": 1})
        for value in (None, old_projection, '{"version": 2}', '{}', 'invalid'):
            with self.sqlite.backend.connect() as connection:
                connection.execute("UPDATE document_jobs SET list_query_json = ?", (value,))
            with self.assertRaises(DocumentJobListProjectionUnavailable):
                self.sqlite.query_document_jobs(self.query)
            with self.sqlite.backend.connect() as connection:
                self.assertEqual(connection.execute("SELECT list_query_json FROM document_jobs").fetchone()[0], value)

    def test_sqlite_aggregates_and_page_share_snapshot(self):
        self.seed([job()])
        with self.sqlite.backend.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
        original = self.sqlite.backend.connect
        calls = []
        class ConnectionProxy:
            def __init__(proxy, connection):
                proxy.connection = connection
            def execute(proxy, statement, params=()):
                cursor = proxy.connection.execute(statement, params)
                calls.append(statement)
                if "GROUP BY" in statement and len([sql for sql in calls if "GROUP BY" in sql]) == 1:
                    # 第一汇总已建立快照后，独立连接提交一个新任务。
                    self.sqlite.create_document_job(job("b"))
                return cursor
        @contextmanager
        def connect():
            with original() as connection:
                yield ConnectionProxy(connection)
        # 写者使用原连接工厂，避免递归包装。
        other = SqliteDocumentJobRepository(SqlitePersistenceBackend(self.sqlite.backend.database_path, initialize=False))
        with patch.object(self.sqlite.backend, "connect", connect), patch.object(
            self.sqlite, "create_document_job", other.create_document_job):
            result = self.sqlite.query_document_jobs(self.query)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.summary, {"pending": 1})
        self.assertEqual([item.id for item in result.items], ["a"])
        self.assertEqual(self.sqlite.query_document_jobs(self.query).total, 2)

    def test_writer_and_state_backfill_keep_projection_current(self):
        self.seed([job()])
        updated = self.sqlite.update_document_job("a", error_message="Straße")
        with self.sqlite.backend.connect() as connection:
            stored = connection.execute("SELECT list_query_json FROM document_jobs").fetchone()[0]
        self.assertEqual(json.loads(stored), document_job_list_projection(updated))
        self.sqlite.backfill_document_job_state_if_missing("a")
        self.assertEqual(self.sqlite.query_document_jobs(replace(self.query, q="strasse")).total, 1)

    def test_sqlite_query_failure_rolls_back_and_closes_read_transaction(self):
        self.seed([job()])
        with self.sqlite.backend.connect() as connection:
            connection.execute("UPDATE document_jobs SET list_query_json = NULL")
        original = self.sqlite.backend.connect
        connections = []
        statements = []

        @contextmanager
        def connect():
            with original() as connection:
                connections.append(connection)
                connection.set_trace_callback(statements.append)
                yield connection

        with patch.object(self.sqlite.backend, "connect", connect):
            with self.assertRaises(DocumentJobListProjectionUnavailable):
                self.sqlite.query_document_jobs(self.query)
        self.assertIn("BEGIN", statements)
        self.assertIn("ROLLBACK", statements)
        with self.assertRaises(sqlite3.ProgrammingError):
            connections[0].execute("SELECT 1")
        self.sqlite.update_document_job("a", error_message="修复投影后可继续查询")
        self.assertEqual(self.sqlite.query_document_jobs(self.query).total, 1)

    def test_mysql_page_query_failure_rolls_back_and_closes_connection(self):
        lifecycle = []

        class Cursor:
            def __enter__(cursor): return cursor
            def __exit__(cursor, *args): pass
            def execute(cursor, sql, params=()):
                if sql.startswith("SELECT j.payload AS payload,"):
                    raise RuntimeError("模拟页面读取失败")
                cursor.rows = ([{"n": 0}] if "COUNT(" in sql and "GROUP BY" not in sql else [])
            def fetchall(cursor): return cursor.rows

        class Connection:
            def cursor(connection): return Cursor()
            def commit(connection): lifecycle.append("commit")
            def rollback(connection): lifecycle.append("rollback")
            def close(connection): lifecycle.append("close")

        backend = MysqlPersistenceBackend(MYSQL_TEST_CONFIG, connect_factory=Connection, initialize=False)
        with self.assertRaisesRegex(RuntimeError, "模拟页面读取失败"):
            MysqlDocumentJobRepository(backend).query_document_jobs(self.query)
        self.assertEqual(lifecycle, ["rollback", "close"])

    def test_mysql_query_uses_binary_bound_values_and_explicit_snapshot(self):
        statements = []
        class Cursor:
            def __enter__(cursor): return cursor
            def __exit__(cursor, *args): pass
            def execute(cursor, sql, params=()):
                statements.append((sql, params))
                cursor.rows = ([{"n": 0}] if "COUNT(" in sql and "GROUP BY" not in sql else [])
            def fetchall(cursor): return cursor.rows
        class Connection:
            committed = False
            closed = False
            def cursor(connection): return Cursor()
            def commit(connection): connection.committed = True
            def rollback(connection): raise AssertionError("不应回滚成功查询")
            def close(connection): connection.closed = True
        connection = Connection()
        backend = MysqlPersistenceBackend(MYSQL_TEST_CONFIG, connect_factory=lambda: connection, initialize=False)
        query = replace(self.query, created_by="U", q="%'_\\", translation_qa_status="approved", created_from=NOW)
        self.assertEqual(MysqlDocumentJobRepository(backend).query_document_jobs(query).total, 0)
        self.assertEqual(statements[0][0], "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        self.assertEqual(statements[1][0], "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        page_sql, values = statements[-1]
        self.assertIn("AS SIGNED", page_sql)
        self.assertIn("AS BINARY", page_sql)
        self.assertIn("LOCATE(CAST(%s AS BINARY)", page_sql)
        self.assertNotIn(query.q, page_sql)
        self.assertIn(query.q, values)
        self.assertEqual(values[-2:], (20, 0))
        self.assertTrue(connection.committed and connection.closed)
