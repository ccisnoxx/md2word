"""显式启用的 MySQL v2 双表专项；只创建 UUID 新库，不读取业务环境配置。"""
from collections import Counter
from contextlib import contextmanager
from dataclasses import replace
import json
import os
import re
from unittest import TestCase, SkipTest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pymysql

from app.core.config import Settings
from app.domains.document_jobs.list_query import DocumentJobListQuery, DocumentJobListProjectionUnavailable
from app.domains.document_jobs.review import ReviewBinding, effective_review_job
from app.domains.files.result_registration import review_source_descriptor
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.document_jobs import MysqlDocumentJobRepository
from app.infrastructure.persistence.mysql.files import MysqlDocumentFileRepository
from app.infrastructure.persistence.mysql.schema import MYSQL_SCHEMA_STATEMENTS
from tests.test_document_job_list_query_v2_writers import NOW, job_record, file_record
from scripts.ops.migrate_document_job_list_query import migrate_document_job_list_query


def _connection_options(environ):
    if environ.get("MD2WORD_TEST_MYSQL") != "1":
        raise SkipTest("未显式启用真实 MySQL 专项验证")
    if "MD2WORD_TEST_MYSQL_DATABASE" in environ:
        raise ValueError("禁止指定既有数据库；测试只能创建随机 schema")
    if any(not environ.get("MD2WORD_TEST_MYSQL_" + name) for name in ("HOST", "PORT", "USER", "PASSWORD")):
        raise ValueError("必须显式提供专用测试 HOST、PORT、USER、PASSWORD")
    if environ["MD2WORD_TEST_MYSQL_HOST"] not in {"127.0.0.1", "::1"}:
        raise ValueError("真实 MySQL 专项验证仅接受 loopback IP")
    try:
        port = int(environ["MD2WORD_TEST_MYSQL_PORT"])
    except ValueError:
        raise ValueError("专用测试端口必须是整数") from None
    if not 1 <= port <= 65535:
        raise ValueError("专用测试端口必须在 1 至 65535 之间")
    return dict(host=environ["MD2WORD_TEST_MYSQL_HOST"], port=port,
        user=environ["MD2WORD_TEST_MYSQL_USER"], password=environ["MD2WORD_TEST_MYSQL_PASSWORD"],
        charset="utf8mb4", connect_timeout=5, read_timeout=10, write_timeout=10,
        cursorclass=pymysql.cursors.DictCursor)


@contextmanager
def _temporary_schema(environ):
    options = _connection_options(environ)
    connection = pymysql.connect(**options, autocommit=True)
    schema = "md2word_query_test_" + uuid4().hex
    created = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION() AS version, @@version_comment AS version_comment, "
                "@@character_set_server AS charset, @@collation_server AS collation, @@transaction_isolation AS isolation")
            facts = cursor.fetchone()
            if not re.match(r"^8\.4\.\d+(?:[-.]|$)", facts["version"]) or "MariaDB" in facts["version"]:
                raise RuntimeError("专项验证要求真实 MySQL 8.4，版本不匹配，未创建 schema")
            print("MySQL v2 专项环境：" + json.dumps(facts, ensure_ascii=False))
            cursor.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            created = True
            cursor.execute(f"USE `{schema}`")
            for table in ("document_jobs", "document_files"):
                ddl = [sql for sql in MYSQL_SCHEMA_STATEMENTS if sql.strip().startswith(f"CREATE TABLE IF NOT EXISTS {table} (")]
                if len(ddl) != 1:
                    raise AssertionError("生产建表语句必须唯一：" + table)
                cursor.execute(ddl[0])
            cursor.execute("SELECT TABLE_NAME AS name, TABLE_COLLATION AS collation FROM INFORMATION_SCHEMA.TABLES "
                           "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME", (schema,))
            print("MySQL v2 双表结构：" + json.dumps(cursor.fetchall(), ensure_ascii=False))
        yield options, schema
    finally:
        try:
            if created:
                with connection.cursor() as cursor:
                    cursor.execute(f"DROP DATABASE `{schema}`")
        finally:
            connection.close()


