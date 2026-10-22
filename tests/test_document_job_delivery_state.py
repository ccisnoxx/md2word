"""任务交付状态的模型、三仓储往返和真实锁内竞争合同。"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event
from unittest import TestCase

from pydantic import ValidationError

from app.domains.document_jobs.delivery_state import (
    DOCUMENT_JOB_STATE_FIELDS,
    backfill_document_job_state_payload,
    document_job_state_columns,
    initial_delivery_state,
    translation_qa_projection,
)
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.result_state import patched_job
from app.domains.resources.models import utc_now
from app.infrastructure.persistence import (
    build_file_persistence_adapters,
    build_mysql_persistence_adapters,
    build_sqlite_persistence_adapters,
)
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config
from tests.test_document_job_result_persistence import _candidate


def _job(**patch):
    return DocumentJobRecord.model_validate({
        "id": "job", "tenant_id": "tenant", "company_id": "company", "created_by": "operator",
        "source_file_id": "source", "template_version_id": "default@2",
        "request_snapshot": {"nested": {"retained": True}}, **patch,
    })


@contextmanager
def _repository(kind):
    with TemporaryDirectory() as directory:
        root = Path(directory)
        database = _FakeMysqlDatabase()
        if kind == "file":
            build = lambda: build_file_persistence_adapters(root)
        elif kind == "sqlite":
            build = lambda: build_sqlite_persistence_adapters(root / "metadata.sqlite3")
        else:
            build = lambda: build_mysql_persistence_adapters(_mysql_config(), connect_factory=database.connect)
        yield build().document_job_repository, build, database


def _raw(repository, kind, database):
    if kind == "file":
        return repository.backend.read_json(repository.backend.document_jobs_dir / "job" / "job.json", {})
    if kind == "sqlite":
        with repository.backend.connect() as connection:
            return json.loads(connection.execute("SELECT payload FROM document_jobs WHERE job_id = ?", ("job",)).fetchone()[0])
    return json.loads(database.document_jobs["job"]["payload"])


def _write_raw(repository, kind, database, payload):
    if kind == "file":
        repository.backend.write_json(repository.backend.document_jobs_dir / "job" / "job.json", payload)
    elif kind == "sqlite":
        with repository.backend.connect() as connection:
            connection.execute("UPDATE document_jobs SET payload = ? WHERE job_id = ?", (json.dumps(payload), "job"))
    else:
        database.document_jobs["job"]["payload"] = json.dumps(payload)


def _review(repository, snapshot, review_status="approved", **overrides):
    return repository.update_document_job_review_if_current(snapshot.id, **{
        "expected_retry_count": snapshot.retry_count, "expected_result_file_id": snapshot.result_file_id,
        "review_status": review_status, "issue_type": None, "note": "复核备注",
        "reviewed_by": "operator", "reviewed_at": utc_now(), "updated_at": utc_now(), **overrides,
    })


class DocumentJobDeliveryStateTests(TestCase):
    def _assert_columns(self, repository, kind, database):
        record = repository.get_document_job("job")
        if kind == "file":
            return
        if kind == "sqlite":
            with repository.backend.connect() as connection:
                row = connection.execute("SELECT quality_status, review_status, delivery_status, quality_summary_json "
                                         "FROM document_jobs WHERE job_id = ?", ("job",)).fetchone()
                values = tuple(row)
        else:
            row = database.document_jobs["job"]
            values = tuple(row[key] for key in ("quality_status", "review_status", "delivery_status", "quality_summary_json"))
        self.assertEqual(values, document_job_state_columns(record))

    def test_legacy_model_defaults_do_not_promote_old_qa_and_round_trip_new_state(self):
        legacy = _job(status="succeeded", stage="completed", result_file_id="result",
                      translation_qa_status="approved", translation_qa_note="历史批准")
        self.assertEqual({key: getattr(legacy, key) for key in DOCUMENT_JOB_STATE_FIELDS}, initial_delivery_state())
        self.assertEqual(translation_qa_projection(legacy)["translation_qa_status"], "unreviewed")
        self.assertIsNone(translation_qa_projection(legacy)["translation_qa_note"])
        blocked = _job(status="succeeded", stage="completed", result_file_id="result",
                       quality_status="blocked", quality_summary={"checks": [{"passed": False}]})
        self.assertEqual(DocumentJobRecord.model_validate_json(blocked.model_dump_json()), blocked)
        for patch in (
            {"quality_status": "unavailable"}, {"review_status": "unknown"}, {"delivery_status": "unknown"},
            {"quality_summary": []}, {"quality_summary": {"object": object()}},
            {"review_status": "approved"},
            {"status": "succeeded", "stage": "completed", "review_status": "approved"},
            {"status": "succeeded", "stage": "completed", "result_file_id": "result",
             "quality_status": "blocked", "review_status": "approved"},
        ):
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                _job(**patch)
        for delivery in ("ready_to_publish", "published"):
            for quality, review in (("blocked", "unreviewed"), ("pending", "approved"), ("passed", "unreviewed")):
                with self.subTest(delivery=delivery, quality=quality, review=review), self.assertRaises(ValidationError):
                    _job(status="succeeded", stage="completed", result_file_id="result",
                         quality_status=quality, review_status=review, delivery_status=delivery)
            valid = _job(status="succeeded", stage="completed", result_file_id="result", quality_status="warning",
                         review_status="approved", delivery_status=delivery)
            self.assertEqual(DocumentJobRecord.model_validate_json(valid.model_dump_json()), valid)

    def test_all_adapters_keep_state_and_columns_on_execution_receipt_review_and_retry(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repository, build, database):
                original = _job(status="running", stage="quality_checking", document_ir_file_id="ir")
                repository.create_document_job(original)
                self._assert_columns(repository, kind, database)
                checked = repository.update_document_job_if_current("job", allowed_statuses={"running"},
                    allowed_stages={"quality_checking"}, expected_retry_count=0, quality_status="warning",
                    quality_summary={"checks": [{"code": "layout_warning"}]}, stage="uploading")
                self.assertEqual(checked.quality_status, "warning")
                self._assert_columns(repository, kind, database)
                prepared = repository.prepare_document_job_result("job", expected_retry_count=0,
                    expected_document_ir_file_id="ir", candidate=_candidate())
                self.assertEqual(prepared.quality_status, "warning")
                self._assert_columns(repository, kind, database)
                completed = repository.update_document_job_if_current("job", allowed_statuses={"running"},
                    allowed_stages={"uploading"}, expected_prepared_result_file_id="candidate",
                    status="succeeded", stage="completed", result_file_id="candidate")
                reviewed = _review(repository, completed)
                self.assertEqual(reviewed.review_status, "approved")
                self.assertEqual(reviewed.delivery_status, "internal_draft")
                self._assert_columns(repository, kind, database)
                loaded = build().document_job_repository.get_document_job("job")
                self.assertEqual(loaded, reviewed)
                self.assertEqual(loaded.created_at, original.created_at)
                self.assertEqual(loaded.request_snapshot, original.request_snapshot)
                self.assertEqual(loaded.prepared_result, prepared.prepared_result)
                self.assertEqual(translation_qa_projection(loaded)["translation_qa_note"], "复核备注")
                blocked = repository.update_document_job("job", quality_status="blocked")
                self.assertEqual(blocked.review_status, "unreviewed")
                self.assertEqual(blocked.translation_qa_status, "approved")
                self.assertIsNone(translation_qa_projection(blocked)["translation_qa_note"])
                failed = repository.update_document_job("job", status="failed", stage="failed")
                retry = repository.retry_document_job("job", expected_retry_count=0, max_retries=2,
                    status="running", stage="uploading", retry_count=1)
                self.assertEqual(retry.result_file_id, failed.result_file_id)
                self.assertIsNone(retry.prepared_result)
                self.assertEqual({key: getattr(retry, key) for key in DOCUMENT_JOB_STATE_FIELDS}, initial_delivery_state())
                self.assertEqual(retry.translation_qa_note, "复核备注")
                self._assert_columns(repository, kind, database)

    def test_result_identity_invalidation_preserves_first_binding_quality_and_protects_published(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repository, _, database):
                repository.create_document_job(_job(status="running", stage="uploading", quality_status="blocked",
                                                    quality_summary={"code": "blocked"}))
                first = repository.update_document_job("job", result_file_id="result", status="succeeded", stage="completed")
                self.assertEqual((first.quality_status, first.quality_summary), ("blocked", {"code": "blocked"}))
                repository.update_document_job("job", quality_status="passed")
                approved = _review(repository, first)
                self.assertEqual(approved.review_status, "approved")
                repository.update_document_job("job", delivery_status="ready_to_publish")
                revoked = repository.update_document_job("job", quality_status="blocked")
                self.assertEqual((revoked.review_status, revoked.delivery_status), ("unreviewed", "internal_draft"))
                repository.update_document_job("job", quality_status="passed")
                _review(repository, revoked)
                changed = repository.update_document_job("job", result_file_id="replacement")
                self.assertEqual({key: getattr(changed, key) for key in DOCUMENT_JOB_STATE_FIELDS}, initial_delivery_state())
                repository.update_document_job("job", quality_status="passed")
                _review(repository, changed)
                published = repository.update_document_job("job", delivery_status="published")
                for patch in ({"result_file_id": "other"}, {"retry_count": 1}, {"quality_status": "blocked"},
                              {"delivery_status": "internal_draft"},
                              {"delivery_status": "internal_draft", "result_file_id": "other"},
                              {"request_snapshot": {"changed": True}}):
                    with self.subTest(patch=patch), self.assertRaises(ValueError):
                        repository.update_document_job("job", **patch)
                self.assertIsNone(_review(repository, published, "needs_fix"))
                self.assertEqual(repository.get_document_job("job"), published)
                archived = repository.update_document_job("job", archived_at=utc_now(), archived_by="admin", updated_at=utc_now())
                self.assertEqual(archived.delivery_status, "published")
                self.assertEqual(archived.result_file_id, "replacement")
                self._assert_columns(repository, kind, database)

    def test_review_cas_compares_none_result_generation_and_latest_block_delete(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repository, _, database):
                before = repository.create_document_job(_job())
                self.assertIsNone(_review(repository, before))
                current = repository.update_document_job("job", status="succeeded", stage="completed", result_file_id="result")
                self.assertIsNone(_review(repository, before, "needs_fix"))
                self.assertIsNone(_review(repository, current, expected_retry_count=1))
                self.assertIsNone(repository.update_document_job_if_current("job", allowed_statuses={"succeeded"},
                    allowed_stages={"completed"}, expected_retry_count=0, quality_status="passed"))
                approved = _review(repository, current)
                self.assertEqual(approved.review_status, "approved")
                repository.update_document_job("job", quality_status="blocked")
                self.assertIsNone(_review(repository, current))
                reviewed = _review(repository, current, "needs_fix")
                self.assertEqual(reviewed.quality_status, "blocked")
                self.assertEqual(reviewed.review_status, "needs_fix")
                repository.update_document_job("job", deleted_at=utc_now())
                self.assertIsNone(_review(repository, current, "unreviewed"))
                self._assert_columns(repository, kind, database)

    def test_backfill_only_adds_missing_fields_and_preserves_raw_and_column_timestamps(self):
        for kind in ("file", "sqlite", "mysql"):
            with self.subTest(kind=kind), _repository(kind) as (repository, _, database):
                repository.create_document_job(_job(status="running", stage="uploading", document_ir_file_id="ir"))
                repository.prepare_document_job_result("job", expected_retry_count=0,
                    expected_document_ir_file_id="ir", candidate=_candidate())
                payload = _raw(repository, kind, database)
                for field in DOCUMENT_JOB_STATE_FIELDS:
                    del payload[field]
                payload.update(quality_status="warning", quality_summary={"retained": ["摘要"]},
                               translation_qa_status="approved", translation_qa_note="旧备注",
                               translation_qa_reviewed_by="legacy", created_at="2020-01-01T00:00:00Z",
                               updated_at="2020-01-02T00:00:00Z", unknown_raw={"retained": True})
                _write_raw(repository, kind, database, payload)
                self.assertEqual(repository.get_document_job("job").review_status, "unreviewed")
                self.assertEqual(_raw(repository, kind, database), payload)
                if kind == "sqlite":
                    with repository.backend.connect() as connection:
                        times = tuple(connection.execute("SELECT created_at, updated_at FROM document_jobs").fetchone())
                elif kind == "mysql":
                    times = (database.document_jobs["job"]["created_at"], database.document_jobs["job"]["updated_at"])
                self.assertTrue(repository.backfill_document_job_state_if_missing("job"))
                expected = {**payload, "review_status": "unreviewed", "delivery_status": "internal_draft"}
                self.assertEqual(_raw(repository, kind, database), expected)
                self.assertFalse(repository.backfill_document_job_state_if_missing("job"))
                self.assertEqual(_raw(repository, kind, database), expected)
                self._assert_columns(repository, kind, database)
                if kind == "sqlite":
                    with repository.backend.connect() as connection:
                        self.assertEqual(tuple(connection.execute("SELECT created_at, updated_at FROM document_jobs").fetchone()), times)
                elif kind == "mysql":
                    self.assertEqual((database.document_jobs["job"]["created_at"], database.document_jobs["job"]["updated_at"]), times)
                for invalid in ({**payload, "review_status": "invalid"}, {**payload, "quality_summary": []}, []):
                    _write_raw(repository, kind, database, invalid)
                    with self.assertRaises(ValueError):
                        repository.backfill_document_job_state_if_missing("job")
                    self.assertEqual(_raw(repository, kind, database), invalid)

    def test_real_record_locks_recheck_quality_generation_and_backfill_new_values(self):
        for kind in ("file", "sqlite"):
            for action in ("block", "retry", "backfill"):
                with self.subTest(kind=kind, action=action), _repository(kind) as (repository, build, database):
                    snapshot = repository.create_document_job(_job(status="succeeded", stage="completed", result_file_id="result"))
                    competitor = build().document_job_repository
                    ready = Event()

                    def attempt():
                        ready.set()
                        if action == "backfill":
                            return competitor.backfill_document_job_state_if_missing("job")
                        return _review(competitor, snapshot)

                    with ThreadPoolExecutor(max_workers=1) as executor:
                        with repository._locked_job("job") as (connection, locked):
                            pending = executor.submit(attempt)
                            self.assertTrue(ready.wait(5))
                            if action == "block":
                                patch = {"quality_status": "blocked"}
                            elif action == "retry":
                                patch = {"status": "running", "stage": "uploading", "retry_count": 1}
                            else:
                                patch = {"quality_status": "warning", "quality_summary": {"new": True}}
                            repository._write_job(connection, patched_job(locked, patch))
                        result = pending.result(timeout=10)
                    if action == "backfill":
                        self.assertFalse(result)
                        self.assertEqual(repository.get_document_job("job").quality_summary, {"new": True})
                    else:
                        self.assertIsNone(result)
                        self.assertEqual(repository.get_document_job("job").review_status, "unreviewed")
                    self._assert_columns(repository, kind, database)

    def test_sqlite_bootstrap_adds_only_missing_columns_to_real_legacy_table(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            payload = _job().model_dump(mode="json")
            for field in DOCUMENT_JOB_STATE_FIELDS:
                del payload[field]
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE document_jobs (job_id TEXT PRIMARY KEY, payload TEXT NOT NULL, "
                                   "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("INSERT INTO document_jobs VALUES (?, ?, ?, ?)",
                                   ("job", json.dumps(payload), "created-raw", "updated-raw"))
            backend = SqlitePersistenceBackend(path)
            backend.initialize_schema()
            with backend.connect() as connection:
                row = connection.execute("SELECT * FROM document_jobs").fetchone()
                self.assertEqual(set(row.keys()), {"job_id", "payload", "created_at", "updated_at", "quality_status",
                                                  "review_status", "delivery_status", "quality_summary_json"})
                self.assertEqual(json.loads(row["payload"]), payload)
                self.assertEqual((row["quality_status"], row["review_status"], row["delivery_status"]),
                                 ("pending", "unreviewed", "internal_draft"))
                self.assertIsNone(row["quality_summary_json"])
                self.assertEqual((row["created_at"], row["updated_at"]), ("created-raw", "updated-raw"))

    def test_raw_helper_does_not_mutate_input_or_trust_legacy_approved(self):
        raw = _job().model_dump(mode="json")
        for field in DOCUMENT_JOB_STATE_FIELDS:
            del raw[field]
        raw["translation_qa_status"] = "approved"
        expected = dict(raw)
        filled = backfill_document_job_state_payload(raw)
        self.assertEqual(raw, expected)
        self.assertEqual(filled["review_status"], "unreviewed")
        self.assertEqual(filled["translation_qa_status"], "approved")
