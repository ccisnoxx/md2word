"""覆盖正式翻译的整批完整性与默认表示隐私合同。"""

from dataclasses import FrozenInstanceError, asdict, replace
import hashlib
import json
from unittest import TestCase
from unittest.mock import patch

from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.domains.translation.models import TermVersionSnapshot, TranslationTermEntry, TranslationTextItem, TranslationProviderResult
from app.domains.translation.protected_tokens import encode
from tests import test_document_ir_translation as translation_tests
from app.domains.translation.integrity import (
    TranslationIntegrityValidator, TranslationIntegrityError, TranslationIntegrityBinding,
    INTEGRITY_SCHEMA_VERSION, INTEGRITY_INSTRUCTION_VERSION, INTEGRITY_INSTRUCTION_SHA256, items_sha256,
)
from app.domains.translation.provider import OpenAICompatibleTranslationProvider, TranslationProviderResponseError
from app.domains.translation.models import TranslationPromptSnapshot, TranslationProfileSnapshot, TranslationProviderRequest


class TranslationIntegrityTests(TestCase):
    def test_preserved_placeholders_do_not_allow_added_raw_quantity(self):
        source = (TranslationTextItem("item", "Voltage 5 V"),)
        encoded = encode(source)
        result = TranslationProviderResult((TranslationTextItem("item", encoded.items[0].text + " extra 999 V"),))
        service = DocumentIRTranslationService(translation_tests.FakeTranslationProvider())
        with self.assertRaises(ValueError):
            service.validator.validate(source, encoded, result)

    def test_real_term_match_context_is_hidden_without_changing_trace(self):
        service = DocumentIRTranslationService(translation_tests.FakeTranslationProvider())
        text = "隐私正文标记 low noise 后文"
        items = [TranslationTextItem("item", text)]
        entry = TranslationTermEntry("en2zh", "low noise", "低噪声", "v1", status="publishable")
        terms = TermVersionSnapshot("terms", "en2zh", "v1", "sha256:terms", (entry,))
        captured = []
        original = service._select_non_overlapping_matches
        def observe(matches):
            captured.extend(matches)
            return original(matches)
        with patch.object(service, "_select_non_overlapping_matches", side_effect=observe):
            request = service.build_provider_request(
                translation_tests.DocumentIRTranslationTests()._make_document_ir(), items,
                term_version=terms, language_pair="en2zh", batch_id="batch",
            ).request
        self.assertEqual(len(captured), 1)
        match = captured[0]
        self.assertEqual(match.context_snippet, text)
        self.assertEqual((match.match_start, match.match_end), (text.index("low noise"), text.index("low noise") + len("low noise")))
        self.assertEqual(request.terms, (entry,))
        self.assertEqual(request.term_traces[0].context_snippet, text)
        self.assertEqual(asdict(match)["context_snippet"], text)
        self.assertEqual(asdict(request.term_traces[0])["context_snippet"], text)
        self.assertEqual(replace(match), match)
        self.assertFalse(hasattr(match, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            match.context_snippet = "被改写"
        with self.assertRaises(FrozenInstanceError):
            request.term_traces[0].context_snippet = "被改写"
        for value in (match, [match], request.term_traces[0], request.term_traces):
            self.assertNotIn("隐私正文标记", repr(value))

    def assert_rejected(self, source, batch, items, code):
        before = (source, batch)
        with self.assertRaises(TranslationIntegrityError) as context:
            TranslationIntegrityValidator().validate(source, batch, TranslationProviderResult(items))
        error = context.exception
        self.assertEqual(error.code, code)
        self.assertEqual(error.evidence.status, "failed")
        self.assertEqual(error.evidence.error_code, code)
        self.assertFalse(hasattr(error, "items"))
        self.assertFalse(hasattr(error, "replacements"))
        self.assertEqual((source, batch), before)
        return error

    def test_legal_natural_language_and_in_item_token_movement(self):
        source = (TranslationTextItem("first", "Typical OPA228 High 25°C and 25°C"),)
        batch = encode(source)
        model, first, second = [token.placeholder for token in batch.occurrences]
        items = (TranslationTextItem("first", f"高 {second}，典型值 {model}，温度 {first}"),)
        checked = TranslationIntegrityValidator().validate(source, batch, TranslationProviderResult(items))
        self.assertEqual(checked.items, (TranslationTextItem("first", "高 25°C，典型值 OPA228，温度 25°C"),))
        self.assertEqual(checked.replacements, {"first": "高 25°C，典型值 OPA228，温度 25°C"})
        self.assertEqual(checked.evidence.status, "passed")
        self.assertEqual(checked.evidence.expected_token_counts, (("model", 1), ("quantity", 2)))
        self.assertEqual(checked.evidence.expected_token_counts, checked.evidence.actual_token_counts)
        with self.assertRaises(FrozenInstanceError):
            checked.items = ()
        with self.assertRaises(FrozenInstanceError):
            checked.evidence.status = "failed"

    def test_supported_technical_categories_roundtrip_and_reject_extra_literals(self):
        vectors = (
            "−40–+85 °C", "±0.5%", "3 nV/sqrt(Hz)", "10 V/us", "6 мкА",
            "0x0028[4:0]", "DATA[4:0]", "VCC1_VCO", "OPA228", "SOIC-8",
            "IEEE 802.3", "v1.2.3", "TA = 25°C", "$V=IR$", "≤ 1.5e-3", "2–4",
            "ADC", "https://example.test/a?x=1", "tech@example.test", "{{PH_001}}",
        )
        validator = TranslationIntegrityValidator()
        for literal in vectors:
            with self.subTest(literal=literal):
                source = (TranslationTextItem("item", "Typical " + literal + "; High"),)
                batch = encode(source)
                self.assertTrue(batch.occurrences)
                response = tuple(TranslationTextItem(item.id, item.text.replace("Typical", "典型值").replace("High", "高")) for item in batch.items)
                checked = validator.validate(source, batch, TranslationProviderResult(response))
                self.assertEqual(checked.items[0].text, "典型值 " + literal + "; 高")
                for injected in ("999 V", "0x0042[7:0]", "OPA999", "V_OUT = V_IN + 9 V", "25°C"):
                    self.assert_rejected(source, batch, (TranslationTextItem("item", response[0].text + "; " + injected),), "translation_integrity_technical_mismatch")
        units = (TranslationTextItem("unit", " V/√Hz "),)
        self.assertEqual(validator.validate(units, encode(units), TranslationProviderResult(encode(units).items)).items, units)

    def test_id_first_error_priority_is_duplicate_missing_extra_then_order(self):
        source = (TranslationTextItem("a", "Natural text"), TranslationTextItem("b", "Other text"))
        batch = encode(source)
        cases = (
            (("a", "a", "evil"), "duplicate"),
            (("a", "evil"), "missing"),
            (("a", "b", "evil"), "extra"),
            (("b", "a"), "order"),
            ((" a", "b"), "missing"),
        )
        for ids, suffix in cases:
            with self.subTest(ids=ids):
                error = self.assert_rejected(source, batch, tuple(TranslationTextItem(item_id, "合法译文") for item_id in ids), "translation_integrity_item_" + suffix)
                self.assertNotIn("evil", repr(error))
                self.assertNotIn("evil", str(error.evidence))

    def test_fake_provider_dto_shape_cannot_bypass_validation(self):
        source = (TranslationTextItem("a", "Natural text"),)
        batch = encode(source)
        for result in (
            None, {"items": [{"id": "a", "text": "译文"}]},
            TranslationProviderResult([TranslationTextItem("a", "译文")]),
            TranslationProviderResult(({"id": "a", "text": "译文"},)),
            TranslationProviderResult((TranslationTextItem(123, "译文"),)),
            TranslationProviderResult((TranslationTextItem("a", 123),)),
            TranslationProviderResult((TranslationTextItem("a", None),)),
            TranslationProviderResult((TranslationTextItem("", "译文"),)),
            TranslationProviderResult((TranslationTextItem("a", " \n"),)),
        ):
            with self.subTest(result_type=type(result).__name__):
                with self.assertRaises(TranslationIntegrityError) as context:
                    TranslationIntegrityValidator().validate(source, batch, result)
                self.assertEqual(context.exception.code, "translation_integrity_invalid_response")
                self.assertIsNone(context.exception.evidence.response_sha256)

    def test_input_and_metadata_are_checked_before_response(self):
        source = (TranslationTextItem("a", "Typical OPA228"),)
        batch = encode(source)
        variants = (
            replace(batch, namespace="wrong"), replace(batch, item_ids=("other",)),
            replace(batch, items=source),
            replace(batch, occurrences=(replace(batch.occurrences[0], original_text="OPA999"),)),
            replace(batch, occurrences=(replace(batch.occurrences[0], start=0),)),
            encode((TranslationTextItem("a", "Typical OPA999"),)),
        )
        for wrong in variants:
            with self.subTest(namespace=wrong.namespace):
                error = self.assert_rejected(source, wrong, batch.items, "translation_integrity_metadata_mismatch")
                self.assertEqual(error.evidence.stage, "metadata")
        invalid_sources = ([source[0]], (source[0], source[0]), (TranslationTextItem("", "原文"),))
        for invalid in invalid_sources:
            with self.assertRaises(TranslationIntegrityError) as context:
                TranslationIntegrityValidator().validate(invalid, batch, TranslationProviderResult(batch.items))
            self.assertEqual(context.exception.code, "translation_integrity_invalid_input")

    def test_placeholder_ownership_count_and_syntax_are_fail_closed(self):
        source = (TranslationTextItem("a", "Typical OPA228"), TranslationTextItem("b", "High 25°C"))
        batch = encode(source)
        first, second = [token.placeholder for token in batch.occurrences]
        cases = (
            ((TranslationTextItem("a", "翻译"), batch.items[1]), "missing"),
            ((TranslationTextItem("a", first + first), batch.items[1]), "duplicate"),
            ((TranslationTextItem("a", "{{MD2W_PT_v1_999_1}}"), batch.items[1]), "unknown"),
            ((TranslationTextItem("a", first.replace("MD2W", "M D2W")), batch.items[1]), "malformed"),
            ((TranslationTextItem("a", second), TranslationTextItem("b", first)), "wrong_item"),
        )
        for items, suffix in cases:
            with self.subTest(suffix=suffix):
                self.assert_rejected(source, batch, items, "translation_integrity_placeholder_" + suffix)
        no_tokens = (TranslationTextItem("a", "Natural words"),)
        self.assert_rejected(no_tokens, encode(no_tokens), (TranslationTextItem("a", "{{MD2W_PT_v1_0_1}}"),), "translation_integrity_placeholder_unknown")
        self.assert_rejected(no_tokens, encode(no_tokens), (TranslationTextItem("a", "普通译文; 999 V"),), "translation_integrity_technical_mismatch")

    def test_source_literal_collision_is_restored_once(self):
        source = (TranslationTextItem("a", "Literal {{MD2W_PT_v1_0_1}} and {{PH_001}} OPA228"),)
        batch = encode(source)
        self.assertEqual(batch.namespace, "{{MD2W_PT_v1_1_")
        checked = TranslationIntegrityValidator().validate(source, batch, TranslationProviderResult(batch.items))
        self.assertEqual(checked.items, source)

    def test_second_item_technical_failure_returns_no_partial_and_changes_nothing(self):
        source = (TranslationTextItem("a", "Typical OPA228"), TranslationTextItem("b", "High 25°C"))
        batch = encode(source)
        before_source, before_batch = asdict(source[0]), asdict(batch)
        items = (batch.items[0], TranslationTextItem("b", batch.items[1].text + "; 999 V"))
        error = self.assert_rejected(source, batch, items, "translation_integrity_technical_mismatch")
        self.assertEqual(error.evidence.checked_item_count, 2)
        self.assertEqual(error.evidence.failed_item_count, 1)
        self.assertEqual(asdict(source[0]), before_source)
        self.assertEqual(asdict(batch), before_batch)
        self.assertEqual(batch.items[0].text, items[0].text)

    def test_inventory_is_per_item_and_preserves_multiplicity_and_category(self):
        source = (TranslationTextItem("a", "Value 25°C"), TranslationTextItem("b", "Other words"))
        batch = encode(source)
        self.assert_rejected(source, batch, (batch.items[0], TranslationTextItem("b", "Other 25°C")), "translation_integrity_technical_mismatch")
        # 同样字节因自然语言邻接变为完整单位或公式时也不猜测等价。
        natural = (TranslationTextItem("a", "V is a symbol"),)
        self.assert_rejected(natural, encode(natural), (TranslationTextItem("a", "V"),), "translation_integrity_technical_mismatch")

    def test_evidence_has_canonical_hashes_counts_and_safe_stage_progress(self):
        source = (TranslationTextItem("a", "私密源文 Typical OPA228"),)
        batch = encode(source)
        result = TranslationProviderResult((TranslationTextItem("a", batch.items[0].text.replace("私密源文 Typical", "私密译文")),))
        checked = TranslationIntegrityValidator().validate(source, batch, result)
        payload = checked.evidence.to_dict()
        canonical = json.dumps([{"id": "a", "text": source[0].text}], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.assertEqual(payload["source_sha256"], "sha256:" + hashlib.sha256(canonical).hexdigest())
        self.assertEqual(payload["source_sha256"], items_sha256(source))
        self.assertEqual(payload["schema_version"], INTEGRITY_SCHEMA_VERSION)
        self.assertEqual(payload["instruction_version"], INTEGRITY_INSTRUCTION_VERSION)
        self.assertEqual(payload["instruction_sha256"], INTEGRITY_INSTRUCTION_SHA256)
        self.assertEqual(payload["source_char_count"], len(source[0].text))
        self.assertEqual(payload["encoded_char_count"], len(batch.items[0].text))
        self.assertEqual(payload["response_char_count"], len(result.items[0].text))
        self.assertEqual(payload["restored_char_count"], len(checked.items[0].text))
        self.assertEqual(payload["expected_token_counts"], {"model": 1})
        payload["expected_token_counts"]["model"] = 99
        self.assertEqual(checked.evidence.expected_token_counts, (("model", 1),))
        for value in (checked, checked.evidence, checked.evidence.to_dict()):
            self.assertNotIn("私密源文", repr(value))
            self.assertNotIn("私密译文", repr(value))
        failed = TranslationIntegrityValidator().call_failure_evidence(source, batch, error_code="translation_provider_failed")
        self.assertEqual(failed.stage, "provider")
        self.assertEqual(failed.status, "failed")
        self.assertIsNone(failed.response_sha256)
        self.assertIsNone(failed.restored_sha256)

    def test_persisted_gate_requires_binding_hashes_pass_status_and_technical_inventory(self):
        source = (TranslationTextItem("a", "Typical OPA228"),)
        batch = encode(source)
        validator = TranslationIntegrityValidator()
        checked = validator.validate(source, batch, TranslationProviderResult(batch.items))
        binding = TranslationIntegrityBinding("job", "batch", "root", None, 2, 3, "source-file", "sha256:source", "sha256:profile", "sha256:prompt", "sha256:terms")
        evidence = checked.evidence.bind(binding)
        payload = evidence.to_dict()
        loaded = validator.validate_persisted(source, checked.items, payload, binding=binding)
        self.assertEqual(loaded.items, checked.items)
        self.assertEqual(loaded.evidence, evidence)
        self.assertIsNone(checked.evidence.binding)
        variants = [None, {}, {**payload, "status": "failed"}, {**payload, "source_sha256": "sha256:wrong"}, {**payload, "restored_sha256": "sha256:wrong"}, {**payload, "instruction_sha256": "sha256:wrong"}, {**payload, "response_sha256": None}, {**payload, "response_char_count": True}, {**payload, "binding": {**payload["binding"], "generation": 1}}, {**payload, "extra": "field"}]
        for supplied in variants:
            with self.subTest(field_type=type(supplied).__name__):
                with self.assertRaises(TranslationIntegrityError) as context:
                    validator.validate_persisted(source, checked.items, supplied, binding=binding)
                self.assertEqual(context.exception.code, "translation_integrity_evidence_missing" if supplied is None else "translation_integrity_evidence_mismatch")
        with self.assertRaises(TranslationIntegrityError) as context:
            validator.validate_persisted(source, (TranslationTextItem("a", "Typical OPA999"),), payload, binding=binding)
        self.assertEqual(context.exception.code, "translation_integrity_technical_mismatch")

    def test_persisted_evidence_does_not_coerce_boolean_or_float_counts_and_bindings(self):
        source = (TranslationTextItem("a", "Typical OPA228"),)
        validator = TranslationIntegrityValidator()
        batch = encode(source)
        checked = validator.validate(source, batch, TranslationProviderResult(batch.items))
        binding = TranslationIntegrityBinding("job", "batch", "root", None, 1, 1, "source-file", "sha256:source", None, None, None)
        payload = checked.evidence.bind(binding).to_dict()
        variants = (
            {**payload, "expected_item_count": True},
            {**payload, "checked_item_count": 1.0},
            {**payload, "expected_token_counts": {"model": True}},
            {**payload, "binding": {**payload["binding"], "generation": True}},
        )
        for supplied in variants:
            with self.subTest(supplied=supplied):
                with self.assertRaises(TranslationIntegrityError) as context:
                    validator.validate_persisted(source, checked.items, supplied, binding=binding)
                self.assertEqual(context.exception.code, "translation_integrity_evidence_mismatch")

    def test_existing_dto_repr_hides_text_prompt_context_and_untrusted_id(self):
        prompt_marker = "隐私提示正文"
        source_marker = "隐私源正文"
        target_marker = "隐私译正文"
        id_marker = "恶意响应正文标记"
        markdown = "# " + prompt_marker
        prompt_hash = "sha256:" + hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        prompt = TranslationPromptSnapshot("prompt", "方案", markdown, prompt_hash, True)
        profile = TranslationProfileSnapshot("profile", "en2zh", "v1", "sha256:profile", "zh", "domain", "v1", None, 20, 8000, prompt)
        source = TranslationTextItem("a", source_marker)
        target = TranslationTextItem(id_marker, target_marker)
        request = TranslationProviderRequest("en2zh", "en", "zh", (source,), system_prompt_markdown=markdown)
        result = TranslationProviderResult((target,))
        for value in (source, target, request, result, prompt, profile, [source, target, request, result, profile]):
            for marker in (source_marker, target_marker, prompt_marker, id_marker):
                self.assertNotIn(marker, repr(value))
        self.assertEqual(asdict(source), {"id": "a", "text": source_marker})
        self.assertEqual(asdict(target)["id"], id_marker)
        self.assertEqual(asdict(request)["system_prompt_markdown"], markdown)
        self.assertEqual(asdict(profile)["prompt"]["markdown"], markdown)
        self.assertEqual(asdict(result)["items"][0]["text"], target_marker)
        self.assertEqual(profile.prompt.content_hash, prompt_hash)
        self.assertEqual(replace(profile), profile)
        for value, name in ((source, "text"), (prompt, "markdown"), (profile, "prompt")):
            with self.assertRaises(FrozenInstanceError):
                setattr(value, name, "改写")


class StrictTranslationProviderResponseTests(TestCase):
    def parse(self, text, *, finish_reason="stop"):
        return OpenAICompatibleTranslationProvider._parse_json_response(text, finish_reason=finish_reason, usage={"total_tokens": 17}, response_id="response")

    def test_strict_response_preserves_strings_and_whitespace_exactly(self):
        text = '{"items":[{"id":" item ","text":"  translated\\n"}]}'
        self.assertEqual(self.parse(text), (TranslationTextItem(" item ", "  translated\n"),))

    def test_strict_json_rejects_wrappers_duplicate_keys_extra_fields_and_coercion(self):
        good = '{"items":[{"id":"item","text":"译文"}]}'
        cases = (
            "```json\n" + good + "\n```", "prose " + good, good + " suffix", "[" + good + "]",
            '{"items":[],"extra":true}', '{"items":[],"items":[]}',
            '{"items":[{"id":"item","id":"item","text":"译文"}]}',
            '{"items":[{"id":"item","text":"译文","extra":null}]}',
            '{"items":[{"id":1,"text":"译文"}]}', '{"items":[{"id":"item","text":123}]}',
            '{"items":[{"id":"item","text":null}]}', '{"items":[{"id":"item","text":true}]}',
            '{"items":[{"id":"item","text":"  "}]}', '{"items":[{"id":"","text":"译文"}]}',
            '{"items":null}', '{"items":[null]}', '{"items":[{"id":"item","text":NaN}]}',
        )
        for content in cases:
            with self.subTest(content=content):
                with self.assertRaises(TranslationProviderResponseError) as context:
                    self.parse(content)
                self.assertFalse(context.exception.suspected_truncation)
                self.assertEqual(context.exception.usage, {"total_tokens": 17})
                self.assertEqual(context.exception.content_length, len(content))
                self.assertNotIn("译文", str(context.exception))

    def test_truncation_still_has_safe_diagnostics(self):
        content = '{"items":[{"id":"恶意正文标记","text":"敏感译文'
        with self.assertRaises(TranslationProviderResponseError) as context:
            self.parse(content, finish_reason="length")
        self.assertTrue(context.exception.suspected_truncation)
        self.assertEqual(context.exception.content_sha256, "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest())
        self.assertNotIn("恶意正文标记", repr(context.exception))
        self.assertNotIn("敏感译文", repr(context.exception))


class TranslationIntegrityAuditTests(TestCase):
    def make_recorder(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from app.core.config import Settings
        from app.domains.translation.audit import TranslationCallAuditRecorder
        from app.domains.document_jobs.models import DocumentJobRecord
        file_service = Mock()
        file_service.register_generated_content.side_effect = lambda **kwargs: SimpleNamespace(id=f"file_{file_service.register_generated_content.call_count}")
        job = DocumentJobRecord(id="job", tenant_id="tenant", company_id="company", created_by="user", source_file_id="source", template_version_id="template")
        recorder = TranslationCallAuditRecorder(
            settings=Settings(_env_file=None), file_service=file_service, job=job,
            term_version=None, trace_id="trace", save_full_text=False,
        )
        return recorder, file_service

    def test_success_and_integrity_failure_each_have_one_redacted_log(self):
        from unittest.mock import Mock
        markers = ("私密源正文", "私密译正文", "私密提示正文", "恶意返回ID正文")
        for failure in (False, True):
            with self.subTest(failure=failure):
                recorder, files = self.make_recorder()
                provider = Mock()
                document = translation_tests.DocumentIRTranslationTests()._make_document_ir()
                document.blocks = document.blocks[:1]
                document.blocks[0].text = markers[0] + " Typical OPA228"
                prompt = TranslationPromptSnapshot("prompt", "name", markers[2], "sha256:prompt", True)
                def respond(request):
                    return TranslationProviderResult(tuple(TranslationTextItem(
                        markers[3] if failure else item.id,
                        item.text.replace(markers[0], markers[1]),
                    ) for item in request.items))
                provider.translate.side_effect = respond
                service = DocumentIRTranslationService(provider)
                if failure:
                    with self.assertRaises(Exception) as context:
                        service.translate(document, term_version=None, prompt=prompt, call_recorder=recorder)
                    self.assertEqual(context.exception.code, "translation_integrity_item_missing")
                else:
                    service.translate(document, term_version=None, prompt=prompt, call_recorder=recorder)
                self.assertEqual(files.register_generated_content.call_count, 1)
                registration = files.register_generated_content.call_args.kwargs
                self.assertEqual(registration["file_type"], "ai_call_log")
                payload = json.loads(registration["content"])
                for marker in markers:
                    self.assertNotIn(marker, registration["content"].decode("utf-8"))
                self.assertNotIn("ledger", payload)
                self.assertEqual(payload["schema_version"], "ai-call-log/v1")
                self.assertEqual(payload["integrity"]["schema_version"], INTEGRITY_SCHEMA_VERSION)
                self.assertEqual(payload["integrity"]["status"], "failed" if failure else "passed")
                self.assertEqual(payload["status"], "failed" if failure else "succeeded")
                self.assertEqual(payload["error"]["code"] if failure else payload["error"], "translation_integrity_item_missing" if failure else None)

    def test_arbitrary_provider_exception_text_is_not_audited_or_rethrown(self):
        from unittest.mock import Mock
        recorder, files = self.make_recorder()
        provider = Mock()
        provider.translate.side_effect = RuntimeError("敏感外部异常全文")
        service = DocumentIRTranslationService(provider)
        with self.assertRaises(Exception) as context:
            service.translate(translation_tests.DocumentIRTranslationTests()._make_document_ir(), term_version=None, call_recorder=recorder)
        self.assertNotIn("敏感外部异常全文", str(context.exception))
        self.assertNotIn("敏感外部异常全文", repr(context.exception))
        self.assertEqual(context.exception.code, "translation_provider_failed")
        self.assertEqual(files.register_generated_content.call_count, 1)
        payload = json.loads(files.register_generated_content.call_args.kwargs["content"])
        self.assertNotIn("敏感外部异常全文", json.dumps(payload, ensure_ascii=False))
        self.assertEqual(payload["integrity"]["stage"], "provider")
        self.assertIsNone(payload["integrity"]["restored_sha256"])
        self.assertEqual(payload["error"]["code"], "translation_provider_failed")

    def test_invalid_dto_shape_does_not_break_safe_failure_audit(self):
        from unittest.mock import Mock
        recorder, files = self.make_recorder()
        provider = Mock()
        provider.translate.return_value = TranslationProviderResult((TranslationTextItem("恶意正文", 123),))
        with self.assertRaises(Exception) as context:
            DocumentIRTranslationService(provider).translate(translation_tests.DocumentIRTranslationTests()._make_document_ir(), term_version=None, call_recorder=recorder)
        self.assertEqual(context.exception.code, "translation_integrity_invalid_response")
        payload = json.loads(files.register_generated_content.call_args.kwargs["content"])
        self.assertEqual(payload["response"], {"invalid_shape": True})
        self.assertNotIn("恶意正文", json.dumps(payload, ensure_ascii=False))