def _baseline(jobs, files, query):
    """冻结线上筛选顺序；先计算有效复核，再做非 QA/QA 分域与分页。"""
    visible = [job for job in jobs if job.tenant_id == query.tenant_id and job.company_id == query.company_id
        and (query.created_by is None or job.created_by == query.created_by) and job.deleted_at is None
        and (query.include_archived or job.archived_at is None)]
    visible = [effective_review_job(job, files.get(job.result_file_id), now=query.as_of) for job in visible]
    def matches(job):
        source = job.request_snapshot.get("source_file")
        name = source.get("original_filename") if isinstance(source, dict) else None
        values = (job.id, job.source_file_id, name if isinstance(name, str) else None, job.error_code, job.error_message)
        return ((query.statuses is None or job.status in query.statuses)
            and (query.q is None or any(query.q in value.casefold() for value in values if value))
            and (query.created_from is None or job.created_at >= query.created_from)
            and (query.created_to is None or job.created_at <= query.created_to))
    base = [job for job in visible if matches(job)]
    qa = Counter(job.review_status for job in base if job.mode != "direct_pdf_to_word")
    filtered = [job for job in base if query.translation_qa_status is None or (
        job.mode != "direct_pdf_to_word" and query.translation_qa_status in {"all", job.review_status})]
    filtered.sort(key=lambda job: (getattr(job, query.sort.rsplit("_", 1)[0]), job.id), reverse=query.sort.endswith("_desc"))
    start = (query.page - 1) * query.page_size
    return ([job.id for job in filtered[start:start + query.page_size]], len(filtered),
        dict(Counter(job.status for job in visible)), dict(Counter(job.status for job in filtered)),
        {key: qa.get(key, 0) for key in ("unreviewed", "approved", "needs_fix", "blocked")})


def _result_tuple(result):
    return ([job.id for job in result.items], result.total, result.summary, result.filtered_summary, result.translation_qa_summary)


