"""冻结线上 owner 的比较对照及 v2 SQL 行为矩阵。"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.domains.document_jobs.list_query import (
    DocumentJobListQuery, DocumentJobListProjectionUnstable, document_job_list_projection,
    document_job_list_projection_from_raw, document_file_review_projection,
    document_file_review_projection_from_raw, query_document_job_records,
)
from app.domains.document_jobs.list_query_facts import equality_key, receipt_file_key
from app.domains.document_jobs.models import DocumentJobPreparedResult, DocumentJobRecord
from app.domains.document_jobs.review import ReviewBinding, effective_review_job, receipt_identity, receipt_matches_file
from app.domains.files.models import DocumentFileRecord
from app.domains.files.result_registration import review_source_descriptor

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)


def job(job_id="a", **values):
    return DocumentJobRecord.model_validate({**dict(id=job_id, tenant_id="T", company_id="C", created_by="U",
        source_file_id="source", template_version_id="default@2", created_at=NOW, updated_at=NOW), **values})


def word(file_id="word", job_id="a", **values):
    base = dict(id=file_id, tenant_id="T", company_id="C", job_id=job_id, file_type="generated_word",
        storage_provider="local_file", bucket="local", object_key="synthetic", original_filename="synthetic.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", size_bytes=1,
        checksum_sha256="sha256:" + "a" * 64, status="uploaded", expires_at=NOW + timedelta(days=1),
        created_at=NOW, updated_at=NOW)
    return DocumentFileRecord.model_validate({**base, **values})


def bound_job(file=None, *, receipt=False, **values):
    file = file or word()
    base = dict(mode="en2zh_pdf_to_word", status="succeeded", stage="completed", result_file_id=file.id,
        quality_status="passed", review_status="approved", current_review_record_id="review", review_sequence=1)
    prepared = DocumentJobPreparedResult(generation=0, document_ir_file_id="ir", file=file) if receipt else None
    base.update(prepared_result=prepared, document_ir_file_id="ir" if receipt else None)
    unbound = SimpleNamespace(prepared_result=prepared)
    binding = ReviewBinding(generation=0, result_file_id=file.id, binding_state="verified",
        result_sha256=file.checksum_sha256, file_review_source_revision=file.review_source_revision,
        descriptor=review_source_descriptor(file), receipt_sha256=receipt_identity(unbound))
    return job(file.job_id, **{**base, "current_review_binding": binding, **values})


def keys_equal(left, right):
    a, ac = equality_key(left)
    b, bc = equality_key(right)
    return ac and bc and a == b


class ListFactsTests(TestCase):
    def test_canonical_matches_python_numeric_container_and_datetime_equality(self):
        cases = [(True, 1), (1, 1.0), (-0.0, False), (2**53+1, float(2**53+1)),
            ({"a": [True, {"x": 2}], "b": None}, {"b": None, "a": [1.0, {"x": 2.0}]}),
            ({}, {"a": None}), ([1, 2], [2, 1]), ([1], (1,)),
            (float("inf"), float("inf")), (float("-inf"), float("inf")),
            (float("nan"), float("nan")), (NOW, NOW.astimezone(timezone(timedelta(hours=8)))),
            (NOW, NOW.replace(tzinfo=None)), ("2026-10-30T00:00:00Z", "2026-10-30T00:00:00+00:00")]
        for left, right in cases:
            with self.subTest(left=left, right=right):
                self.assertEqual(keys_equal(left, right), left == right)

    def test_descriptor_and_receipt_keys_follow_different_owners(self):
        first = word(metadata={"number": True, "nested": [1, None]})
        second = word(metadata={"nested": [1.0, None], "number": 1})
        self.assertEqual(review_source_descriptor(first), review_source_descriptor(second))
        self.assertTrue(keys_equal(review_source_descriptor(first), review_source_descriptor(second)))
        receipt = SimpleNamespace(file=first)
        for changes in ({"original_filename": "changed"}, {"etag": "changed"},
                        {"created_at": NOW.astimezone(timezone(timedelta(hours=9)))},
                        {"created_at": NOW.replace(tzinfo=None)}, {"metadata": second.metadata}):
            current = second.model_copy(update=changes)
            a, ac = receipt_file_key(first)
            b, bc = receipt_file_key(current)
            self.assertEqual(ac and bc and a == b, receipt_matches_file(current, receipt))

    def test_persisted_conversion_and_nonfinite_values(self):
        original = word(metadata={"tuple": (1, 2), "time": NOW, "nan": float("nan")})
        serialized = json.dumps(original.model_dump(mode="json"))
        persisted = DocumentFileRecord.model_validate_json(serialized)
        self.assertEqual(document_file_review_projection_from_raw(serialized), document_file_review_projection(persisted))
        self.assertNotEqual(original, persisted)
        for number in (float("nan"), float("inf"), -float("inf")):
            raw = json.dumps({**word().model_dump(mode="json"), "metadata": {"v": number}})
            first = DocumentFileRecord.model_validate_json(raw)
            second = DocumentFileRecord.model_validate_json(raw)
            a, ac = receipt_file_key(first)
            b, bc = receipt_file_key(second)
            self.assertEqual(ac and bc and a == b, first == second)
            self.assertEqual(document_file_review_projection(first)["descriptor_key"],
                             document_file_review_projection(word(metadata={"v": None}))["descriptor_key"])

    def test_stable_raw_times_are_required_only_where_used(self):
        raw = job().model_dump(mode="json")
        raw.pop("created_at")
        with self.assertRaises(DocumentJobListProjectionUnstable):
            document_job_list_projection_from_raw(raw)
        raw = bound_job(receipt=True).model_dump(mode="json")
        raw["prepared_result"]["file"].pop("updated_at")
        with self.assertRaises(DocumentJobListProjectionUnstable):
            document_job_list_projection_from_raw(raw)
        raw = word().model_dump(mode="json")
        raw.pop("updated_at")
        document_file_review_projection_from_raw(raw)
        raw.pop("created_at")
        with self.assertRaises(DocumentJobListProjectionUnstable):
            document_file_review_projection_from_raw(raw)
        raw["file_type"] = "source_pdf"
        self.assertNotIn("receipt_key", document_file_review_projection_from_raw(raw))


class ListSqlV2Tests(TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.addCleanup(self.connection.close)
        self.connection.execute("CREATE TABLE document_jobs (job_id TEXT PRIMARY KEY, payload TEXT, list_query_json TEXT)")
        self.connection.execute("CREATE TABLE document_files (file_id TEXT PRIMARY KEY, payload TEXT, review_query_json TEXT)")
        self.query = DocumentJobListQuery("T", "C", as_of=NOW)
        self.jobs = []
        self.files = {}

    def seed(self, jobs, files=()):
        self.jobs = jobs
        self.files = {file.id: file for file in files}
        for item in jobs:
            raw = json.dumps(item.model_dump(mode="json"), ensure_ascii=False)
            self.connection.execute("INSERT INTO document_jobs VALUES (?, ?, ?)",
                (item.id, raw, json.dumps(document_job_list_projection_from_raw(raw), ensure_ascii=False)))
        for file in files:
            raw = json.dumps(file.model_dump(mode="json"), ensure_ascii=False)
            self.connection.execute("INSERT INTO document_files VALUES (?, ?, ?)",
                (file.id, raw, json.dumps(document_file_review_projection_from_raw(raw), ensure_ascii=False)))

    def run_query(self, query=None):
        from app.infrastructure.persistence.document_job_list_query import query_document_jobs_sql
        return query_document_jobs_sql(self.connection, query or self.query, mysql=False)

    def assert_owner(self, query=None):
        query = query or self.query
        oracle = query_document_job_records(self.jobs, query,
            file_repository=SimpleNamespace(get_document_file=lambda identity: self.files.get(identity)))
        actual = self.run_query(query)
        self.assertEqual([item.id for item in actual.items], [item.id for item in oracle.items])
        self.assertEqual((actual.total, actual.summary, actual.filtered_summary, actual.translation_qa_summary),
                         (oracle.total, oracle.summary, oracle.filtered_summary, oracle.translation_qa_summary))
        self.assertEqual(actual.observed_results, oracle.observed_results)
        return actual

    def test_effective_review_filters_permissions_three_scopes_and_search(self):
        files = [word("w1", "approved"), word("w2", "changed", review_source_revision=1),
                 word("w3", "expired", expires_at=NOW), word("w4", "published", expires_at=NOW)]
        jobs = [bound_job(files[0]), bound_job(word("w2", "changed")), bound_job(files[2]),
                bound_job(files[3], delivery_status="published"),
                job("legacy", mode="en2zh_pdf_to_word", status="succeeded", stage="completed",
                    result_file_id="absent", review_status="approved"),
                job("search", request_snapshot={"source_file": {"original_filename": "Straße Σς İ 中文 %_\\"}}),
                job("other", tenant_id="t"), job("archived", archived_at=NOW), job("deleted", deleted_at=NOW)]
        self.seed(jobs, files)
        for qa in (None, "all", "approved", "unreviewed", "blocked", "needs_fix"):
            for page in (1, 2, 99):
                self.assert_owner(replace(self.query, translation_qa_status=qa, page=page, page_size=2))
        for needle in ("strasse", "σσ", "i\u0307", "中文", "%_\\", "absent"):
            self.assert_owner(replace(self.query, q=needle))
        self.assert_owner(replace(self.query, statuses=("succeeded",), include_archived=True))
        self.assertEqual(self.run_query(replace(self.query, translation_qa_status="approved")).total, 2)

    def test_actual_file_change_and_time_progress_do_not_rewrite_job(self):
        file = word()
        item = bound_job(file, receipt=True)
        self.seed([item], [file])
        before = self.connection.execute("SELECT payload, list_query_json FROM document_jobs").fetchone()
        self.assertEqual(self.run_query().translation_qa_summary["approved"], 1)
        later = self.run_query(replace(self.query, as_of=file.expires_at))
        self.assertEqual(later.translation_qa_summary["unreviewed"], 1)
        changed = file.model_copy(update={"deletion_claim": "claim"})
        raw = json.dumps(changed.model_dump(mode="json"))
        self.connection.execute("UPDATE document_files SET payload=?, review_query_json=?",
            (raw, json.dumps(document_file_review_projection_from_raw(raw))))
        self.assertEqual(self.run_query().translation_qa_summary["unreviewed"], 1)
        self.assertEqual(tuple(before), tuple(self.connection.execute("SELECT payload, list_query_json FROM document_jobs").fetchone()))

    def test_download_naive_error_is_visible_before_filters_and_claim_short_circuits(self):
        file = word(expires_at=(NOW + timedelta(days=1)).replace(tzinfo=None))
        self.seed([bound_job(file)], [file])
        with self.assertRaises(TypeError):
            self.run_query(replace(self.query, q="not matching", translation_qa_status="blocked"))
        changed = file.model_copy(update={"deletion_claim": "claim"})
        raw = json.dumps(changed.model_dump(mode="json"))
        self.connection.execute("UPDATE document_files SET payload=?, review_query_json=?",
            (raw, json.dumps(document_file_review_projection_from_raw(raw))))
        self.assertEqual(self.run_query().translation_qa_summary["unreviewed"], 1)

    def test_receipt_kind_error_reachable_published_and_prior_mismatch(self):
        file = word()
        item = bound_job(file, receipt=True)
        prepared = item.prepared_result.model_copy(update={"file": file.model_copy(update={"expires_at": file.expires_at.replace(tzinfo=None)})})
        item = item.model_copy(update={"prepared_result": prepared})
        item = item.model_copy(update={"current_review_binding": item.current_review_binding.model_copy(update={"receipt_sha256": receipt_identity(item)}), "delivery_status": "published"})
        self.seed([item], [file])
        with self.assertRaises(TypeError):
            self.run_query()
        changed = file.model_copy(update={"review_source_revision": 1})
        raw = json.dumps(changed.model_dump(mode="json"))
        self.connection.execute("UPDATE document_files SET payload=?, review_query_json=?",
            (raw, json.dumps(document_file_review_projection_from_raw(raw))))
        self.assertEqual(self.run_query().translation_qa_summary["approved"], 1)

    def test_nonverified_status_and_static_quality_exception(self):
        binding = ReviewBinding(generation=0, result_file_id=None, binding_state="no_result")
        item = job("a", mode="en2zh_pdf_to_word", review_status="needs_fix", current_review_record_id="r",
                   review_sequence=1, current_review_binding=binding)
        self.seed([item])
        self.assert_owner()
        self.assertEqual(self.run_query().translation_qa_summary["needs_fix"], 1)
        invalid = item.model_copy(update={"quality_summary": {"checks_v1": []}})
        raw = json.dumps(invalid.model_dump(mode="json"))
        self.connection.execute("UPDATE document_jobs SET payload=?, list_query_json=?",
            (raw, json.dumps(document_job_list_projection_from_raw(raw))))
        with self.assertRaises(ValueError):
            self.run_query(replace(self.query, page=99))

    def test_missing_projection_identity_error_and_decode_bound(self):
        from app.domains.document_jobs.list_query import DocumentJobListProjectionUnavailable
        self.seed([bound_job(word("w", "a")), job("b"), job("c")], [word("w", "a")])
        with patch.object(DocumentJobRecord, "model_validate_json", wraps=DocumentJobRecord.model_validate_json) as decode:
            self.run_query(replace(self.query, page_size=1))
            self.assertEqual(decode.call_count, 1)
        with patch.object(DocumentJobRecord, "model_validate_json", side_effect=AssertionError("不应解码")):
            self.assertEqual(self.run_query(replace(self.query, page=99)).items, [])
        projection = document_file_review_projection(word("wrong", "a"))
        self.connection.execute("UPDATE document_files SET review_query_json=?", (json.dumps(projection),))
        with self.assertRaises(ValueError):
            self.run_query()
        self.connection.execute("UPDATE document_files SET review_query_json=NULL")
        with self.assertRaises(DocumentJobListProjectionUnavailable):
            self.run_query()

    def test_table_guard_compares_only_original_fields_without_decoding_job(self):
        from app.infrastructure.persistence.document_job_list_query import is_document_job_table_evidence_snapshot_current_sql
        item = job()
        self.seed([item])
        check = lambda expected: is_document_job_table_evidence_snapshot_current_sql(self.connection, expected, mysql=False)
        with patch.object(DocumentJobRecord, "model_validate_json", side_effect=AssertionError("窄读不应解码")):
            self.assertTrue(check(item))
            self.assertTrue(check(item.model_copy(update={"quality_summary": {"unrelated": True}})))
            self.assertFalse(check(item.model_copy(update={"source_file_id": "changed"})))
            self.assertFalse(check(item.model_copy(update={"id": "missing"})))
        self.connection.execute("UPDATE document_jobs SET list_query_json=NULL")
        from app.domains.document_jobs.list_query import DocumentJobListProjectionUnavailable
        with self.assertRaises(DocumentJobListProjectionUnavailable):
            check(item)

    def test_order_date_timezone_and_id_are_exact(self):
        self.seed([job("a"), job("b", created_at=NOW.astimezone(timezone(timedelta(hours=8)))),
                   job("c", created_at=NOW + timedelta(microseconds=1)), job("d", updated_at=NOW + timedelta(microseconds=2))])
        for order in ("created_at_asc", "created_at_desc", "updated_at_asc", "updated_at_desc"):
            self.assert_owner(replace(self.query, sort=order))
        self.assert_owner(replace(self.query, created_from=NOW, created_to=NOW))
        with self.assertRaises(TypeError):
            self.run_query(replace(self.query, created_from=NOW.replace(tzinfo=None)))

    def test_observation_gate_keeps_original_file_for_page_reason_codes(self):
        original = word()
        cases = [word(file_type="source_pdf"), word(status="pending_upload"),
                 word(tenant_id="other"), word(company_id="other"), word(job_id="other"),
                 word(checksum_sha256=None), word(checksum_sha256=""), word(etag="changed"),
                 word(metadata={"changed": True}), word(expires_at=None),
                 word(review_source_revision=1)]
        for current in cases:
            with self.subTest(patch=current.model_dump()):
                self.connection.execute("DELETE FROM document_jobs")
                self.connection.execute("DELETE FROM document_files")
                self.seed([bound_job(original, receipt=True)], [current])
                result = self.assert_owner()
                self.assertIsNotNone(result.observed_results["a"])
        self.connection.execute("DELETE FROM document_jobs")
        self.connection.execute("DELETE FROM document_files")
        self.seed([bound_job(original, status="running", stage="rendering", review_status="needs_fix")], [original])
        self.assertIsNone(self.assert_owner().observed_results["a"])

    def test_descriptor_overflow_only_after_live_revision_prefix(self):
        original = word()
        overflow = original.model_copy(update={"expires_at": datetime(9999, 12, 31, 23, tzinfo=timezone(-timedelta(hours=14)))})
        item = bound_job(original)
        self.seed([item], [overflow])
        with self.assertRaises(OverflowError):
            self.run_query()
        with self.assertRaises(OverflowError):
            effective_review_job(item, overflow, now=NOW)
        changed = overflow.model_copy(update={"review_source_revision": 1})
        raw = json.dumps(changed.model_dump(mode="json"))
        self.connection.execute("UPDATE document_files SET payload=?, review_query_json=?",
            (raw, json.dumps(document_file_review_projection_from_raw(raw))))
        self.assertEqual(self.run_query().translation_qa_summary["unreviewed"], 1)

    def test_shape_requires_keys_correct_scalar_types_and_missing_columns_fail_explicitly(self):
        from app.domains.document_jobs.list_query import DocumentJobListProjectionUnavailable
        item, file = bound_job(), word()
        self.seed([item], [file])
        for patch_values in ({"version": 1}, {"version": True}, {"created_us": "0"},
                             {"result_present": None}, {"descriptor_key": None}, {"search": [1]}):
            with self.subTest(patch=patch_values):
                projection = {**document_job_list_projection(item), **patch_values}
                self.connection.execute("UPDATE document_jobs SET list_query_json=?", (json.dumps(projection),))
                with self.assertRaises(DocumentJobListProjectionUnavailable):
                    self.run_query()
        self.connection.execute("UPDATE document_jobs SET list_query_json=?", (json.dumps(document_job_list_projection(item)),))
        projection = document_file_review_projection(file)
        del projection["revision"]
        self.connection.execute("UPDATE document_files SET review_query_json=?", (json.dumps(projection),))
        with self.assertRaises(DocumentJobListProjectionUnavailable):
            self.run_query()
        self.connection.execute("ALTER TABLE document_files DROP COLUMN review_query_json")
        with self.assertRaises(DocumentJobListProjectionUnavailable):
            self.run_query()
