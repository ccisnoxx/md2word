"""在隔离 MySQL 上验证参数值列同包接纳、审批和发布的真实事务竞争。"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from importlib.metadata import version
import json
import os
from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

import pymysql

from app.domains.document_jobs.new_generation import (
    GENERATION_REQUESTS_ENVELOPE, NewGenerationCommitUnknownError, NewGenerationConflict,
)
from app.domains.document_jobs.review import digest
from app.domains.resources.models import utc_now
from app.infrastructure.persistence.factory import build_mysql_persistence_adapters
from app.infrastructure.persistence.mysql import document_jobs as mysql_jobs
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.services.preview.models import PreviewPolicy
from tests import test_fastapi_jobs_backend as fixtures
from tests import test_online_table_value_generation_store as replay_fixtures
from tests import test_online_table_value_pdf_binding as delivery_fixtures
from tests import test_online_table_value_quality as quality_fixtures
from tests.document_job_list_query_v2_publication_fixtures import RecordingPreviewProvider, V2PublicationFixture
from tests.document_job_use_case_support import replace_dependency
from tests.test_document_job_list_query_v2_mysql import _temporary_schema


class RolloutMysqlTests(V2PublicationFixture, TestCase):
    _verified_submission = replay_fixtures.OnlineTableValueGenerationStoreTests._verified_submission
    _install_review = quality_fixtures.OnlineTableValueQualityTests._install_review
    _approve = quality_fixtures.OnlineTableValueQualityTests._approve
    try_publish = delivery_fixtures.OnlineTableValuePdfBindingTests.try_publish

    @classmethod
    def setUpClass(cls):
        cls.options, cls.schema = cls.enterClassContext(_temporary_schema(os.environ))
        cls.config = MysqlPersistenceConfig(
            host=cls.options["host"], port=cls.options["port"], user=cls.options["user"],
            password=cls.options["password"], database=cls.schema,
        )
        cls.adapters = build_mysql_persistence_adapters(cls.config, connect_factory=cls.connect)
        cls.backend = cls.adapters.document_job_repository.backend
        with cls.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT VERSION() AS version, @@session.transaction_isolation AS isolation, "
                "@@session.autocommit AS autocommit, @@session.innodb_lock_wait_timeout AS lock_timeout"
            )
            session = cursor.fetchone()
            cursor.execute(
                "SELECT t.TABLE_NAME AS name, t.ENGINE AS engine, t.TABLE_COLLATION AS collation, "
                "s.COLUMN_NAME AS primary_key FROM information_schema.tables AS t "
                "JOIN information_schema.statistics AS s USING (table_schema, table_name) "
                "WHERE t.TABLE_SCHEMA = %s AND s.INDEX_NAME = 'PRIMARY' AND t.TABLE_NAME IN "
                "('document_jobs','document_files','document_job_review_records','document_job_publications','audit_events') "
                "ORDER BY t.TABLE_NAME", (cls.schema,),
            )
            structure = cursor.fetchall()
        if len(structure) != 5 or any(table["engine"] != "InnoDB" for table in structure):
            raise AssertionError("验收所需的五张 InnoDB 表及其主键必须齐全。")
        if session["autocommit"] != 0:
            raise AssertionError("写连接必须关闭 autocommit。")
        print("参数值列锁验收环境 " + json.dumps({
            "driver": version("PyMySQL"), **session, "tables": structure,
        }, ensure_ascii=False), flush=True)

    @classmethod
    def connect(cls):
        return pymysql.connect(**cls.options, database=cls.schema, autocommit=False)

    def _build_runtime(self, root, kind):
        self.assertEqual(kind, "mysql")
        return fixtures.build_test_runtime(
            root, repository_factory=lambda _: self.adapters, jobs_repository_backend="mysql",
            jobs_artifact_storage_backend="local_object", auth_jwt_secret_key="test-jwt-secret",
            auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
        )

    @contextmanager
    def _pause_after_write(self, repository, method, *, failure=None):
        """真实 SQL 执行后持锁，另一条连接可被观察为等待。"""
        acquired, release = Queue(maxsize=1), Event()
        original = getattr(repository, method)

        def pause(connection, *args, **kwargs):
            result = original(connection, *args, **kwargs)
            acquired.put(connection.thread_id(), timeout=8)
            if not release.wait(8):
                raise RuntimeError("测试持锁方等待释放超时。")
            if failure is not None:
                raise failure
            return result

        with patch.object(repository, method, side_effect=pause):
            try:
                yield acquired, release
            finally:
                release.set()

    def _observe_primary_wait(self, *, holder, table):
        """直接从 InnoDB 等待图观察请求涉及的行锁。"""
        started = monotonic()
        with self.backend.connect() as connection, connection.cursor() as cursor:
            while monotonic() - started <= 4:
                cursor.execute(
                    "SELECT requested.INDEX_NAME AS index_name, requested.LOCK_TYPE AS lock_type, "
                    "requester.PROCESSLIST_ID AS requester FROM performance_schema.data_lock_waits AS wait "
                    "JOIN performance_schema.data_locks AS requested "
                    "ON requested.ENGINE_LOCK_ID = wait.REQUESTING_ENGINE_LOCK_ID "
                    "JOIN performance_schema.threads AS blocker ON blocker.THREAD_ID = wait.BLOCKING_THREAD_ID "
                    "JOIN performance_schema.threads AS requester ON requester.THREAD_ID = wait.REQUESTING_THREAD_ID "
                    "WHERE blocker.PROCESSLIST_ID = %s AND requested.OBJECT_SCHEMA = %s "
                    "AND requested.OBJECT_NAME = %s", (holder, self.schema, table),
                )
                row = cursor.fetchone()
                if row is not None:
                    self.assertNotEqual(row["requester"], holder)
                    self.assertEqual((row["index_name"], row["lock_type"]), ("PRIMARY", "RECORD"))
                    elapsed_ms = round((monotonic() - started) * 1000)
                    print(f"InnoDB 等待 {table}.PRIMARY RECORD，A/B 独立连接，观察用时 {elapsed_ms} ms", flush=True)
                    return
                sleep(0.02)
        self.fail(f"未在真实 InnoDB 等待图中观察到 {table} 主键行锁。")

    def _committed(self, job_id):
        with self.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM document_jobs WHERE job_id = %s", (job_id,))
            job = json.loads(cursor.fetchone()["payload"])
            cursor.execute(
                "SELECT audit_id FROM audit_events WHERE JSON_UNQUOTE(JSON_EXTRACT(payload, '$.target_id')) = %s "
                "AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.action')) = 'document_job.new_generation.accepted'",
                (job_id,),
            )
            return job, [row["audit_id"] for row in cursor.fetchall()]

    def _assert_single_acceptance(self, current, submission):
        current_payload, audit = self._committed(current.id)
        self.assertEqual(current_payload["retry_count"], current.retry_count + 1)
        self.assertEqual(current_payload["stage"], "parsed")
        self.assertEqual(current_payload["mineru_raw_result_file_id"], current.mineru_raw_result_file_id)
        self.assertIsNone(current_payload["result_file_id"])
        self.assertEqual(list(current_payload[GENERATION_REQUESTS_ENVELOPE]), [submission.request_id])
        self.assertEqual(audit, [submission.audit_id])

    def _assert_no_acceptance(self, current):
        current_payload, audit = self._committed(current.id)
        self.assertEqual(current_payload["retry_count"], current.retry_count)
        self.assertEqual(current_payload["result_file_id"], current.result_file_id)
        self.assertFalse(current_payload.get(GENERATION_REQUESTS_ENVELOPE))
        self.assertEqual(audit, [])

    def test_same_and_different_uuids_observe_the_committed_generation_after_wait(self):
        for same in (True, False):
            with self.subTest(same_uuid=same), self._verified_submission("mysql") as (jobs, _, current, submission):
                alternate = submission if same else submission.model_copy(update={
                    "request_id": str(uuid4()), "audit_id": "audit_" + uuid4().hex,
                })

                def accept(request):
                    return jobs.accept_document_job_new_generation(current.id, submission=request, max_retries=3)

                with ThreadPoolExecutor(max_workers=2) as pool, self._pause_after_write(jobs, "_write_job") as (
                    acquired, release,
                ):
                    winner = pool.submit(accept, submission)
                    holder = acquired.get(timeout=8)
                    contender = pool.submit(accept, alternate)
                    self._observe_primary_wait(holder=holder, table="document_jobs")
                    self._assert_no_acceptance(current)
                    release.set()
                    receipt, _, replayed = winner.result(timeout=8)
                    self.assertFalse(replayed)
                    if same:
                        retry, _, replayed = contender.result(timeout=8)
                        self.assertTrue(replayed)
                        self.assertEqual(retry, receipt)
                    else:
                        with self.assertRaises(NewGenerationConflict) as rejected:
                            contender.result(timeout=8)
                        self.assertEqual(rejected.exception.reason_code, "new_generation_state_invalid")
                self._assert_single_acceptance(current, submission)
                with self.assertRaises(NewGenerationConflict) as changed:
                    accept(submission.model_copy(update={
                        "table_value_column_request_sha256": digest("同 UUID 的另一份人工核定"),
                    }))
                self.assertEqual(changed.exception.reason_code, "new_generation_request_conflict")
                with self.assertRaises(NewGenerationConflict) as late:
                    jobs.get_document_job_table_value_column_replay(current.id, current.retry_count)
                self.assertEqual(late.exception.reason_code, "new_generation_source_changed")
                self.assertIsNone(jobs.update_document_job_if_current(
                    current.id, allowed_statuses={"running"}, allowed_stages={"parsed"},
                    expected_retry_count=current.retry_count, progress=77,
                ))
                self.assertEqual(jobs.get_document_job_table_value_column_replay(current.id, receipt.accepted_generation),
                                 submission.table_value_column_replay)

    def test_dependency_reservation_commit_rollback_and_expiry_while_waiting(self):
        for outcome in ("commit", "rollback", "expire"):
            with self.subTest(outcome=outcome), self._verified_submission("mysql") as (jobs, files, current, submission):
                report = next(file for file in submission.table_value_column_files if file.file_type == "quality_report")
                now = utc_now()
                if outcome == "expire":
                    report = files.update_document_file(report.id, expires_at=now + timedelta(seconds=5))
                    submission = submission.model_copy(update={"table_value_column_files": tuple(
                        report if file.id == report.id else file for file in submission.table_value_column_files
                    )})
                rollback = RuntimeError("模拟锁持有方回滚。") if outcome != "commit" else None
                with ThreadPoolExecutor(max_workers=2) as pool, patch.object(mysql_jobs, "utc_now", side_effect=lambda: now):
                    with self._pause_after_write(files, "_write_file", failure=rollback) as (acquired, release):
                        claim = pool.submit(files.reserve_document_file_deletion, report.id, claim_id="fixture-claim", now=now)
                        holder = acquired.get(timeout=8)
                        contender = pool.submit(
                            jobs.accept_document_job_new_generation, current.id, submission=submission, max_retries=3,
                        )
                        self._observe_primary_wait(holder=holder, table="document_files")
                        if outcome == "expire":
                            now = report.expires_at + timedelta(seconds=1)
                        release.set()
                        if rollback is None:
                            self.assertIsNotNone(claim.result(timeout=8).deletion_claim)
                        else:
                            with self.assertRaisesRegex(RuntimeError, "模拟锁持有方回滚"):
                                claim.result(timeout=8)
                        if outcome == "rollback":
                            self.assertEqual(contender.result(timeout=8)[0].accepted_generation, current.retry_count + 1)
                        else:
                            with self.assertRaises(NewGenerationConflict) as rejected:
                                contender.result(timeout=8)
                            self.assertEqual(rejected.exception.reason_code, "new_generation_source_changed")
                if outcome == "rollback":
                    self._assert_single_acceptance(current, submission)
                else:
                    self._assert_no_acceptance(current)
                self.assertEqual(files.get_document_file(report.id).deletion_claim is not None, outcome == "commit")

    def test_file_claim_waits_until_same_package_acceptance_commits(self):
        with self._verified_submission("mysql") as (jobs, files, current, submission):
            report = next(file for file in submission.table_value_column_files if file.file_type == "quality_report")
            with ThreadPoolExecutor(max_workers=2) as pool, self._pause_after_write(jobs, "_write_job") as (
                acquired, release,
            ):
                acceptance = pool.submit(
                    jobs.accept_document_job_new_generation, current.id, submission=submission, max_retries=3,
                )
                holder = acquired.get(timeout=8)
                claim = pool.submit(files.reserve_document_file_deletion, report.id, claim_id="fixture-claim", now=utc_now())
                self._observe_primary_wait(holder=holder, table="document_files")
                self.assertIsNone(files.get_document_file(report.id).deletion_claim)
                release.set()
                self.assertFalse(acceptance.result(timeout=8)[2])
                self.assertIsNotNone(claim.result(timeout=8).deletion_claim)
            self._assert_single_acceptance(current, submission)

    def test_lock_timeout_and_lost_commit_ack_can_be_reconciled_by_original_uuid(self):
        with self._verified_submission("mysql") as (jobs, _, current, submission):
            def timeout_connection():
                connection = self.connect()
                with connection.cursor() as cursor:
                    cursor.execute("SET SESSION innodb_lock_wait_timeout = 1")
                return connection

            timed = mysql_jobs.MysqlDocumentJobRepository(MysqlPersistenceBackend(
                self.config, initialize=False, connect_factory=timeout_connection,
            ))
            with self.backend.connect() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM document_jobs WHERE job_id = %s FOR UPDATE", (current.id,))
                with self.assertRaises(pymysql.OperationalError) as timed_out:
                    timed.accept_document_job_new_generation(current.id, submission=submission, max_retries=3)
                self.assertEqual(timed_out.exception.args[0], 1205)
            self._assert_no_acceptance(current)
            self.assertIsNone(jobs.get_document_job_generation_request(
                current.id, request_id=submission.request_id, actor_id=submission.actor_id,
            ))

            def lost_ack_connection():
                connection = self.connect()
                commit = connection.commit

                def lost_ack():
                    commit()
                    raise pymysql.OperationalError(2013, "模拟提交回执丢失。")

                connection.commit = lost_ack
                return connection

            lost = mysql_jobs.MysqlDocumentJobRepository(MysqlPersistenceBackend(
                self.config, initialize=False, connect_factory=lost_ack_connection,
            ))
            with self.assertRaises(NewGenerationCommitUnknownError):
                lost.accept_document_job_new_generation(current.id, submission=submission, max_retries=3)
            receipt, _ = jobs.get_document_job_generation_request(
                current.id, request_id=submission.request_id, actor_id=submission.actor_id,
            )
            retry, _, replayed = jobs.accept_document_job_new_generation(current.id, submission=submission, max_retries=3)
            self.assertTrue(replayed)
            self.assertEqual(retry, receipt)
            self._assert_single_acceptance(current, submission)

    @contextmanager
    def _ready_to_approve(self, *, repair_count=2):
        with TemporaryDirectory() as directory:
            runtime = self._build_runtime(Path(directory), "mysql")
            runtime.settings.document_publication_enabled = True
            execution = runtime.document_job_execution_service
            execution.fake_mineru_client.result_zip_bytes = replay_fixtures._gs008_package(replay_fixtures._GS008_ROWS)
            preview = execution.rendering.results.word_preview_service
            preview.provider = RecordingPreviewProvider()
            preview.audit_service = runtime.audit_service
            replace_dependency(runtime.document_job_use_cases, "audit_service", runtime.audit_service)
            replace_dependency(runtime.document_job_use_cases, "word_preview_service", preview)
            with fixtures.TestClient(fixtures.create_app(runtime)) as client:
                owner = fixtures.build_auth_header(client)
                job = self._pause_after_ir(runtime, execution, client, owner)
                job = self.install_publication_resources(runtime, execution, job)
                policy = PreviewPolicy(backend="sandboxed", required=True, render_pages=True)
                job = runtime.document_job_repository.update_document_job(job.id, request_snapshot={
                    **job.request_snapshot, "word_preview": policy.model_dump(mode="json"),
                })
                self._install_review(runtime, execution, job, repair_count=repair_count)
                result = execution.execute_job(job.id)
                self.assertEqual(result.status, "succeeded", result.error_message)
                if repair_count == 2:
                    self.assertIn(result.quality_status, {"passed", "warning"}, result.quality_summary)
                else:
                    self.assertEqual(result.quality_status, "blocked")
                word_file = runtime.document_file_repository.get_document_file(result.result_file_id)
                report_id = word_file.metadata["table_evidence_report"]["report_file_id"]
                admin = fixtures.build_auth_header(client, username="admin", password="admin-pass")
                yield result, report_id, client, owner, admin

    def test_review_refuses_report_or_ir_claim_after_final_read_without_writing_history(self):
        for role in ("report", "ir"):
            with self.subTest(role=role), self._ready_to_approve() as (job, report_id, client, owner, _):
                jobs, files = self.adapters.document_job_repository, self.adapters.document_file_repository
                dependency_id = report_id if role == "report" else job.document_ir_file_id
                original = jobs.update_document_job_review_if_current

                def invalidate_then_approve(*args, **kwargs):
                    files.reserve_document_file_deletion(dependency_id, claim_id="fixture-claim", now=utc_now())
                    return original(*args, **kwargs)

                with patch.object(jobs, "update_document_job_review_if_current", side_effect=invalidate_then_approve):
                    rejected = self._approve(client, owner, job.id)
                self.assertEqual(rejected.status_code, 409, rejected.text)
                self.assertEqual(rejected.json()["error"]["reason_code"], "review_result_integrity_conflict")
                current = jobs.get_document_job(job.id)
                self.assertEqual((current.review_status, current.review_sequence, current.current_review_record_id),
                                 ("unreviewed", 0, None))
                self.assertEqual(jobs.list_document_job_reviews(job.id), [])
                self.assertIsNotNone(files.get_document_file(dependency_id).deletion_claim)

    def test_review_holds_report_row_until_commit(self):
        for rollback in (False, True):
            with self.subTest(rollback=rollback), self._ready_to_approve() as (job, report_id, client, owner, _):
                jobs, files = self.adapters.document_job_repository, self.adapters.document_file_repository
                failure = RuntimeError("模拟审批插入后的事务中断。") if rollback else None
                with ThreadPoolExecutor(max_workers=2) as pool, self._pause_after_write(
                    jobs, "_insert_review", failure=failure,
                ) as (acquired, release):
                    approval = pool.submit(self._approve, client, owner, job.id)
                    holder = acquired.get(timeout=8)
                    claim = pool.submit(files.reserve_document_file_deletion, report_id, claim_id="fixture-claim",
                                        now=utc_now())
                    self._observe_primary_wait(holder=holder, table="document_files")
                    self.assertEqual(jobs.list_document_job_reviews(job.id), [])
                    release.set()
                    outcome = approval.result(timeout=8)
                    self.assertEqual(outcome.status_code, 500 if rollback else 200, outcome.text)
                    self.assertIsNotNone(claim.result(timeout=8).deletion_claim)
                current = jobs.get_document_job(job.id)
                expected = ("unreviewed", 0) if rollback else ("approved", 1)
                self.assertEqual((current.review_status, current.review_sequence), expected)
                self.assertEqual(len(jobs.list_document_job_reviews(job.id)), expected[1])

    def test_publication_rechecks_after_approval_and_retains_normal_release(self):
        for drift in ("before_verification", "before_commit", None):
            with self.subTest(drift=drift), self._ready_to_approve() as (job, report_id, client, owner, admin):
                jobs, files = self.adapters.document_job_repository, self.adapters.document_file_repository
                approved = self._approve(client, owner, job.id)
                self.assertEqual(approved.status_code, 200, approved.text)
                original = jobs.publish_document_job

                def invalidate_then_publish(*args, **kwargs):
                    files.reserve_document_file_deletion(report_id, claim_id="fixture-claim", now=utc_now())
                    return original(*args, **kwargs)

                url = f"/api/v1/document-jobs/{job.id}"
                if drift == "before_verification":
                    source = client.get(f"{url}/publications", headers=admin)
                    self.assertEqual(source.status_code, 200, source.text)
                    files.reserve_document_file_deletion(report_id, claim_id="fixture-claim", now=utc_now())
                    rejected = client.post(f"{url}/publish", headers=admin, json={
                        "request_id": str(uuid4()), "note": "核对当前审批后尝试发布",
                        "expected_source": source.json()["expected_source"],
                    })
                    self.assertIn(rejected.status_code, (409, 500), rejected.text)
                    self.assertEqual(jobs.list_document_job_publications(job.id), [])
                    self.assertIsNone(jobs.get_document_job(job.id).current_publication_id)
                elif drift == "before_commit":
                    with patch.object(jobs, "publish_document_job", side_effect=invalidate_then_publish):
                        rejected = self.try_publish(client, admin, url)
                    self.assertEqual(rejected.status_code, 409, rejected.text)
                    self.assertEqual(rejected.json()["error"]["reason_code"], "publication_result_unavailable")
                    self.assertEqual(jobs.list_document_job_publications(job.id), [])
                    self.assertIsNone(jobs.get_document_job(job.id).current_publication_id)
                else:
                    published = self.try_publish(client, admin, url)
                    self.assertEqual(published.status_code, 201, published.text)
                    self.assertEqual(len(jobs.list_document_job_publications(job.id)), 1)
                    self.assertEqual(jobs.get_document_job(job.id).delivery_status, "published")

    def test_unresolved_value_still_blocks_review_and_publication(self):
        with self._ready_to_approve(repair_count=1) as (job, _, client, owner, admin):
            approval = self._approve(client, owner, job.id)
            self.assertEqual(approval.status_code, 409, approval.text)
            self.assertEqual(approval.json()["error"]["reason_code"], "review_quality_blocked")
            publication = self.try_publish(client, admin, f"/api/v1/document-jobs/{job.id}")
            self.assertEqual(publication.status_code, 409, publication.text)
            self.assertEqual(publication.json()["error"]["reason_code"], "publication_quality_blocked")