class MysqlV2GuardTests(TestCase):
    def test_default_and_invalid_configuration_never_connect(self):
        valid = dict(MD2WORD_TEST_MYSQL="1", MD2WORD_TEST_MYSQL_HOST="127.0.0.1", MD2WORD_TEST_MYSQL_PORT="33060",
                     MD2WORD_TEST_MYSQL_USER="test", MD2WORD_TEST_MYSQL_PASSWORD="placeholder")
        cases = [({}, SkipTest), ({**valid, "MD2WORD_TEST_MYSQL_DATABASE": "business"}, ValueError),
                 ({**valid, "MD2WORD_TEST_MYSQL_HOST": "remote.invalid"}, ValueError),
                 ({**valid, "MD2WORD_TEST_MYSQL_PORT": "bad"}, ValueError)]
        with patch.object(pymysql, "connect") as connect:
            for env, error in cases:
                with self.subTest(error=error.__name__), self.assertRaises(error):
                    with _temporary_schema(env):
                        self.fail("入口应拒绝")
            connect.assert_not_called()

    def test_real_engine_semantic_fixtures_first_run_against_sqlite(self):
        # 同一输入矩阵先离线建模，避免在真实引擎窗口才发现非法夹具。
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
        from app.infrastructure.persistence.sqlite.document_jobs import SqliteDocumentJobRepository
        from app.infrastructure.persistence.sqlite.files import SqliteDocumentFileRepository
        with TemporaryDirectory() as directory:
            case = MysqlV2IntegrationTests()
            case.backend = SqlitePersistenceBackend(Path(directory) / "fixture.sqlite")
            case.jobs = SqliteDocumentJobRepository(case.backend)
            case.files = SqliteDocumentFileRepository(case.backend)
            case.query = DocumentJobListQuery("T", "C", as_of=NOW)
            case.test_effective_review_filter_order_permissions_summaries_and_all_pages()
            with case.backend.connect() as connection:
                connection.execute("DELETE FROM document_jobs")
                connection.execute("DELETE FROM document_files")
            case.test_full_text_casefold_and_literal_wildcards()

    def test_receipt_error_and_guard_fixtures_first_run_against_sqlite(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
        from app.infrastructure.persistence.sqlite.document_jobs import SqliteDocumentJobRepository
        from app.infrastructure.persistence.sqlite.files import SqliteDocumentFileRepository
        with TemporaryDirectory() as directory:
            case = MysqlV2IntegrationTests()
            case.backend = SqlitePersistenceBackend(Path(directory) / "receipt.sqlite")
            case.jobs = SqliteDocumentJobRepository(case.backend)
            case.files = SqliteDocumentFileRepository(case.backend)
            case.query = DocumentJobListQuery("T", "C", as_of=NOW)
            case.test_receipt_error_prefixes_and_narrow_table_guard()

    def test_create_failure_never_drops_existing_database(self):
        env = dict(MD2WORD_TEST_MYSQL="1", MD2WORD_TEST_MYSQL_HOST="127.0.0.1", MD2WORD_TEST_MYSQL_PORT="33060",
                   MD2WORD_TEST_MYSQL_USER="test", MD2WORD_TEST_MYSQL_PASSWORD="placeholder")
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {"version": "8.4.9"}
        def execute(sql, params=()):
            if sql.startswith("CREATE DATABASE"):
                raise RuntimeError("测试建库失败")
        cursor.execute.side_effect = execute
        with patch.object(pymysql, "connect", return_value=connection), patch("builtins.print"), self.assertRaises(RuntimeError):
            with _temporary_schema(env):
                self.fail("建库失败不得继续")
        self.assertFalse(any(call.args[0].startswith("DROP DATABASE") for call in cursor.execute.call_args_list))
        connection.close.assert_called_once()


class MysqlV2IntegrationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.options, cls.schema = cls.enterClassContext(_temporary_schema(os.environ))
        cls.backend = MysqlPersistenceBackend(MysqlPersistenceConfig(host=cls.options["host"], port=cls.options["port"],
            user=cls.options["user"], password=cls.options["password"], database=cls.schema), initialize=False,
            connect_factory=cls.connect)
        cls.jobs = MysqlDocumentJobRepository(cls.backend)
        cls.files = MysqlDocumentFileRepository(cls.backend)

    @classmethod
    def connect(cls):
        connection = pymysql.connect(**cls.options, database=cls.schema, autocommit=False)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
                cursor.execute("SET SESSION lock_wait_timeout = 10")
        except BaseException:
            connection.close()
            raise
        return connection

    def setUp(self):
        with self.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM document_jobs")
            cursor.execute("DELETE FROM document_files")
        self.query = DocumentJobListQuery("T", "C", as_of=NOW)

    def seed(self, jobs, files=()):
        for file in files:
            self.files.create_document_file(file)
        for job in jobs:
            self.jobs.create_document_job(job)

    def bound(self):
        file = file_record()
        binding = ReviewBinding(generation=0, result_file_id=file.id, binding_state="verified",
            result_sha256=file.checksum_sha256, file_review_source_revision=0, descriptor=review_source_descriptor(file))
        job = job_record(mode="en2zh_pdf_to_word", status="succeeded", stage="completed", result_file_id=file.id,
            review_status="approved", current_review_record_id="review", review_sequence=1, current_review_binding=binding)
        return job, file

    def test_effective_review_filter_order_permissions_summaries_and_all_pages(self):
        bound, file = self.bound()
        jobs = [bound, job_record("unbound", mode="en2zh_pdf_to_word", review_status="approved",
            status="succeeded", stage="completed", result_file_id="missing"),
            job_record("fail", mode="ru2zh_pdf_to_word", review_status="needs_fix", status="failed", stage="failed"),
            job_record("archived", archived_at=NOW), job_record("deleted", deleted_at=NOW),
            job_record("tenant-case", tenant_id="t"), job_record("company-accent", company_id="Ć"),
            job_record("owner-case", created_by="u"), job_record("owner-accent", created_by="Ú")]
        self.seed(jobs, [file])
        queries = [self.query, replace(self.query, created_by="U"), replace(self.query, created_by="u"),
            replace(self.query, include_archived=True), replace(self.query, statuses=("failed",)),
            replace(self.query, created_from=NOW, created_to=NOW), replace(self.query, q="source")]
        queries += [replace(self.query, translation_qa_status=qa) for qa in ("all", "approved", "unreviewed", "needs_fix", "blocked")]
        queries += [replace(self.query, as_of=file.expires_at, translation_qa_status="approved")]
        queries += [replace(self.query, sort=sort, page=page, page_size=2)
            for sort in ("created_at_asc", "created_at_desc", "updated_at_asc", "updated_at_desc")
            for page in range(1, 5)]
        for query in queries:
            with self.subTest(sort=query.sort, page=query.page, qa=query.translation_qa_status, owner=query.created_by):
                self.assertEqual(_result_tuple(self.jobs.query_document_jobs(query)), _baseline(jobs, {file.id: file}, query))

    def test_full_text_casefold_and_literal_wildcards(self):
        jobs = [job_record("search", error_message="x" * 70000 + "Straße Σς İ 中文 %_\\末端"),
                job_record("split", error_code="alpha", error_message="beta")]
        self.seed(jobs)
        if isinstance(self.jobs, MysqlDocumentJobRepository):
            with self.backend.connect() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT JSON_TYPE(JSON_EXTRACT(list_query_json, '$.created_us')) AS created_type, "
                    "JSON_TYPE(JSON_EXTRACT(list_query_json, '$.updated_us')) AS updated_type, "
                    "JSON_TYPE(JSON_EXTRACT(list_query_json, '$.version')) AS version_type FROM document_jobs")
                self.assertTrue(all(row == {"created_type": "UNSIGNED INTEGER", "updated_type": "UNSIGNED INTEGER",
                    "version_type": "INTEGER"} for row in cursor.fetchall()))
        for term in ("strasse", "σσ", "i\u0307", "中文", "%_\\", "末端", "alphabeta", "alpha"):
            query = replace(self.query, q=term)
            try:
                result = self.jobs.query_document_jobs(query)
            except DocumentJobListProjectionUnavailable:
                # 仅测试自产虚构行的类型/长度诊断，不输出 payload、搜索正文或连接凭据。
                from app.infrastructure.persistence.document_job_list_query import _ListSql, _JOB_TEXT, _JOB_FLAGS
                with self.backend.connect() as connection, connection.cursor() as cursor:
                    sql = _ListSql(connection, mysql=True)
                    names = (*_JOB_TEXT, *_JOB_FLAGS, "created_us", "updated_us", "receipt_expiry_us", "version", "search")
                    selected = [sql.kind("list_query_json", name) + f" AS `{name}`" for name in names]
                    selected += [sql.shape("list_query_json", job=True) + " AS ready",
                        sql.number("list_query_json", "version") + " AS projection_version",
                        "JSON_LENGTH(list_query_json, '$.search') AS search_length",
                        *[sql.kind("list_query_json", f"search[{index}]") + f" AS search_{index}" for index in range(5)]]
                    cursor.execute("SELECT job_id," + ",".join(selected) + " FROM document_jobs")
                    print("MySQL v2 自产投影类型诊断：" + json.dumps(cursor.fetchall(), ensure_ascii=False))
                raise
            self.assertEqual(_result_tuple(result), _baseline(jobs, {}, query))

    def test_collation_alias_file_address_is_error_even_on_empty_page(self):
        job, file = self.bound()
        job = job.model_copy(update={"result_file_id": file.id.upper()})
        self.seed([job], [file])
        with self.assertRaises(ValueError):
            self.files.get_document_file(file.id.upper())
        with self.assertRaises(ValueError):
            self.jobs.query_document_jobs(replace(self.query, page=99))

    def test_transaction_snapshot_keeps_old_job_and_file_until_next_query(self):
        job, file = self.bound()
        self.seed([job], [file])
        fired = False
        original_connect = self.connect
        owner = self
        class CursorProxy:
            def __init__(self, cursor): self.cursor = cursor
            def __enter__(self): self.cursor.__enter__(); return self
            def __exit__(self, *args): return self.cursor.__exit__(*args)
            def __getattr__(self, name): return getattr(self.cursor, name)
            def execute(self, sql, params=()):
                nonlocal fired
                result = self.cursor.execute(sql, params)
                if not fired and sql.lstrip().upper().startswith("SELECT"):
                    fired = True
                    with owner.backend.connect() as connection:
                        owner.jobs._write_job(connection, job.model_copy(update={"error_message": "new-state"}))
                        owner.files._write_file(connection, file.model_copy(update={"status": "expired"}))
                return result
        class ConnectionProxy:
            def __init__(self, connection): self.connection = connection
            def __getattr__(self, name): return getattr(self.connection, name)
            def cursor(self): return CursorProxy(self.connection.cursor())
        def connect():
            connection = original_connect()
            return connection if fired else ConnectionProxy(connection)
        with patch.object(self.backend, "_connect_factory", side_effect=connect):
            before = self.jobs.query_document_jobs(self.query)
        self.assertTrue(fired)
        self.assertEqual(before.items[0].review_status, "approved")
        self.assertIsNone(before.items[0].error_message)
        self.assertEqual(before.observed_results[job.id].status, "uploaded")
        after = self.jobs.query_document_jobs(self.query)
        self.assertEqual(effective_review_job(after.items[0], after.observed_results[job.id], now=NOW).review_status, "unreviewed")
        self.assertEqual(after.items[0].error_message, "new-state")
        self.assertEqual(after.observed_results[job.id].status, "expired")

    def test_double_table_backfill_adds_columns_preserves_raw_and_verifies_all(self):
        job, file = self.bound()
        self.seed([job], [file])
        settings = Settings.model_construct(jobs_repository_backend="mysql", jobs_mysql_host=self.options["host"],
            jobs_mysql_port=self.options["port"], jobs_mysql_user=self.options["user"],
            jobs_mysql_password=self.options["password"], jobs_mysql_database=self.schema,
            jobs_mysql_charset="utf8mb4", jobs_mysql_connect_timeout_seconds=5)
        def rows():
            with self.backend.connect() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT file_id,payload,created_at,updated_at FROM document_files")
                files = cursor.fetchall()
                cursor.execute("SELECT job_id,payload,created_at,updated_at,quality_status,review_status,delivery_status,quality_summary_json FROM document_jobs")
                return files, cursor.fetchall()
        before = rows()
        with self.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("ALTER TABLE document_files DROP COLUMN review_query_json")
            cursor.execute("ALTER TABLE document_jobs DROP COLUMN list_query_json")
        dry = migrate_document_job_list_query(settings, mode="dry-run", mysql_connect_factory=self.connect)
        self.assertEqual(dry["exit_code"], 0)
        self.assertEqual(rows(), before)
        applied = migrate_document_job_list_query(settings, mode="apply", mysql_connect_factory=self.connect)
        self.assertEqual(applied["exit_code"], 0, applied)
        self.assertEqual(rows(), before)
        self.assertEqual(applied["tables"]["document_files"]["schema_added"], ["review_query_json"])
        self.assertEqual(applied["tables"]["document_jobs"]["schema_added"], ["list_query_json"])
        verified = migrate_document_job_list_query(settings, mode="verify", batch_size=1, mysql_connect_factory=self.connect)
        self.assertEqual(verified["exit_code"], 0, verified)
        self.assertTrue(verified["all_ready"])
        self.assertEqual(_result_tuple(self.jobs.query_document_jobs(self.query)), _baseline([job], {file.id: file}, self.query))

    def test_receipt_error_prefixes_and_narrow_table_guard(self):
        """同一紧凑矩阵复验 MySQL 凭据/异常可达性；每个夹具先完整模型验证。"""
        from datetime import datetime, timedelta, timezone
        from app.domains.document_jobs.models import DocumentJobRecord
        from app.domains.document_jobs.review import receipt_identity
        from app.domains.files.models import DocumentFileRecord
        from tests.test_document_job_list_query_v2 import bound_job

        def execute(connection, statement):
            if isinstance(self.jobs, MysqlDocumentJobRepository):
                with connection.cursor() as cursor:
                    cursor.execute(statement)
            else:
                connection.execute(statement)

        def load(item, file):
            # 真实历史记录允许 revision>0；直接共享 writer 保存，不让 create 重置序号。
            item = DocumentJobRecord.model_validate(item.model_dump(mode="python"))
            file = DocumentFileRecord.model_validate(file.model_dump(mode="python"))
            with self.backend.connect() as connection:
                execute(connection, "DELETE FROM document_jobs")
                execute(connection, "DELETE FROM document_files")
                self.files._write_file(connection, file, create=True)
            self.jobs.create_document_job(item)
            return item, file

        def check(item, file, *, error=None, query=None):
            item, file = load(item, file)
            query = query or self.query
            if error is not None:
                with self.assertRaises(error):
                    _baseline([item], {file.id: file}, query)
                with self.assertRaises(error):
                    self.jobs.query_document_jobs(query)
                return None
            actual = self.jobs.query_document_jobs(query)
            self.assertEqual(_result_tuple(actual), _baseline([item], {file.id: file}, query))
            return actual

        file = file_record()
        item = bound_job(file, receipt=True)
        with self.subTest(branch="receipt_present_valid"):
            self.assertEqual(check(item, file).translation_qa_summary["approved"], 1)
        changed_name = DocumentFileRecord.model_validate({**file.model_dump(mode="python"), "original_filename": "renamed.docx"})
        with self.subTest(branch="receipt_identity_mismatch"):
            self.assertEqual(check(item, changed_name).translation_qa_summary["unreviewed"], 1)

        mixed_raw = item.model_dump(mode="python")
        mixed_raw["prepared_result"]["file"]["expires_at"] = file.expires_at.replace(tzinfo=None)
        mixed = DocumentJobRecord.model_validate(mixed_raw)
        mixed_raw["current_review_binding"]["receipt_sha256"] = receipt_identity(mixed)
        mixed_raw["delivery_status"] = "published"
        mixed = DocumentJobRecord.model_validate(mixed_raw)
        with self.subTest(branch="published_receipt_mixed_expiry_error_before_filters"):
            check(mixed, file, error=TypeError, query=replace(self.query, page=99, q="no-match"))
        changed_revision = DocumentFileRecord.model_validate({**file.model_dump(mode="python"), "review_source_revision": 1})
        with self.subTest(branch="revision_short_circuits_receipt_error"):
            self.assertEqual(check(mixed, changed_revision).translation_qa_summary["approved"], 1)

        quality = DocumentJobRecord.model_validate({**item.model_dump(mode="python"), "quality_summary": {"checks_v1": []}})
        with self.subTest(branch="quality_error_before_filters"):
            check(quality, file, error=ValueError, query=replace(self.query, page=99, q="no-match"))
        with self.subTest(branch="invisible_quality_error_not_reached"):
            self.assertEqual(check(quality, file, query=replace(self.query, created_by="another-owner")).total, 0)
        published_quality = DocumentJobRecord.model_validate({**quality.model_dump(mode="python"), "delivery_status": "published"})
        with self.subTest(branch="published_quality_owner_short_circuit"):
            self.assertEqual(check(published_quality, file).translation_qa_summary["approved"], 1)

        overflow = DocumentFileRecord.model_validate({**file.model_dump(mode="python"),
            "expires_at": datetime(9999, 12, 31, 23, tzinfo=timezone(-timedelta(hours=14)))})
        with self.subTest(branch="live_descriptor_overflow"):
            check(item, overflow, error=OverflowError)
        overflow_revision = DocumentFileRecord.model_validate({**overflow.model_dump(mode="python"), "review_source_revision": 1})
        with self.subTest(branch="revision_short_circuits_descriptor_overflow"):
            self.assertEqual(check(item, overflow_revision).translation_qa_summary["unreviewed"], 1)

        with self.subTest(branch="narrow_guard_current_changed_and_unavailable"):
            item, _ = load(item, file)
            changed_source = DocumentJobRecord.model_validate({**item.model_dump(mode="python"), "source_file_id": "changed-source"})
            with patch.object(DocumentJobRecord, "model_validate_json", side_effect=AssertionError("窄读不得解码任务 payload")):
                self.assertTrue(self.jobs.is_document_job_table_evidence_snapshot_current(item))
                self.assertFalse(self.jobs.is_document_job_table_evidence_snapshot_current(changed_source))
                with self.backend.connect() as connection:
                    execute(connection, "UPDATE document_jobs SET list_query_json = NULL")
                with self.assertRaises(DocumentJobListProjectionUnavailable):
                    self.jobs.is_document_job_table_evidence_snapshot_current(item)
