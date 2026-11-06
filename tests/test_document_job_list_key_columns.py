"""拆列前后用权威 Python 语义对照；大 key 不进入列表 JSON。"""
from dataclasses import replace
import json
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
from types import SimpleNamespace
from unittest import TestCase

from app.core.config import Settings
from app.domains.document_jobs.list_query import (
    DocumentJobListProjectionUnavailable, DocumentJobListQuery,
    document_job_list_projection_from_raw, document_file_review_projection_from_raw,
    query_document_job_records,
)
from app.domains.document_jobs.models import DocumentJobPreparedResult
from app.domains.document_jobs.review import ReviewBinding, ReviewSubmission, receipt_identity
from app.domains.files.result_registration import review_source_descriptor
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.infrastructure.persistence.sqlite.document_jobs import SqliteDocumentJobRepository
from app.infrastructure.persistence.sqlite.files import SqliteDocumentFileRepository
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.infrastructure.persistence.file.document_jobs import FileDocumentJobRepository
from app.infrastructure.persistence.file.files import FileDocumentFileRepository
from scripts.ops.migrate_document_job_list_query import migrate_document_job_list_query
from tests.test_document_job_list_query_v2 import NOW, job, word


def result_values(result):
    return ([item.id for item in result.items], result.total, result.summary,
            result.filtered_summary, result.translation_qa_summary)


def seed_large_records(jobs, files):
    """长公共前缀后的单字符、大小写、空白差异必须仍可见。"""
    records, current_files = [], {}
    text = "合成é\\\"" * 8192
    for index, case in enumerate(("equal", "tail", "case", "space", "receipt", "missing", "no-receipt")):
        identity = f"large-{index}"
        source = word(identity + "-word", identity,
            object_key=f"document-files/T/{identity}-word/result.docx",
            metadata={"large": text + "A", "number": 1})
        receipt = None if case == "no-receipt" else DocumentJobPreparedResult(
            generation=0, document_ir_file_id="ir", file=source)
        record = jobs.create_document_job(job(identity, mode="en2zh_pdf_to_word", status="succeeded",
            stage="completed", quality_status="passed", result_file_id=source.id,
            document_ir_file_id="ir" if receipt else None, prepared_result=receipt))
        binding = ReviewBinding(generation=0, result_file_id=source.id, binding_state="verified",
            result_sha256=source.checksum_sha256, file_review_source_revision=0,
            descriptor=review_source_descriptor(source), receipt_sha256=receipt_identity(record))
        record = jobs.update_document_job_review_if_current(identity, submission=ReviewSubmission(
            record_id=identity + "-review", status="approved", reviewed_by="U", reviewer_role="operator",
            reviewed_at=NOW, binding=binding))
        records.append(record)
        if case == "missing":
            continue
        changes = {}
        if case in {"tail", "case", "space"}:
            suffix = {"tail": "B", "case": "a", "space": "A "}[case]
            changes["metadata"] = {"large": text + suffix, "number": 1}
        elif case == "receipt":
            changes["original_filename"] = "凭据名不同.docx"
        current = files.create_document_file(source.model_copy(update=changes))
        current_files[current.id] = current
    records.append(jobs.create_document_job(job("direct")))
    return records, current_files


