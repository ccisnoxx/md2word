from __future__ import annotations

import copy
import threading
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator
from unittest import TestCase

from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobTranslationBatchRecord
from app.domains.document_jobs.repository import TranslationBatchTreeInvalidError
from app.domains.document_jobs.workflow import TranslationRootPlan
from app.domains.resources.models import utc_now
from app.infrastructure.persistence.file.backend import FilePersistenceBackend
from app.infrastructure.persistence.file.document_jobs import (
    FileDocumentJobRepository,
    FileDocumentJobTranslationBatchRepository,
)
from app.infrastructure.persistence.file.record_lock import record_lock
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.document_jobs import (
    MysqlDocumentJobRepository,
    MysqlDocumentJobTranslationBatchRepository,
)
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.infrastructure.persistence.sqlite.document_jobs import (
    SqliteDocumentJobRepository,
    SqliteDocumentJobTranslationBatchRepository,
)
from tests.test_database_job_repository import _FakeMysqlConnection, _FakeMysqlCursor, _FakeMysqlDatabase


class _RecordingMysqlDatabase(_FakeMysqlDatabase):
    """在既有 fake MySQL 上记录连接内 SQL，并提供测试用事务快照。"""

    def __init__(self) -> None:
        super().__init__()
        self.connection_logs: list[list[str]] = []
        self.fail_child_id: str | None = None

    def connect(self) -> "_RecordingMysqlConnection":
        connection = _RecordingMysqlConnection(self)
        self.connection_logs.append(connection.queries)
        return connection


class _RecordingMysqlConnection(_FakeMysqlConnection):
    def __init__(self, database: _RecordingMysqlDatabase) -> None:
        super().__init__(database)
        self.database = database
        self.queries: list[str] = []
        self._snapshot = (
            copy.deepcopy(database.document_jobs),
            copy.deepcopy(database.document_job_translation_batches),
        )

    def cursor(self) -> "_RecordingMysqlCursor":
        return _RecordingMysqlCursor(self.database, self)

    def rollback(self) -> None:
        self.database.document_jobs = self._snapshot[0]
        self.database.document_job_translation_batches = self._snapshot[1]
        super().rollback()


class _RecordingMysqlCursor(_FakeMysqlCursor):
    def __init__(self, database: _RecordingMysqlDatabase, connection: _RecordingMysqlConnection) -> None:
        super().__init__(database)
        self.connection = connection

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        normalized = " ".join(sql.lower().split())
        self.connection.queries.append(normalized)
        if (
            self.database.fail_child_id is not None
            and normalized.startswith("insert into document_job_translation_batches")
            and params
            and params[0] == self.database.fail_child_id
        ):
            raise RuntimeError("fake MySQL 注入子节点写入失败")
        super().execute(sql, params)


