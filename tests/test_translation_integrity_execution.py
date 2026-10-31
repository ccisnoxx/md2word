"""正式 Worker、fan-in 与迟到生成件的完整性集成证据。"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.domains.translation.models import TranslationProviderResult, TranslationTextItem
from app.services.document_ir.models import DocumentIR
from tests.test_fastapi_jobs_backend import build_test_runtime


class ControlledProvider:
    """只改自然语言前缀；反例由测试显式注入，保留真实编码请求。"""

    def __init__(self):
        self.requests = []
        self.transform = None

    def translate(self, request):
        self.requests.append(request)
        items = tuple(TranslationTextItem(id=item.id, text="译文：" + item.text) for item in request.items)
        if self.transform is not None:
            items = self.transform(request, items)
        return TranslationProviderResult(items=items)


class TranslationIntegrityExecutionTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="translation_integrity_execution_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.counter = 0

    def make_case(self, *, defer_planning=False, source_blocks=None):
        self.counter += 1
        runtime = build_test_runtime(self.root / str(self.counter), jobs_artifact_storage_backend="local_object")
        execution = runtime.document_job_execution_service
        provider = ControlledProvider()
        execution.document_ir_translation_service = DocumentIRTranslationService(provider)
        source_pdf = runtime.file_upload_service.register_generated_content(
            tenant_id="tenant", company_id="company", job_id="job", created_by="operator",
            file_type="source_pdf", filename="source.pdf", mime_type="application/pdf", content=b"source-pdf",
        )
        job = runtime.document_job_repository.create_document_job(DocumentJobRecord(
            id="job", tenant_id="tenant", company_id="company", created_by="operator",
            source_file_id=source_pdf.id, mode="en2zh_pdf_to_word", document_language="en",
            status="running", stage="ir_converting", template_version_id=execution.template_read_service.resolve_template_version(None).template_version_id,
        ))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("content_list_v2.json", json.dumps(source_blocks if source_blocks is not None else [
                {"type": "text", "text": "Model OPA228 uses 10 V.", "page_idx": 0},
                {"type": "text", "text": "Supply 5 V.", "page_idx": 0},
            ]))
        raw = runtime.file_upload_service.register_generated_content(
            tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
            file_type="mineru_raw_result", filename="mineru.zip", mime_type="application/zip", content=buffer.getvalue(),
        )
        zip_path = self.root / f"source-{self.counter}.zip"
        zip_path.write_bytes(buffer.getvalue())
        document = execution.document_ir_service.convert_zip(
            zip_path, job_id=job.id, source_file_id=job.source_file_id, document_language="en",
        ).document
        planning = (
            patch.object(execution, "_ensure_translation_batches_and_enqueue", side_effect=lambda job, document, **kwargs: job)
            if defer_planning else nullcontext()
        )
        with planning:
            job = execution._register_source_ir_and_enqueue_translation(
                job, raw_file=raw, document_ir=document, image_file_ids=[], image_archive_file=None, trace_id=None,
            )
        batch = None if defer_planning else runtime.document_job_translation_batch_repository.list_translation_batches(job.id)[0]
        return runtime, execution, provider, job, batch, document, raw

    @staticmethod
    def files(runtime, file_type):
        return [file for file in runtime.document_file_repository.list_document_files() if file.file_type == file_type]

    @staticmethod
    def payload(runtime, file):
        return json.loads(runtime.file_upload_service.read_file_content(file))

    def persist_batch(self, runtime, execution, batch):
        with patch.object(execution, "_finalize_translation_generation", return_value=None):
            return execution.execute_translation_batch(batch.id)

    def test_worker_restores_before_persistence_and_fan_in_revalidates(self):
        runtime, execution, provider, job, batch, document, _raw = self.make_case()
        with patch.object(execution, "_render_and_save_word", side_effect=lambda job, **kwargs: job):
            completed = execution.execute_translation_batch(batch.id)
        self.assertEqual(completed.status, "succeeded")
        result_file = runtime.document_file_repository.get_document_file(completed.result_file_id)
        result = self.payload(runtime, result_file)
        self.assertEqual([item["text"] for item in result["items"]], ["译文：Model OPA228 uses 10 V.", "译文：Supply 5 V."])
        self.assertNotIn("MD2W_PT", json.dumps(result["items"]))
        self.assertIn("MD2W_PT", provider.requests[0].items[0].text)
        binding = result["integrity"]["binding"]
        self.assertEqual(binding["source_document_ir_file_id"], job.source_document_ir_file_id)
        self.assertEqual((binding["attempt"], binding["generation"]), (1, 0))
        self.assertEqual(result["integrity"]["status"], "passed")
        target_job = runtime.document_job_repository.get_document_job(job.id)
        target = self.payload(runtime, runtime.document_file_repository.get_document_file(target_job.document_ir_file_id))
        self.assertEqual(target["blocks"][0]["text"], "译文：Model OPA228 uses 10 V.")
        self.assertEqual(document.blocks[0].text, "Model OPA228 uses 10 V.")
        logs = self.files(runtime, "ai_call_log")
        self.assertEqual(len(logs), 1)
        self.assertEqual(self.payload(runtime, logs[0])["integrity"], result["integrity"])

    def test_bad_second_item_is_atomic_and_preserves_specific_retryable_codes(self):
        cases = {
            "missing": (lambda req, items: items[:1], "translation_integrity_item_missing"),
            "extra": (lambda req, items: items + (TranslationTextItem(id="UNTRUSTED_BODY_MARKER", text="extra"),), "translation_integrity_item_extra"),
            "placeholder": (lambda req, items: (items[0], TranslationTextItem(id=items[1].id, text="bad")), "translation_integrity_placeholder_missing"),
            "injection": (lambda req, items: (items[0], TranslationTextItem(id=items[1].id, text=items[1].text + " extra 999 V")), "translation_integrity_technical_mismatch"),
        }
        for name, (transform, expected) in cases.items():
            with self.subTest(name=name):
                runtime, execution, provider, _job, batch, document, _raw = self.make_case()
                before = document.model_dump_json()
                provider.transform = transform
                with patch.object(execution.document_ir_translation_service, "apply_replacements") as apply:
                    failed = execution.execute_translation_batch(batch.id)
                self.assertEqual((failed.status, failed.error_code, failed.attempt_count), ("failed", expected, 1))
                self.assertTrue(failed.retryable)
                self.assertIsNone(failed.result_file_id)
                self.assertEqual(self.files(runtime, "translation_batch_result"), [])
                apply.assert_not_called()
                self.assertEqual(document.model_dump_json(), before)
                logs = self.files(runtime, "ai_call_log")
                self.assertEqual(len(logs), 1)
                log = self.payload(runtime, logs[0])
                self.assertEqual((log["status"], log["error"]["code"]), ("failed", expected))
                self.assertEqual(log["integrity"]["status"], "failed")
                diagnostics = json.dumps([log, failed.error_message, [event.model_dump(mode="json") for event in runtime.document_job_event_repository.list_document_job_events("job")]])
                self.assertNotIn("UNTRUSTED_BODY_MARKER", diagnostics)
                self.assertNotIn("Model OPA228 uses 10 V.", diagnostics)
                provider.transform = None
                with patch.object(execution, "_render_and_save_word", side_effect=lambda job, **kwargs: job):
                    recovered = execution.execute_translation_batch(batch.id)
                self.assertEqual((recovered.status, recovered.attempt_count), ("succeeded", 2))
                self.assertEqual(len(self.files(runtime, "ai_call_log")), 2)

    def test_provider_exception_is_redacted_and_preflight_budget_has_no_call_audit(self):
        runtime, execution, provider, _job, batch, _document, _raw = self.make_case()
        def fail(_request, _items):
            raise RuntimeError("SENSITIVE_PROVIDER_BODY_MARKER Model OPA228 uses 10 V.")
        provider.transform = fail
        failed = execution.execute_translation_batch(batch.id)
        log = self.payload(runtime, self.files(runtime, "ai_call_log")[0])
        self.assertEqual(failed.error_code, "translation_provider_failed")
        self.assertEqual(log["integrity"]["stage"], "provider")
        self.assertIsNone(log["integrity"]["restored_sha256"])
        self.assertNotIn("SENSITIVE_PROVIDER_BODY_MARKER", json.dumps([log, failed.model_dump(mode="json")]))
        runtime, execution, provider, _job, batch, _document, _raw = self.make_case()
        execution.settings.translation_max_chars = 2
        failed = execution.execute_translation_batch(batch.id)
        self.assertEqual(failed.error_code, "translation_request_budget_exceeded")
        self.assertEqual(provider.requests, [])
        self.assertEqual(self.files(runtime, "ai_call_log"), [])

    def test_first_plan_budget_failure_keeps_translation_code_and_safe_evidence(self):
        runtime, execution, provider, job, _batch, _document, _raw = self.make_case(defer_planning=True)
        execution.settings.translation_max_chars = 10
        with patch.object(execution.document_ir_translation_service, "apply_replacements") as apply:
            failed = execution.execute_job(job.id)
        self.assertEqual((failed.status, failed.failed_stage, failed.error_code), ("failed", "translating", "translation_failed"))
        failures = [event for event in runtime.document_job_event_repository.list_document_job_events(job.id) if event.event_type == "stage_failed"]
        self.assertEqual(len(failures), 1)
        evidence = failures[0].payload["integrity"]
        self.assertEqual((evidence["status"], evidence["stage"], evidence["error_code"]), ("failed", "budget", "translation_request_budget_exceeded"))
        self.assertIsNone(evidence["binding"])
        self.assertTrue(evidence["source_sha256"].startswith("sha256:"))
        self.assertNotIn("Model OPA228 uses 10 V.", json.dumps(failures[0].model_dump(mode="json")))
        self.assertEqual(provider.requests, [])
        self.assertEqual(runtime.document_job_translation_batch_repository.list_translation_batches(job.id), [])
        for file_type in ("ai_call_log", "translation_batch_result", "generated_word"):
            self.assertEqual(self.files(runtime, file_type), [])
        current = runtime.document_job_repository.get_document_job(job.id)
        self.assertEqual(current.document_ir_file_id, job.document_ir_file_id)
        self.assertEqual(current.source_document_ir_file_id, job.source_document_ir_file_id)
        self.assertEqual(len(self.files(runtime, "document_ir")), 1)
        apply.assert_not_called()

    def test_first_formula_boundary_failure_preserves_source_without_provider_or_fake_integrity(self):
        source = r"Before $\text{High <b>Low</b>}$ After"
        runtime, execution, provider, job, _batch, _document, _raw = self.make_case(
            defer_planning=True,
            source_blocks=[{"type": "table", "table_body": f"<table><tr><td>{source}</td></tr></table>", "page_idx": 0}],
        )
        with patch.object(execution.document_ir_translation_service, "apply_replacements") as apply:
            failed = execution.execute_job(job.id)
        self.assertEqual((failed.status, failed.failed_stage, failed.error_code), ("failed", "translating", "translation_failed"))
        failures = [event for event in runtime.document_job_event_repository.list_document_job_events(job.id) if event.event_type == "stage_failed"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].payload["formula_protection"], {
            "code": "translation_formula_boundary_unprotected", "formula_count": 1, "unprotected_count": 1,
        })
        self.assertNotIn("integrity", failures[0].payload)
        self.assertNotIn("High", json.dumps(failures[0].model_dump(mode="json")))
        self.assertEqual(provider.requests, [])
        self.assertEqual(runtime.document_job_translation_batch_repository.list_translation_batches(job.id), [])
        for file_type in ("ai_call_log", "translation_batch_result", "generated_word"):
            self.assertEqual(self.files(runtime, file_type), [])
        self.assertEqual(failed.source_document_ir_file_id, job.source_document_ir_file_id)
        self.assertEqual(len(self.files(runtime, "document_ir")), 1)
        apply.assert_not_called()

    def test_old_math_dom_root_plan_is_not_rewritten_or_silently_backfilled(self):
        formula = r"\text{High Low}"
        runtime, execution, provider, job, _batch, document, _raw = self.make_case(
            defer_planning=True,
            source_blocks=[{"type": "table", "table_body": f"<table><tr><td>Before<eq>{formula}</eq>After</td></tr></table>", "page_idx": 0}],
        )
        current_plan = execution._build_expected_translation_plans(job, document)[0]
        legacy_plan = replace(
            current_plan,
            item_ids=("block_0001.html.0000", "block_0001.html.0001", "block_0001.html.0002"),
            item_count=3,
            char_count=current_plan.char_count + len(formula),
        )
        repository = runtime.document_job_translation_batch_repository
        installed = repository.ensure_translation_batch_roots(job.id, generation=job.retry_count, expected_plans=[legacy_plan])
        with patch.object(execution.document_ir_translation_service, "apply_replacements") as apply:
            failed = execution.execute_job(job.id)
        self.assertEqual((failed.status, failed.failed_stage, failed.error_code), ("failed", "translating", "translation_batch_tree_invalid"))
        remaining = repository.list_translation_batches(job.id)
        self.assertEqual([batch.id for batch in remaining], [batch.id for batch in installed])
        self.assertEqual(remaining[0].item_ids, list(legacy_plan.item_ids))
        self.assertEqual((remaining[0].item_count, remaining[0].char_count), (legacy_plan.item_count, legacy_plan.char_count))
        self.assertEqual(provider.requests, [])
        self.assertEqual(self.files(runtime, "translation_batch_result"), [])
        self.assertEqual(self.files(runtime, "generated_word"), [])
        self.assertEqual(failed.source_document_ir_file_id, job.source_document_ir_file_id)
        apply.assert_not_called()

    def test_worker_rejects_previously_installed_unprotected_math_before_provider(self):
        # 模拟升级前已安装的合法旧计划；新消费者不能沿旧计划发送裸数学。
        with patch.object(DocumentIRTranslationService, "_validate_formula_protection"):
            runtime, execution, provider, job, batch, _document, _raw = self.make_case(
                source_blocks=[{"type": "table", "table_body": r"<table><tr><td>Before \frac{High}{Low} After</td></tr></table>", "page_idx": 0}],
            )
        execution.execute_translation_batch(batch.id)
        failed = runtime.document_job_repository.get_document_job(job.id)
        self.assertEqual((failed.status, failed.failed_stage, failed.error_code), ("failed", "translating", "translation_failed"))
        failures = [event for event in runtime.document_job_event_repository.list_document_job_events(job.id) if event.event_type == "stage_failed"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].payload["formula_protection"]["code"], "translation_formula_boundary_unprotected")
        self.assertNotIn("integrity", failures[0].payload)
        self.assertEqual(provider.requests, [])
        for file_type in ("ai_call_log", "translation_batch_result", "generated_word"):
            self.assertEqual(self.files(runtime, file_type), [])
        self.assertEqual(failed.source_document_ir_file_id, job.source_document_ir_file_id)

    def test_audit_failure_is_visible_and_never_recorded_twice(self):
        _runtime, execution, _provider, _job, batch, _document, _raw = self.make_case()
        with patch.object(execution.translation_audit_service, "build_recorder") as build:
            recorder = build.return_value
            recorder.record_success.side_effect = OSError("audit write failed")
            with self.assertRaisesRegex(OSError, "audit write failed"):
                execution.execute_translation_batch(batch.id)
        recorder.record_success.assert_called_once()
        recorder.record_failure.assert_not_called()

    def test_fan_in_rejects_missing_evidence_origin_generation_attempt_hash_shape_and_technical_changes(self):
        def edit_binding(payload, key, value):
            payload["integrity"]["binding"][key] = value
        mutations = {
            "no_evidence": lambda p: p.pop("integrity"),
            "source": lambda p: p.update(source_document_ir_file_id="other-source"),
            "generation": lambda p: p.update(generation=1),
            "attempt": lambda p: p.update(attempt=2),
            "generation_type": lambda p: p.update(generation=0.0),
            "attempt_type": lambda p: p.update(attempt=True),
            "missing_parent": lambda p: p.pop("parent_batch_id"),
            "profile_hash": lambda p: edit_binding(p, "profile_snapshot_hash", "sha256:wrong"),
            "prompt_hash": lambda p: edit_binding(p, "prompt_content_hash", "sha256:wrong"),
            "term_hash": lambda p: edit_binding(p, "term_snapshot_hash", "sha256:wrong"),
            "source_hash": lambda p: p["integrity"].update(source_sha256="sha256:wrong"),
            "restored_hash": lambda p: p["integrity"].update(restored_sha256="sha256:wrong"),
            "shape": lambda p: p["items"][0].update(text=42),
            "duplicate_id": lambda p: p["items"].append(p["items"][0]),
            "technical": lambda p: p["items"][1].update(text="译文：Supply 999 V."),
            "checksum": None,
            "source_wrong_job": None,
            "source_checksum": None,
            "source_role": None,
            "source_pointer": None,
            "result_owner": None,
            "result_generation": None,
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                runtime, execution, _provider, job, batch, _document, _raw = self.make_case()
                batch = self.persist_batch(runtime, execution, batch)
                result_file = runtime.document_file_repository.get_document_file(batch.result_file_id)
                if name == "checksum":
                    runtime.document_file_repository.update_document_file(result_file.id, checksum_sha256="sha256:wrong")
                elif name.startswith("source_") and mutate is None:
                    source = runtime.document_file_repository.get_document_file(job.source_document_ir_file_id)
                    if name == "source_wrong_job":
                        runtime.document_file_repository.update_document_file(source.id, job_id="other-job")
                    elif name == "source_checksum":
                        runtime.document_file_repository.update_document_file(source.id, checksum_sha256="sha256:wrong")
                    elif name == "source_role":
                        runtime.document_file_repository.update_document_file(source.id, metadata={**source.metadata, "translation": {"role": "translated", "applied": True}})
                    else:
                        runtime.document_job_repository.update_document_job(job.id, source_document_ir_file_id="other-source")
                elif name == "result_owner":
                    runtime.document_file_repository.update_document_file(result_file.id, tenant_id="other-tenant")
                elif name == "result_generation":
                    runtime.document_file_repository.update_document_file(result_file.id, metadata={**result_file.metadata, "retry_count": 1})
                else:
                    payload = self.payload(runtime, result_file)
                    mutate(payload)
                    edited = runtime.file_upload_service.register_generated_content(
                        tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                        file_type="translation_batch_result", filename=result_file.original_filename,
                        mime_type="application/json", content=json.dumps(payload).encode(), metadata=result_file.metadata,
                    )
                    runtime.document_job_translation_batch_repository.update_translation_batch(batch.id, result_file_id=edited.id)
                with patch.object(execution.document_ir_translation_service, "apply_replacements") as apply:
                    final = execution._finalize_translation_generation(job.id, generation=0, trace_id=None)
                self.assertEqual((final.status, final.error_code), ("failed", "translation_failed"))
                apply.assert_not_called()
                self.assertIsNone(final.document_ir_file_id)
                self.assertEqual(self.files(runtime, "generated_word"), [])

    def test_fan_in_rejects_overlap_between_successful_leaf_batches(self):
        runtime, execution, _provider, job, batch, _document, _raw = self.make_case()
        batch = self.persist_batch(runtime, execution, batch)
        original = runtime.document_file_repository.get_document_file(batch.result_file_id)
        payload = self.payload(runtime, original)
        second_id = batch.id + "_overlap"
        payload["batch_id"] = second_id
        payload["integrity"]["binding"]["batch_id"] = second_id
        second = runtime.file_upload_service.register_generated_content(
            tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
            file_type="translation_batch_result", filename=second_id + ".json", mime_type="application/json",
            content=json.dumps(payload).encode(), metadata={**original.metadata, "batch_id": second_id},
        )
        runtime.document_job_translation_batch_repository.create_translation_batch(batch.model_copy(update={"id": second_id, "result_file_id": second.id}))
        with patch.object(execution.document_ir_translation_service, "apply_replacements") as apply:
            final = execution._finalize_translation_generation(job.id, generation=0, trace_id=None)
        self.assertEqual(final.status, "failed")
        self.assertIn("translation_batch_tree_invalid", final.error_message)
        apply.assert_not_called()

    def test_generation_changed_during_provider_cannot_register_success_or_enter_fan_in(self):
        runtime, execution, provider, job, batch, _document, _raw = self.make_case()
        def advance(_request, items):
            runtime.document_job_repository.update_document_job(job.id, retry_count=1)
            return items
        provider.transform = advance
        with patch.object(execution.document_ir_translation_service, "apply_replacements") as apply:
            execution.execute_translation_batch(batch.id)
            execution._finalize_translation_generation(job.id, generation=0, trace_id=None)
        self.assertEqual(self.files(runtime, "translation_batch_result"), [])
        apply.assert_not_called()
        self.assertIsNone(runtime.document_job_repository.get_document_job(job.id).document_ir_file_id)

    def assert_stored_bytes(self, runtime, snapshots):
        for file_id, (content, checksum) in snapshots.items():
            record = runtime.document_file_repository.get_document_file(file_id)
            self.assertEqual(runtime.file_upload_service.read_file_content(record), content)
            self.assertEqual(record.checksum_sha256, checksum)
            self.assertEqual(checksum, "sha256:" + hashlib.sha256(content).hexdigest())

    def snapshot_files(self, runtime):
        return {file.id: (runtime.file_upload_service.read_file_content(file), file.checksum_sha256)
                for file in runtime.document_file_repository.list_document_files()}

    def test_late_old_generation_writes_cannot_overwrite_winning_or_historical_source_target_or_docx(self):
        for delayed_type in ("source", "translated", "generated_word"):
            with self.subTest(delayed_type=delayed_type):
                runtime, execution, _provider, job, batch, document, raw = self.make_case()
                register = runtime.file_upload_service.register_generated_content
                register_candidate = runtime.file_upload_service.register_result_candidate
                delayed = False
                snapshots = {}
                rejected = []
                cas = runtime.document_job_repository.update_document_job_if_current
                prepare = runtime.document_job_repository.prepare_document_job_result
                def observe_cas(job_id, **kwargs):
                    result = cas(job_id, **kwargs)
                    if kwargs.get("expected_retry_count") == 0 and result is None:
                        rejected.append(kwargs)
                    return result

                def observe_prepare(job_id, **kwargs):
                    result = prepare(job_id, **kwargs)
                    if kwargs.get("expected_retry_count") == 0 and result is None:
                        rejected.append(kwargs)
                    return result

                def interleave_after_barrier(content, retry_count, kind):
                    nonlocal delayed, snapshots
                    if not delayed and kind == delayed_type and retry_count == 0:
                        delayed = True
                        new_job = runtime.document_job_repository.update_document_job(
                            job.id, retry_count=1, status="running", stage="ir_converting", source_document_ir_file_id=None,
                            document_ir_file_id=None, result_file_id=None,
                        )
                        new_document = document.model_copy(deep=True)
                        for block in new_document.blocks:
                            if block.text:
                                block.text = "New generation " + block.text
                        execution._register_source_ir_and_enqueue_translation(
                            new_job, raw_file=raw, document_ir=new_document, image_file_ids=[], image_archive_file=None, trace_id=None,
                        )
                        new_batch = runtime.document_job_translation_batch_repository.list_translation_batches(job.id, generation=1)[0]
                        execution.execute_translation_batch(new_batch.id)
                        winner = runtime.document_job_repository.get_document_job(job.id)
                        self.assertEqual((winner.status, winner.retry_count), ("succeeded", 1))
                        snapshots = self.snapshot_files(runtime)
                        winner_id = (winner.source_document_ir_file_id if delayed_type == "source" else
                                     winner.document_ir_file_id if delayed_type == "translated" else winner.result_file_id)
                        self.assertNotEqual(content, snapshots[winner_id][0])

                def interleave(**kwargs):
                    role = kwargs.get("metadata", {}).get("translation", {}).get("role")
                    kind = role if kwargs["file_type"] == "document_ir" else kwargs["file_type"]
                    interleave_after_barrier(
                        kwargs["content"], kwargs.get("metadata", {}).get("retry_count"), kind,
                    )
                    return register(**kwargs)

                def interleave_candidate(**kwargs):
                    interleave_after_barrier(
                        kwargs["content"], kwargs.get("metadata", {}).get("retry_count"), "generated_word",
                    )
                    return register_candidate(**kwargs)

                with patch.object(runtime.file_upload_service, "register_generated_content", side_effect=interleave), patch.object(
                    runtime.document_job_repository, "update_document_job_if_current", side_effect=observe_cas,
                ), patch.object(runtime.document_job_repository, "prepare_document_job_result", side_effect=observe_prepare), patch.object(
                    runtime.file_upload_service, "register_result_candidate", side_effect=interleave_candidate,
                ):
                    if delayed_type == "source":
                        execution._register_source_ir_and_enqueue_translation(
                            job, raw_file=raw, document_ir=document, image_file_ids=[], image_archive_file=None, trace_id=None,
                        )
                    else:
                        execution.execute_translation_batch(batch.id)
                self.assertTrue(delayed)
                self.assertTrue(rejected)
                self.assert_stored_bytes(runtime, snapshots)
                winner = runtime.document_job_repository.get_document_job(job.id)
                self.assertEqual((winner.status, winner.retry_count), ("succeeded", 1))
                self.assertIn(winner.document_ir_file_id, snapshots)
                self.assertIn(winner.result_file_id, snapshots)
                all_files = runtime.document_file_repository.list_document_files()
                self.assertEqual(len({file.object_key for file in all_files}), len(all_files))

    def test_late_old_attempt_cas_rejection_preserves_winning_result_evidence_and_output_bytes(self):
        runtime, execution, provider, job, batch, _document, _raw = self.make_case()
        provider.transform = lambda request, items: tuple(TranslationTextItem(
            id=item.id, text=("新尝试：" if request.attempt == 2 else "旧尝试：") + item.text,
        ) for item in items)
        register = runtime.file_upload_service.register_generated_content
        delayed = False
        snapshots = {}
        winner_result_id = None
        rejected = []
        cas = runtime.document_job_translation_batch_repository.update_translation_batch_if_current
        def observe_cas(batch_id, **kwargs):
            result = cas(batch_id, **kwargs)
            if kwargs.get("status") == "succeeded" and result is None:
                rejected.append(kwargs)
            return result
        def interleave(**kwargs):
            nonlocal delayed, snapshots, winner_result_id
            if not delayed and kwargs["file_type"] == "translation_batch_result" and kwargs["metadata"]["attempt_count"] == 1:
                delayed = True
                # 模拟既有过期 lease 恢复后新尝试胜出；不增加 fencing 协议。
                runtime.document_job_translation_batch_repository.update_translation_batch(batch.id, status="queued")
                execution.execute_translation_batch(batch.id)
                winner = runtime.document_job_translation_batch_repository.get_translation_batch(batch.id)
                self.assertEqual((winner.status, winner.attempt_count), ("succeeded", 2))
                winner_result_id = winner.result_file_id
                snapshots = self.snapshot_files(runtime)
                self.assertNotEqual(kwargs["content"], snapshots[winner_result_id][0])
            return register(**kwargs)
        with patch.object(runtime.file_upload_service, "register_generated_content", side_effect=interleave), patch.object(
            runtime.document_job_translation_batch_repository, "update_translation_batch_if_current", side_effect=observe_cas,
        ):
            execution.execute_translation_batch(batch.id)
        self.assertTrue(rejected)
        self.assert_stored_bytes(runtime, snapshots)
        winner = runtime.document_job_translation_batch_repository.get_translation_batch(batch.id)
        self.assertEqual(winner.result_file_id, winner_result_id)
        result = self.payload(runtime, runtime.document_file_repository.get_document_file(winner.result_file_id))
        self.assertEqual(result["integrity"]["binding"]["attempt"], 2)
        self.assertTrue(result["items"][0]["text"].startswith("新尝试："))
        self.assertEqual(len(self.files(runtime, "translation_batch_result")), 2)
        self.assertEqual(runtime.document_job_repository.get_document_job(job.id).status, "succeeded")
