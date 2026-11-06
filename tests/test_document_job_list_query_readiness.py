"""列表请求内就绪校验：统计域、跨请求损坏和独立扫描消除。"""
from dataclasses import replace
from datetime import timedelta
from contextlib import nullcontext
import json
from types import SimpleNamespace
from unittest import TestCase

from app.core.errors import ApiError
from app.domains.document_jobs.list_query import DocumentJobListProjectionUnavailable
from app.infrastructure.persistence.document_job_list_query import query_document_jobs_sql
from tests import test_document_job_list_query_v2 as sql_fixtures
from tests import test_document_job_list_query_v2_service as service_fixtures


class DocumentJobListReadinessTests(TestCase):
    def setUp(self):
        self.fixture = sql_fixtures.ListSqlV2Tests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.connection = self.fixture.connection
        self.query = self.fixture.query

    def test_eleven_selects_for_page_empty_page_and_empty_result(self):
        self.fixture.seed([sql_fixtures.job()])
        for query, total, size in ((self.query, 1, 1), (replace(self.query, page=99), 1, 0),
                                   (replace(self.query, q="absent"), 0, 0)):
            with self.subTest(query=query):
                statements = []
                self.connection.set_trace_callback(statements.append)
                result = self.fixture.run_query(query)
                self.connection.set_trace_callback(None)
                selects = [statement for statement in statements if statement.startswith("SELECT")]
                self.assertEqual((result.total, len(result.items)), (total, size))
                self.assertEqual(len(selects), 11)
                self.assertIn("AS unavailable", selects[0])
                for statement in selects[1:]:
                    self.assertNotIn("JSON_EXTRACT(f.review_query_json,", statement)
                self.assertFalse(any(statement.startswith("SELECT COUNT(*) AS n FROM document_jobs WHERE")
                                     or statement.startswith("SELECT COUNT(*) AS n FROM document_files WHERE")
                                     for statement in selects))
                plan = self.connection.execute("EXPLAIN QUERY PLAN " + selects[0]).fetchall()
                details = [row["detail"] for row in plan]
                self.assertTrue(any("SEARCH f USING INDEX" in detail for detail in details), details)
                self.assertFalse(any("SCAN f" in detail for detail in details), details)

    def test_corruption_before_first_query_and_after_success_covers_full_summary_scope(self):
        file = sql_fixtures.word()
        self.fixture.seed([sql_fixtures.bound_job(file)], [file])
        queries = (self.query, replace(self.query, page=99), replace(self.query, q="absent"),
                   replace(self.query, statuses=("failed",)),
                   replace(self.query, created_from=sql_fixtures.NOW + timedelta(days=1)),
                   replace(self.query, translation_qa_status="blocked"))
        for table, column, missing in (("document_jobs", "list_query_json", "status"),
                                       ("document_files", "review_query_json", "revision")):
            original = self.connection.execute(f"SELECT {column} FROM {table}").fetchone()[0]
            incomplete = json.loads(original)
            del incomplete[missing]
            wrong_version = {**json.loads(original), "version": 99}
            for warm in (False, True):
                for query in queries:
                    for invalid in (None, "{broken", "null", "[]", json.dumps(incomplete), json.dumps(wrong_version)):
                        with self.subTest(table=table, warm=warm, query=query, invalid=invalid):
                            self.connection.execute(f"UPDATE {table} SET {column} = ?", (original,))
                            if warm:
                                self.assertEqual(self.fixture.run_query().total, 1)
                            self.connection.execute(f"UPDATE {table} SET {column} = ?", (invalid,))
                            with self.assertRaises(DocumentJobListProjectionUnavailable):
                                self.fixture.run_query(query)
            self.connection.execute(f"UPDATE {table} SET {column} = ?", (original,))

    def test_missing_keys_after_success_still_fail_outside_filtered_page(self):
        file = sql_fixtures.word()
        self.fixture.seed([sql_fixtures.bound_job(file)], [file])
        for table, columns in (
            ("document_jobs", ("list_descriptor_key", "list_receipt_key", "list_table_snapshot_key")),
            ("document_files", ("review_descriptor_key", "review_receipt_key")),
        ):
            for column in columns:
                original = self.connection.execute(f"SELECT {column} FROM {table}").fetchone()[0]
                self.assertEqual(self.fixture.run_query().total, 1)
                self.connection.execute(f"UPDATE {table} SET {column} = NULL")
                for query in (replace(self.query, q="absent"), replace(self.query, page=99),
                              replace(self.query, statuses=("failed",))):
                    with self.subTest(column=column, query=query):
                        with self.assertRaises(DocumentJobListProjectionUnavailable):
                            self.fixture.run_query(query)
                self.connection.execute(f"UPDATE {table} SET {column} = ?", (original,))

    def test_missing_or_wrong_visibility_fields_do_not_silently_hide_jobs(self):
        self.fixture.seed([sql_fixtures.job()])
        original = json.loads(self.connection.execute("SELECT list_query_json FROM document_jobs").fetchone()[0])
        for field in ("tenant_id", "company_id", "created_by", "deleted", "archived"):
            for mutation in ("missing", None, [], True, 2):
                with self.subTest(field=field, mutation=mutation):
                    projection = dict(original)
                    if mutation == "missing":
                        del projection[field]
                    else:
                        projection[field] = mutation
                    self.connection.execute("UPDATE document_jobs SET list_query_json = ?", (json.dumps(projection),))
                    with self.assertRaises(DocumentJobListProjectionUnavailable):
                        self.fixture.run_query(replace(self.query, created_by="U"))

    def test_reliably_hidden_jobs_and_unrelated_files_skip_full_shape_validation(self):
        self.fixture.seed([sql_fixtures.job("visible")])
        for changes in ({"tenant_id": "other"}, {"company_id": "other"}, {"created_by": "other"},
                        {"archived_at": sql_fixtures.NOW}, {"deleted_at": sql_fixtures.NOW}):
            with self.subTest(changes=changes):
                self.connection.execute("DELETE FROM document_jobs WHERE job_id <> 'visible'")
                self.connection.execute("DELETE FROM document_files")
                file = sql_fixtures.word("hidden-file", "hidden")
                self.fixture.seed([sql_fixtures.bound_job(file, **changes)], [file])
                projection = json.loads(self.connection.execute(
                    "SELECT list_query_json FROM document_jobs WHERE job_id = 'hidden'").fetchone()[0])
                del projection["table_snapshot_key_comparable"]
                projection["version"] = 99
                self.connection.execute("UPDATE document_jobs SET list_query_json = ? WHERE job_id = 'hidden'",
                                        (json.dumps(projection),))
                self.connection.execute("UPDATE document_files SET review_query_json = '{broken'")
                result = self.fixture.run_query(replace(self.query, created_by="U"))
                self.assertEqual([item.id for item in result.items], ["visible"])
        self.connection.execute("DELETE FROM document_jobs")
        self.assertEqual(self.fixture.run_query().total, 0)

    def test_file_shape_is_checked_before_observation_gate_and_identity_error(self):
        file = sql_fixtures.word(tenant_id="other", status="pending_upload")
        self.fixture.seed([sql_fixtures.bound_job(file)], [file])
        projection = json.loads(self.connection.execute("SELECT review_query_json FROM document_files").fetchone()[0])
        projection["id"] = "wrong"
        self.connection.execute("UPDATE document_files SET review_query_json = ?", (json.dumps(projection),))
        with self.assertRaisesRegex(ValueError, "文件寻址与 payload 的 id 不一致"):
            self.fixture.run_query(replace(self.query, page=99))
        del projection["revision"]
        self.connection.execute("UPDATE document_files SET review_query_json = ?", (json.dumps(projection),))
        with self.assertRaises(DocumentJobListProjectionUnavailable):
            self.fixture.run_query(replace(self.query, page=99))

    def test_unfinished_job_does_not_validate_unobserved_result_file(self):
        file = sql_fixtures.word()
        self.fixture.seed([sql_fixtures.bound_job(file, status="running", stage="rendering", review_status="needs_fix")], [file])
        self.connection.execute("UPDATE document_files SET review_query_json = '{broken'")
        result = self.fixture.run_query()
        self.assertEqual(result.total, 1)
        self.assertIsNone(result.observed_results["a"])

    def test_mysql_preflight_error_priority_and_later_file_extractions_are_safe(self):
        for unavailable, mismatch, error in ((1, 1, DocumentJobListProjectionUnavailable),
                                             (0, 1, ValueError), (0, 0, None)):
            statements = []

            class Cursor:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    pass

                def execute(self, statement, params):
                    statements.append((statement, params))

                def fetchall(self):
                    statement = statements[-1][0]
                    return ([{"unavailable": unavailable, "n": mismatch}]
                            if "COUNT(" in statement and "GROUP BY" not in statement else [])

            with self.subTest(unavailable=unavailable, mismatch=mismatch), (
                    self.assertRaises(error) if error else nullcontext()):
                query_document_jobs_sql(SimpleNamespace(cursor=Cursor), replace(self.query, created_by="U"), mysql=True)
            self.assertEqual(len(statements), 1 if error else 11)
            for statement, params in statements[1:]:
                # 防止后续查询绕过保护，不能依赖 MySQL 的 WHERE 求值顺序。
                self.assertNotIn("JSON_EXTRACT(f.review_query_json,", statement)
                self.assertEqual(statement.count("%s"), len(params))
            if error is None:
                self.assertTrue(any("JSON_EXTRACT(CASE WHEN JSON_VALID(f.review_query_json) "
                                    "THEN f.review_query_json END," in statement
                                    for statement, _ in statements[1:]))
            statement, params = statements[0]
            self.assertEqual(params, ("T", "C", "U"))
            self.assertIn("ON f.file_id = CASE WHEN JSON_VALID(j.list_query_json)", statement)
            self.assertIn("COUNT(CASE WHEN JSON_VALID(f.review_query_json)", statement)
            self.assertIn("'UNSIGNED INTEGER'", statement)
            self.assertIn("AS BINARY", statement)
            self.assertEqual(statement.count("%s"), len(params))

    def test_real_initialized_repository_service_rejects_corruption_after_success(self):
        fixture = service_fixtures.DocumentJobListV2ServiceTests()
        for table, column in (("document_jobs", "list_query_json"), ("document_files", "review_query_json")):
            with self.subTest(table=table), fixture.environment("sqlite") as (jobs, files, service):
                fixture.verified(jobs, files)
                self.assertEqual(fixture.listing(service).total, 1)
                with jobs.backend.connect() as connection:
                    connection.execute(f"UPDATE {table} SET {column} = NULL")
                with self.assertRaises(ApiError) as error:
                    fixture.listing(service, q="absent")
                self.assertEqual((error.exception.status_code, error.exception.code), (503, "service_unavailable"))