class TranslationBatchRepositoryTests(TestCase):
    """覆盖 file/sqlite 真实交错、事务回滚与 fake MySQL 边界合同。"""

    def _job(self) -> DocumentJobRecord:
        return DocumentJobRecord(
            id="job_batch_repo",
            tenant_id="tenant",
            company_id="company",
            created_by="operator",
            source_file_id="source.pdf",
            mode="en2zh_pdf_to_word",
            status="running",
            stage="translating",
            template_version_id="default@2",
        )

    def _plans(self) -> list[TranslationRootPlan]:
        return [
            TranslationRootPlan(
                batch_id="job_batch_repo_retry0_translation_batch_0001",
                job_id="job_batch_repo", generation=0, job_retry_count=0,
                source_document_ir_file_id="source-ir", language_pair="en2zh",
                item_ids=("p1.text", "p2.text"), item_count=2, char_count=10,
                provider_call_budget=4, max_attempts=2,
            ),
            TranslationRootPlan(
                batch_id="job_batch_repo_retry0_translation_batch_0002",
                job_id="job_batch_repo", generation=0, job_retry_count=0,
                source_document_ir_file_id="source-ir", language_pair="en2zh",
                item_ids=("p3.text",), item_count=1, char_count=3,
                provider_call_budget=4, max_attempts=2,
            ),
        ]

    @staticmethod
    def _children(parent: DocumentJobTranslationBatchRecord) -> tuple[DocumentJobTranslationBatchRecord, ...]:
        common = {
            "parent_batch_id": parent.id, "split_level": parent.split_level + 1,
            "status": "pending", "attempt_count": 0, "lease_owner": None,
            "leased_at": None, "lease_expires_at": None,
        }
        return (
            parent.model_copy(update={"id": f"{parent.id}_s1_01", "item_ids": ["p1.text"], "item_count": 1, **common}),
            parent.model_copy(update={"id": f"{parent.id}_s1_02", "item_ids": ["p2.text"], "item_count": 1, **common}),
        )

    @contextmanager
    def _paired_adapters(self, kind: str) -> Iterator[tuple[Any, Any, Any, Any]]:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            if kind == "file":
                backend_a = FilePersistenceBackend(root / "file")
                backend_b = FilePersistenceBackend(root / "file")
                yield (FileDocumentJobRepository(backend_a), FileDocumentJobTranslationBatchRepository(backend_a),
                       FileDocumentJobRepository(backend_b), FileDocumentJobTranslationBatchRepository(backend_b))
                return
            backend_a = SqlitePersistenceBackend(root / "jobs.sqlite")
            backend_b = SqlitePersistenceBackend(root / "jobs.sqlite")
            yield (SqliteDocumentJobRepository(backend_a), SqliteDocumentJobTranslationBatchRepository(backend_a),
                   SqliteDocumentJobRepository(backend_b), SqliteDocumentJobTranslationBatchRepository(backend_b))

    @staticmethod
    def _paired_kinds() -> tuple[str, ...]:
        return ("file", "sqlite")

    def _prepare_roots(self, job_repository: Any, batch_repository: Any) -> list[TranslationRootPlan]:
        job_repository.create_document_job(self._job())
        plans = self._plans()
        batch_repository.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=plans)
        return plans

    def _queue(self, batch_repository: Any, plan: TranslationRootPlan, plans: list[TranslationRootPlan], budget: int = 2) -> None:
        self.assertIsNotNone(batch_repository.enqueue_translation_batch(
            plan.batch_id, expected_generation=0, expected_attempt_count=0,
            provider_call_budget=budget, expected_plans=plans,
        ))

    def test_double_initialization_keeps_state_after_stale_empty_observation(self) -> None:
        """B 先观察空集合后暂停，A 安装并改变两根状态，B 恢复不得重置账本。"""
        for kind in self._paired_kinds():
            with self.subTest(adapter=kind), self._paired_adapters(kind) as (job_a, batch_a, job_b, batch_b):
                job_a.create_document_job(self._job())
                plans = self._plans()
                observed_empty, resume = threading.Event(), threading.Event()
                errors: list[BaseException] = []

                def stale_reader() -> None:
                    try:
                        self.assertEqual(batch_b.list_translation_batches("job_batch_repo", generation=0), [])
                        observed_empty.set()
                        if not resume.wait(2):
                            raise AssertionError("B 等待 A 的 barrier 超时")
                        batch_b.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=plans)
                    except BaseException as exc:
                        errors.append(exc)

                worker = threading.Thread(target=stale_reader, daemon=True)
                worker.start()
                self.assertTrue(observed_empty.wait(2), "B 未观察到空根集合")
                batch_a.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=plans)
                now = utc_now()
                batch_a.update_translation_batch(plans[0].batch_id, status="succeeded", attempt_count=1,
                                                 result_file_id="result-a", usage={"total_tokens": 7})
                batch_a.update_translation_batch(plans[1].batch_id, status="running", attempt_count=1,
                                                 lease_owner="worker-a", leased_at=now,
                                                 lease_expires_at=now + timedelta(minutes=1), usage={"total_tokens": 11})
                before = {item.id: item for item in batch_a.list_translation_batches("job_batch_repo", generation=0)}
                resume.set()
                worker.join(2)
                self.assertFalse(worker.is_alive(), "B barrier 线程未在限定时间内退出")
                self.assertEqual(errors, [])
                after = {item.id: item for item in batch_b.list_translation_batches("job_batch_repo", generation=0)}
                self.assertEqual(after, before)
                self.assertEqual(sum(item.attempt_count for item in after.values()), 2)

    def test_file_snapshot_waits_for_normal_split_writer_until_tree_is_complete(self) -> None:
        """正常 split 写入期间的读取必须等待 job 锁，而不是把半树判成损坏。"""

        with self._paired_adapters("file") as (job_a, batch_a, _job_b, batch_b):
            plans = self._prepare_roots(job_a, batch_a)
            self._queue(batch_a, plans[0], plans, budget=4)
            now = utc_now()
            parent = batch_a.claim_translation_batch(
                plans[0].batch_id,
                expected_generation=0,
                expected_attempt_count=0,
                lease_owner="split-writer",
                leased_at=now,
                lease_expires_at=now + timedelta(minutes=1),
                provider_call_budget=4,
                expected_plans=plans,
            )
            assert parent is not None
            children = self._children(parent)
            writer_started = threading.Event()
            release_writer = threading.Event()
            snapshot_done = threading.Event()
            snapshot: list[DocumentJobTranslationBatchRecord] = []

            def writer() -> None:
                lock_path = batch_a.backend.document_jobs_dir / parent.job_id / "job.lock"
                with record_lock(lock_path):
                    writer_started.set()
                    batch_a._write_record(parent.model_copy(update={"status": "split", "lease_owner": None}))
                    self.assertTrue(release_writer.wait(2))
                    for child in children:
                        batch_a._write_record(child)

            def reader() -> None:
                _job, records = batch_b.get_translation_batch_snapshot(parent.job_id, generation=0)
                snapshot.extend(records)
                snapshot_done.set()

            writer_thread = threading.Thread(target=writer, daemon=True)
            reader_thread = threading.Thread(target=reader, daemon=True)
            writer_thread.start()
            self.assertTrue(writer_started.wait(2))
            reader_thread.start()
            self.assertFalse(snapshot_done.wait(0.1))
            release_writer.set()
            writer_thread.join(2)
            reader_thread.join(2)

            self.assertFalse(writer_thread.is_alive() or reader_thread.is_alive())
            self.assertEqual({record.id for record in snapshot}, {plans[1].batch_id, parent.id, *[child.id for child in children]})

    def test_real_barrier_claim_has_one_winner_and_fences_last_budget(self) -> None:
        """两个独立连接同时 claim 时只有一个胜者，最后预算拒绝另一根。"""
        for kind in self._paired_kinds():
            with self.subTest(adapter=kind), self._paired_adapters(kind) as (job_a, batch_a, job_b, batch_b):
                plans = self._prepare_roots(job_a, batch_a)
                self._queue(batch_a, plans[0], plans); self._queue(batch_a, plans[1], plans)
                barrier = threading.Barrier(2)
                results: list[Any] = []; errors: list[BaseException] = []

                def claim(repo: Any, owner: str) -> None:
                    try:
                        barrier.wait(2)
                        results.append(repo.claim_translation_batch(
                            plans[0].batch_id, expected_generation=0, expected_attempt_count=0,
                            lease_owner=owner, leased_at=utc_now(),
                            lease_expires_at=utc_now() + timedelta(minutes=1),
                            provider_call_budget=1, expected_plans=plans,
                        ))
                    except BaseException as exc:
                        errors.append(exc)

                first = threading.Thread(target=claim, args=(batch_a, "worker-a"), daemon=True)
                second = threading.Thread(target=claim, args=(batch_b, "worker-b"), daemon=True)
                first.start(); second.start(); first.join(2); second.join(2)
                self.assertFalse(first.is_alive() or second.is_alive(), "claim barrier 线程未退出")
                self.assertEqual(errors, [])
                self.assertEqual(sum(result is not None for result in results), 1)
                self.assertIsNone(batch_a.enqueue_translation_batch(
                    plans[1].batch_id, expected_generation=0, expected_attempt_count=0,
                    provider_call_budget=1, expected_plans=plans,
                ))

    def test_last_budget_inflight_success_is_allowed_without_pending_leaf(self) -> None:
        """没有待消费兄弟时，合法占用最后预算的在途结果仍可晋升。"""
        for kind in self._paired_kinds():
            with self.subTest(adapter=kind), self._paired_adapters(kind) as (job_a, batch_a, job_b, batch_b):
                plan = replace(self._plans()[0], provider_call_budget=1)
                job_a.create_document_job(self._job())
                batch_a.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=[plan])
                self.assertIsNotNone(batch_a.enqueue_translation_batch(
                    plan.batch_id, expected_generation=0, expected_attempt_count=0,
                    provider_call_budget=1, expected_plans=[plan],
                ))
                now = utc_now()
                claimed = batch_a.claim_translation_batch(
                    plan.batch_id, expected_generation=0, expected_attempt_count=0,
                    lease_owner="last-budget-worker", leased_at=now,
                    lease_expires_at=now + timedelta(minutes=1), provider_call_budget=1,
                    expected_plans=[plan],
                )
                self.assertIsNotNone(claimed)
                assert claimed is not None
                self.assertIsNotNone(batch_b.update_translation_batch_if_current(
                    claimed.id, allowed_statuses={"running"}, expected_generation=0,
                    expected_attempt_count=1, expected_lease_owner="last-budget-worker",
                    expected_plans=[plan], status="succeeded", result_file_id="last-budget-result",
                ))

    def test_old_attempt_lease_and_terminal_sibling_cannot_promote_result(self) -> None:
        """旧 attempt/lease 的结果、split 与终态兄弟窗口均不得覆盖当前记录。"""
        for kind in self._paired_kinds():
            with self.subTest(adapter=kind), self._paired_adapters(kind) as (job_a, batch_a, job_b, batch_b):
                plans = self._prepare_roots(job_a, batch_a); self._queue(batch_a, plans[0], plans)
                current = batch_a.claim_translation_batch(
                    plans[0].batch_id, expected_generation=0, expected_attempt_count=0,
                    lease_owner="winner", leased_at=utc_now(),
                    lease_expires_at=utc_now() + timedelta(minutes=1), provider_call_budget=2,
                    expected_plans=plans,
                )
                self.assertIsNotNone(current); assert current is not None
                self.assertIsNone(batch_b.update_translation_batch_if_current(
                    current.id, allowed_statuses={"running"}, expected_generation=0,
                    expected_attempt_count=0, expected_lease_owner="old-worker", expected_plans=plans,
                    status="succeeded", result_file_id="old-result",
                ))
                self.assertIsNone(batch_b.update_translation_batch_if_current(
                    current.id, allowed_statuses={"running"}, expected_generation=0,
                    expected_attempt_count=0, expected_lease_owner="old-worker", expected_plans=plans,
                    status="failed", retryable=True, error_code="old-failure",
                ))
                self.assertIsNone(batch_b.release_translation_batch_lease(
                    current.id, expected_generation=0, expected_attempt_count=0,
                    expected_lease_owner="old-worker", now=utc_now() + timedelta(minutes=2), expected_plans=plans,
                ))
                self.assertIsNone(batch_b.split_translation_batch(
                    current.id, expected_generation=0, expected_attempt_count=0,
                    expected_lease_owner="old-worker", expected_plans=plans, children=self._children(current),
                ))
                batch_a.update_translation_batch(plans[1].batch_id, status="failed", retryable=False, error_code="terminal")
                self.assertIsNone(batch_a.enqueue_translation_batch(
                    plans[1].batch_id, expected_generation=0, expected_attempt_count=0,
                    provider_call_budget=2, expected_plans=plans,
                ))
                self.assertIsNone(batch_a.update_translation_batch_if_current(
                    current.id, allowed_statuses={"running"}, expected_generation=0,
                    expected_attempt_count=1, expected_lease_owner="winner", expected_plans=plans,
                    status="succeeded", result_file_id="blocked-result",
                ))
                self.assertEqual(batch_a.get_translation_batch(current.id).status, "running")

    def test_reducer_stops_expired_exhausted_claim_but_allows_own_recovery(self) -> None:
        """过期且耗尽 attempt 的批次阻止新 claim，但自身 lease 回收和可重试恢复仍可落库。"""
        for kind in self._paired_kinds():
            with self.subTest(adapter=kind), self._paired_adapters(kind) as (job_a, batch_a, job_b, batch_b):
                plans = self._plans()
                plans[0] = replace(plans[0], max_attempts=1, provider_call_budget=4)
                job_a.create_document_job(self._job())
                batch_a.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=plans)
                self._queue(batch_a, plans[0], plans, budget=4)
                self._queue(batch_a, plans[1], plans, budget=4)
                now = utc_now()
                expired = batch_a.claim_translation_batch(
                    plans[0].batch_id, expected_generation=0, expected_attempt_count=0,
                    lease_owner="expired-worker", leased_at=now - timedelta(minutes=2),
                    lease_expires_at=now - timedelta(minutes=1), provider_call_budget=4,
                    expected_plans=plans,
                )
                self.assertIsNotNone(expired)
                assert expired is not None
                self.assertIsNone(batch_b.claim_translation_batch(
                    plans[1].batch_id, expected_generation=0, expected_attempt_count=0,
                    lease_owner="blocked-worker", leased_at=now,
                    lease_expires_at=now + timedelta(minutes=1), provider_call_budget=4,
                    expected_plans=plans,
                ))
                self.assertIsNone(batch_b.update_translation_batch_if_current(
                    expired.id, allowed_statuses={"running"}, expected_generation=0,
                    expected_attempt_count=1, expected_lease_owner="expired-worker",
                    expected_plans=plans, status="succeeded", result_file_id="late-result",
                ))
                recovered = batch_a.release_translation_batch_lease(
                    expired.id, expected_generation=0, expected_attempt_count=1,
                    expected_lease_owner="expired-worker", now=now,
                    expected_plans=plans, retryable=True,
                )
                self.assertIsNotNone(recovered)


    def test_expired_lease_with_remaining_attempt_can_reclaim(self) -> None:
        """过期但仍有 attempt 和预算的 lease 可回收后重新 claim。"""
        for kind in self._paired_kinds():
            with self.subTest(adapter=kind), self._paired_adapters(kind) as (job_a, batch_a, job_b, batch_b):
                plans = self._plans()
                job_a.create_document_job(self._job())
                batch_a.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=plans)
                self._queue(batch_a, plans[0], plans, budget=4)
                now = utc_now()
                expired = batch_a.claim_translation_batch(
                    plans[0].batch_id, expected_generation=0, expected_attempt_count=0,
                    lease_owner="expired-worker", leased_at=now - timedelta(minutes=2),
                    lease_expires_at=now - timedelta(minutes=1), provider_call_budget=4,
                    expected_plans=plans,
                )
                assert expired is not None
                self.assertIsNotNone(batch_a.release_translation_batch_lease(
                    expired.id, expected_generation=0, expected_attempt_count=1,
                    expected_lease_owner="expired-worker", now=now,
                    expected_plans=plans, retryable=True,
                ))
                self.assertIsNotNone(batch_b.claim_translation_batch(
                    expired.id, expected_generation=0, expected_attempt_count=1,
                    lease_owner="retry-worker", leased_at=now,
                    lease_expires_at=now + timedelta(minutes=1), provider_call_budget=4,
                    expected_plans=plans,
                ))

    def test_file_root_and_split_interruption_leave_tree_invalid_without_repair(self) -> None:
        """file 根或 split 中途失败后重放必须报树错误，不得自动补写。"""
        with self._paired_adapters("file") as (job_a, batch_a, job_b, batch_b):
            job_a.create_document_job(self._job()); plans = self._plans()
            original_write = batch_a._write_record; count = 0

            def fail_on_second(record: DocumentJobTranslationBatchRecord) -> None:
                nonlocal count
                count += 1
                if count == 2:
                    raise RuntimeError("file 根写入注入失败")
                original_write(record)

            batch_a._write_record = fail_on_second  # type: ignore[method-assign]
            with self.assertRaises(RuntimeError):
                batch_a.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=plans)
            batch_a._write_record = original_write  # type: ignore[method-assign]
            with self.assertRaises(TranslationBatchTreeInvalidError):
                batch_a.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=plans)
            self.assertEqual(len(batch_a.list_translation_batches("job_batch_repo", generation=0)), 1)

            for record in batch_a.list_translation_batches("job_batch_repo", generation=0):
                (batch_a.backend.document_job_translation_batches_dir / f"{record.id}.json").unlink()
            batch_a.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=[plans[0]])
            self._queue(batch_a, plans[0], [plans[0]])
            parent = batch_a.claim_translation_batch(
                plans[0].batch_id, expected_generation=0, expected_attempt_count=0,
                lease_owner="worker-a", leased_at=utc_now(), lease_expires_at=utc_now() + timedelta(minutes=1),
                provider_call_budget=2, expected_plans=[plans[0]],
            )
            assert parent is not None; children = self._children(parent); original_write = batch_a._write_record

            def fail_on_second_child(record: DocumentJobTranslationBatchRecord) -> None:
                if record.id.endswith("_02"):
                    raise RuntimeError("file split 子写入注入失败")
                original_write(record)

            batch_a._write_record = fail_on_second_child  # type: ignore[method-assign]
            with self.assertRaises(RuntimeError):
                batch_a.split_translation_batch(
                    parent.id, expected_generation=0, expected_attempt_count=1, expected_lease_owner="worker-a",
                    expected_plans=[plans[0]], children=children,
                )
            batch_a._write_record = original_write  # type: ignore[method-assign]
            with self.assertRaises(TranslationBatchTreeInvalidError):
                batch_a.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=[plans[0]])

    def test_sqlite_root_and_split_transactions_roll_back(self) -> None:
        """SQLite 根集合和 split 的父子写入异常必须整事务回滚。"""
        with self._paired_adapters("sqlite") as (job_a, batch_a, job_b, batch_b):
            job_a.create_document_job(self._job()); plans = self._plans()
            original_insert = batch_a._insert_record; count = 0

            def fail_root_insert(connection: Any, record: DocumentJobTranslationBatchRecord) -> None:
                nonlocal count
                count += 1; original_insert(connection, record)
                if count == 2:
                    raise RuntimeError("sqlite 根写入注入失败")

            batch_a._insert_record = fail_root_insert  # type: ignore[method-assign]
            with self.assertRaises(RuntimeError):
                batch_a.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=plans)
            batch_a._insert_record = original_insert  # type: ignore[method-assign]
            self.assertEqual(batch_a.list_translation_batches("job_batch_repo", generation=0), [])
            batch_a.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=plans)
            now = utc_now()
            batch_a.update_translation_batch(plans[0].batch_id, status="running", attempt_count=1,
                                             lease_owner="worker-a", leased_at=now, lease_expires_at=now + timedelta(minutes=1))
            parent = batch_a.get_translation_batch(plans[0].batch_id); assert parent is not None
            children = self._children(parent); original_insert = batch_a._insert_record

            def fail_child_insert(connection: Any, record: DocumentJobTranslationBatchRecord) -> None:
                original_insert(connection, record)
                if record.id.endswith("_02"):
                    raise RuntimeError("sqlite split 子写入注入失败")

            batch_a._insert_record = fail_child_insert  # type: ignore[method-assign]
            with self.assertRaises(RuntimeError):
                batch_a.split_translation_batch(
                    parent.id, expected_generation=0, expected_attempt_count=1, expected_lease_owner="worker-a",
                    expected_plans=plans, children=children,
                )
            batch_a._insert_record = original_insert  # type: ignore[method-assign]
            stored = batch_a.list_translation_batches("job_batch_repo", generation=0)
            self.assertEqual({record.id for record in stored}, {plan.batch_id for plan in plans})
            self.assertEqual(batch_a.get_translation_batch(parent.id).status, "running")

    def test_fake_mysql_same_connection_lock_order_and_rollback(self) -> None:
        """fake MySQL 自动断言 job→batch 锁序、同连接执行和 rollback 调用。"""
        database = _RecordingMysqlDatabase()
        backend = MysqlPersistenceBackend(
            MysqlPersistenceConfig(host="127.0.0.1", port=3306, user="test", password="", database="test"),
            connect_factory=database.connect, initialize=False,
        )
        job_repository = MysqlDocumentJobRepository(backend)
        batch_repository = MysqlDocumentJobTranslationBatchRepository(backend)
        job_repository.create_document_job(self._job()); plans = self._plans()
        plans.append(TranslationRootPlan(
            batch_id="job_batch_repo_retry0_translation_batch_0003",
            job_id="job_batch_repo", generation=0, job_retry_count=0,
            source_document_ir_file_id="source-ir", language_pair="en2zh",
            item_ids=("p4.text", "p5.text"), item_count=2, char_count=8,
            provider_call_budget=2, max_attempts=2,
        ))

        def assert_current_read_order() -> None:
            queries = database.connection_logs[-1]
            job_lock = next(index for index, query in enumerate(queries) if "document_jobs" in query and "for update" in query)
            batch_reads = [index for index, query in enumerate(queries) if "document_job_translation_batches" in query]
            self.assertTrue(batch_reads)
            self.assertTrue(all(index > job_lock for index in batch_reads))
            self.assertTrue(any("for update" in queries[index] for index in batch_reads))

        batch_repository.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=plans)
        assert_current_read_order()
        batch_repository.update_translation_batch(plans[1].batch_id, usage={"total_tokens": 1})
        assert_current_read_order()
        self._queue(batch_repository, plans[0], plans)
        assert_current_read_order()
        now = utc_now()
        claimed = batch_repository.claim_translation_batch(
            plans[0].batch_id, expected_generation=0, expected_attempt_count=0,
            lease_owner="worker-a", leased_at=now - timedelta(minutes=2),
            lease_expires_at=now - timedelta(minutes=1), provider_call_budget=2,
            expected_plans=plans,
        )
        self.assertIsNotNone(claimed); assert_current_read_order()
        batch_repository.release_translation_batch_lease(
            plans[0].batch_id, expected_generation=0, expected_attempt_count=1,
            expected_lease_owner="worker-a", now=now, expected_plans=plans,
            retryable=True,
        )
        assert_current_read_order()
        batch_repository.update_translation_batch_if_current(
            plans[0].batch_id, allowed_statuses={"failed"}, expected_generation=0,
            expected_attempt_count=1, expected_plans=plans, status="succeeded",
            result_file_id="result-a",
        )
        assert_current_read_order()
        self._queue(batch_repository, plans[2], plans)
        parent = batch_repository.claim_translation_batch(
            plans[2].batch_id, expected_generation=0, expected_attempt_count=0,
            lease_owner="worker-split", leased_at=now,
            lease_expires_at=now + timedelta(minutes=1), provider_call_budget=2,
            expected_plans=plans,
        )
        self.assertIsNotNone(parent); assert_current_read_order(); assert parent is not None
        common = {"parent_batch_id": parent.id, "split_level": 1, "status": "pending", "attempt_count": 0,
                  "lease_owner": None, "leased_at": None, "lease_expires_at": None}
        children = (
            parent.model_copy(update={"id": f"{parent.id}_s1_01", "item_ids": ["p4.text"], "item_count": 1, **common}),
            parent.model_copy(update={"id": f"{parent.id}_s1_02", "item_ids": ["p5.text"], "item_count": 1, **common}),
        )
        database.fail_child_id = children[1].id
        with self.assertRaises(RuntimeError):
            batch_repository.split_translation_batch(
                parent.id, expected_generation=0, expected_attempt_count=1, expected_lease_owner="worker-split",
                expected_plans=plans, children=children,
            )
        assert_current_read_order()
        self.assertGreater(database.rollback_count, 0)
        self.assertEqual(batch_repository.get_translation_batch(parent.id).status, "running")
        self.assertIsNone(batch_repository.get_translation_batch(children[0].id))

    def test_fake_mysql_terminal_sibling_blocks_result_promotion(self) -> None:
        """fake MySQL 在同一事务内重算 reducer，兄弟终败后禁止旧在途结果晋升。"""
        database = _RecordingMysqlDatabase()
        backend = MysqlPersistenceBackend(
            MysqlPersistenceConfig(host="127.0.0.1", port=3306, user="test", password="", database="test"),
            connect_factory=database.connect, initialize=False,
        )
        job_repository = MysqlDocumentJobRepository(backend)
        batch_repository = MysqlDocumentJobTranslationBatchRepository(backend)
        job_repository.create_document_job(self._job())
        plans = [replace(plan, provider_call_budget=2) for plan in self._plans()]
        batch_repository.ensure_translation_batch_roots("job_batch_repo", generation=0, expected_plans=plans)
        self._queue(batch_repository, plans[1], plans, budget=2)
        now = utc_now()
        running = batch_repository.claim_translation_batch(
            plans[1].batch_id, expected_generation=0, expected_attempt_count=0,
            lease_owner="running-worker", leased_at=now,
            lease_expires_at=now + timedelta(minutes=1), provider_call_budget=2,
            expected_plans=plans,
        )
        self.assertIsNotNone(running)
        batch_repository.update_translation_batch(
            plans[0].batch_id, status="failed", retryable=False,
            error_code="terminal-sibling",
        )
        assert running is not None
        self.assertIsNone(batch_repository.update_translation_batch_if_current(
            running.id, allowed_statuses={"running"}, expected_generation=0,
            expected_attempt_count=1, expected_lease_owner="running-worker",
            expected_plans=plans, status="succeeded", result_file_id="must-not-promote",
        ))
        self.assertEqual(batch_repository.get_translation_batch(running.id).status, "running")