class LargeKeyAssertions:
    """SQL 迁移前后的比较合同可由 SQLite 和显式启用的 MySQL 共用。"""

    def execute(self, statement, params=()):
        with self.backend.connect() as connection:
            if self.mysql:
                with connection.cursor() as cursor:
                    cursor.execute(statement, params)
                    return cursor.fetchall()
            return connection.execute(statement, params).fetchall()

    def migrate(self, mode):
        kwargs = {"mysql_connect_factory": self.connect} if self.mysql else {}
        return migrate_document_job_list_query(self.settings, mode=mode, batch_size=100, **kwargs)

    def test_large_keys_migrate_compare_and_measure(self):
        records, files = seed_large_records(self.jobs, self.files)
        query = DocumentJobListQuery("T", "C", as_of=NOW)
        marker = "%s" if self.mysql else "?"
        old_sizes = {"document_jobs": [], "document_files": []}
        for table, identity, column, builder, keys in (
            ("document_jobs", "job_id", "list_query_json", document_job_list_projection_from_raw,
             ("list_descriptor_key", "list_receipt_key", "list_table_snapshot_key")),
            ("document_files", "file_id", "review_query_json", document_file_review_projection_from_raw,
             ("review_descriptor_key", "review_receipt_key")),
        ):
            for row in self.execute(f"SELECT {identity}, payload FROM {table}"):
                old_json = json.dumps(builder(row["payload"]), ensure_ascii=False)
                old_sizes[table].append(len(old_json.encode()))
                self.execute(f"UPDATE {table} SET {column}={marker}, "
                    + ", ".join(key + "=NULL" for key in keys) + f" WHERE {identity}={marker}",
                    (old_json, row[identity]))
        with self.assertRaises(DocumentJobListProjectionUnavailable):
            self.jobs.query_document_jobs(query)
        with self.assertRaises(DocumentJobListProjectionUnavailable):
            self.jobs.is_document_job_table_evidence_snapshot_current(records[0])
        before = {table: [dict(row) for row in self.execute(f"SELECT * FROM {table}")]
                  for table in old_sizes}
        self.assertEqual(self.migrate("dry-run")["exit_code"], 0)
        for table in old_sizes:
            self.assertEqual([dict(row) for row in self.execute(f"SELECT * FROM {table}")], before[table])
        report = self.migrate("apply")
        self.assertEqual(report["exit_code"], 0, report)
        self.assertTrue(self.migrate("verify")["all_ready"])
        first = {table: [dict(row) for row in self.execute(f"SELECT * FROM {table}")]
                 for table in old_sizes}
        self.assertEqual(self.migrate("apply")["exit_code"], 0)
        sizes = {}
        for table, column in (("document_jobs", "list_query_json"), ("document_files", "review_query_json")):
            rows = [dict(row) for row in self.execute(f"SELECT * FROM {table}")]
            self.assertEqual(rows, first[table])
            new_sizes = [len(row[column].encode()) for row in rows]
            sizes[table] = dict(rows=len(rows), before_mean_bytes=sum(old_sizes[table]) / len(rows),
                               after_mean_bytes=sum(new_sizes) / len(rows))
            self.assertLess(sum(new_sizes), sum(old_sizes[table]) / 10)
            for row in rows:
                self.assertTrue({"descriptor_key", "receipt_key", "table_snapshot_key"}.isdisjoint(json.loads(row[column])))
        queries = [query, replace(query, page=99), replace(query, created_by="U"), replace(query, q="large")]
        queries += [replace(query, translation_qa_status=qa) for qa in ("all", "approved", "unreviewed", "needs_fix", "blocked")]
        queries += [replace(query, sort=sort, page=page, page_size=2)
                    for sort in ("created_at_asc", "created_at_desc", "updated_at_asc", "updated_at_desc")
                    for page in range(1, 6)]
        oracle_files = SimpleNamespace(get_document_file=files.get)
        for candidate in queries:
            with self.subTest(query=candidate):
                expected = query_document_job_records(records, candidate, file_repository=oracle_files)
                self.assertEqual(result_values(self.jobs.query_document_jobs(candidate)), result_values(expected))
        self.assertEqual(self.jobs.query_document_jobs(query).translation_qa_summary["approved"], 2)
        self.assertTrue(self.jobs.is_document_job_table_evidence_snapshot_current(records[0]))
        self.assertFalse(self.jobs.is_document_job_table_evidence_snapshot_current(
            records[0].model_copy(update={"source_file_id": "changed"})))
        print("大 key 拆列体积：" + json.dumps(sizes, ensure_ascii=False))
        if self.mysql:
            self._measure_json_parse(before)

    def _measure_json_parse(self, before):
        """同一引擎测量相同筛选表达式；只打印耗时，不设脆弱的速度断言。"""
        statement = "SELECT COUNT(*) AS n FROM document_jobs WHERE JSON_UNQUOTE(JSON_EXTRACT(list_query_json, '$.tenant_id')) = 'T'"
        def measure():
            samples = []
            for _ in range(7):
                started = perf_counter()
                self.execute(statement)
                samples.append((perf_counter() - started) * 1000)
            return median(samples)
        after_ms = measure()
        try:
            for row in before["document_jobs"]:
                self.execute("UPDATE document_jobs SET list_query_json=%s WHERE job_id=%s",
                             (row["list_query_json"], row["job_id"]))
            before_ms = measure()
        finally:
            self.assertEqual(self.migrate("apply")["exit_code"], 0)
        print("MySQL 同表达式 JSON 解析耗时：" + json.dumps(dict(before_median_ms=before_ms, after_median_ms=after_ms)))


class SqliteLargeKeyTests(LargeKeyAssertions, TestCase):
    mysql = False

    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        path = Path(directory) / "keys.sqlite"
        self.backend = SqlitePersistenceBackend(path)
        self.jobs = SqliteDocumentJobRepository(self.backend)
        self.files = SqliteDocumentFileRepository(self.backend)
        self.settings = Settings.model_construct(jobs_repository_backend="database", jobs_metadata_database_path=str(path))


class FileLargeKeyTests(TestCase):
    def test_file_backend_keeps_authoritative_semantics_without_projection_migration(self):
        directory = self.enterContext(TemporaryDirectory())
        backend = FilePersistenceBackend(Path(directory))
        jobs, files = FileDocumentJobRepository(backend), FileDocumentFileRepository(backend)
        records, current_files = seed_large_records(jobs, files)
        query = DocumentJobListQuery("T", "C", as_of=NOW)
        expected = query_document_job_records(records, query,
            file_repository=SimpleNamespace(get_document_file=current_files.get))
        actual = jobs.query_document_jobs(query)
        self.assertEqual(result_values(actual), result_values(expected))
        self.assertEqual(actual.translation_qa_summary["approved"], 2)
        self.assertTrue(jobs.is_document_job_table_evidence_snapshot_current(records[0]))
        self.assertFalse(jobs.is_document_job_table_evidence_snapshot_current(
            records[0].model_copy(update={"source_file_id": "changed"})))
        for path in backend.document_jobs_dir.glob("*/job.json"):
            self.assertNotIn("list_query_json", json.loads(path.read_text()))
