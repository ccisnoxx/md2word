from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from zipfile import ZipFile

from app.domains.translation.models import TranslationTextItem
from app.domains.translation.protected_tokens import (
    EncodedTokenBatch,
    ProtectedTokenError,
    ProtectedTokenKind as Kind,
    decode,
    encode,
)


class FakeEncodedProvider:
    """仅在测试内改变自然语言或损坏 Token，不接入正式翻译服务。"""

    def translate(self, items: tuple[TranslationTextItem, ...], *, corrupt: bool = False) -> tuple[TranslationTextItem, ...]:
        return tuple(
            TranslationTextItem(
                id=item.id,
                text=item.text.replace("Typical", "典型值").replace("High", "高")
                + (" {{MD2W_PT_v1_999_1}}" if corrupt else ""),
            )
            for item in items
        )


class ProtectedTokenCodecTests(unittest.TestCase):
    def assert_roundtrip(self, items: tuple[TranslationTextItem, ...]) -> EncodedTokenBatch:
        batch = encode(items)
        restored = decode(batch.items, batch)
        self.assertEqual(restored, items)
        self.assertEqual([item.text.encode("utf-8") for item in restored], [item.text.encode("utf-8") for item in items])
        return batch

    def assert_error(self, code: str, items: tuple[TranslationTextItem, ...], batch: EncodedTokenBatch) -> None:
        with self.assertRaises(ProtectedTokenError) as context:
            decode(items, batch)
        self.assertEqual(context.exception.code, code)

    def test_roundtrip_preserves_existing_placeholder_literals(self) -> None:
        items = (TranslationTextItem(id="i", text="literal {{PH_001}} OPA228 25°C"),)

        batch = encode(items)

        self.assertNotEqual(batch.items, items)
        self.assertEqual(decode(batch.items, batch), items)

    def test_category_vectors_are_exact_original_spans(self) -> None:
        vectors = (
            ("25°C", Kind.QUANTITY), ("−40–+85 °C", Kind.QUANTITY),
            ("±0.5%", Kind.QUANTITY), ("1.2e−3 A", Kind.QUANTITY),
            ("3 nV/sqrt(Hz)", Kind.QUANTITY), ("10 V/us", Kind.QUANTITY),
            ("4 μA", Kind.QUANTITY), ("5 µA", Kind.QUANTITY), ("6 мкА", Kind.QUANTITY),
            ("0x0028", Kind.ADDRESS), ("0x0028[4:0]", Kind.ADDRESS),
            ("[4:0]", Kind.BIT_FIELD), ("DATA[4:0]", Kind.BIT_FIELD),
            ("VCC1_VCO", Kind.SIGNAL), ("V_OUT", Kind.SIGNAL), ("RESET_N", Kind.SIGNAL),
            ("OPA228", Kind.MODEL), ("ZK7044", Kind.MODEL),
            ("SOIC-8", Kind.MODEL), ("QFN-32", Kind.MODEL),
            ("IEEE 802.3", Kind.STANDARD), ("v1.2.3", Kind.VERSION),
            ("v1.2", Kind.VERSION), ("1.2.3", Kind.VERSION),
            ("TA = 25°C", Kind.FORMULA), ("E=mc^2", Kind.FORMULA),
            ("V=IR", Kind.FORMULA), ("V_OUT = V_IN + 0.5 V", Kind.FORMULA),
            ("$V=IR$", Kind.FORMULA), ("$$E=mc^2$$", Kind.FORMULA),
            (r"\(V=IR\)", Kind.FORMULA), (r"\[V=IR\]", Kind.FORMULA),
            ("https://example.test/a?x=1", Kind.URL), ("tech@example.test", Kind.EMAIL),
            ("≤ 1.5e-3", Kind.NUMBER), ("2–4", Kind.NUMBER), ("3 to 5", Kind.NUMBER),
            ("-2.5", Kind.NUMBER), ("1 ± 0.2", Kind.NUMBER),
            ("≤", Kind.SYMBOL),
            ("ADC", Kind.TECHNICAL_LITERAL), ("I2C", Kind.TECHNICAL_LITERAL),
            ("USB", Kind.TECHNICAL_LITERAL), ("JEDEC", Kind.TECHNICAL_LITERAL),
        )
        for source, kind in vectors:
            with self.subTest(source=source):
                suffix = "V_OUT" if kind == Kind.SYMBOL else "; High"
                items = (TranslationTextItem(id="vector", text=f"Typical {source}{suffix}"),)
                batch = self.assert_roundtrip(items)
                expected = [(source, kind)] + ([("V_OUT", Kind.SIGNAL)] if kind == Kind.SYMBOL else [])
                self.assertEqual([(occ.original_text, occ.kind) for occ in batch.occurrences], expected)
                occurrence = batch.occurrences[0]
                self.assertEqual(items[0].text[occurrence.start:occurrence.end], source)
                if kind != Kind.SYMBOL:
                    self.assertEqual(batch.items[0].text, f"Typical {occurrence.placeholder}; High")

    def test_standalone_units_preserve_surrounding_whitespace(self) -> None:
        for unit in ("V", "A", "Hz", "Ω", "F", "s", "°C", "%", "µV", "μV", "мкА", "V/√Hz", "m/s²"):
            with self.subTest(unit=unit):
                batch = self.assert_roundtrip((TranslationTextItem(id="u", text=f"\r\n {unit}\t "),))
                self.assertEqual([(occ.original_text, occ.kind) for occ in batch.occurrences], [(unit, Kind.UNIT)])

    def test_natural_language_and_non_unit_single_letters_remain_translatable(self) -> None:
        for source in (
            "Typical Reserved High Low Input voltage NOTE UNKNOWN",
            "中文参数名称 典型值", "Обычное входное напряжение Примечание",
            "a in at", "A normal sentence in a note at noon", "PH {{NAME}} {{PHONE}}",
            "V A Hz s are symbols in prose", "$unfinished natural language", r"\(unfinished ordinary words",
        ):
            with self.subTest(source=source):
                items = (TranslationTextItem(id="natural", text=source),)
                batch = self.assert_roundtrip(items)
                self.assertEqual(batch.items, items)
                self.assertEqual(batch.occurrences, ())

    def test_unselected_characters_are_kept_in_their_exact_order(self) -> None:
        source = "输入 Typical\t25°C\r\nReserved\u00a0OPA228 High\u0301: 0x0028[4:0], Low"
        batch = self.assert_roundtrip((TranslationTextItem(id="i", text=source),))
        unselected_source: list[str] = []
        cursor = 0
        for occurrence in batch.occurrences:
            self.assertGreaterEqual(occurrence.start, cursor)
            unselected_source.append(source[cursor:occurrence.start])
            cursor = occurrence.end
        unselected_source.append(source[cursor:])
        unselected_encoded = batch.items[0].text
        for occurrence in batch.occurrences:
            unselected_encoded = unselected_encoded.replace(occurrence.placeholder, "")
        self.assertEqual(unselected_encoded, "".join(unselected_source))

    def test_overlap_selection_is_deterministic_and_non_overlapping(self) -> None:
        items = (TranslationTextItem(id="overlap", text="TA = 25°C; 0x0028[4:0] OPA228 VCC1_VCO 3 nV/sqrt(Hz)"),)
        batch = self.assert_roundtrip(items)
        self.assertEqual([occ.original_text for occ in batch.occurrences], ["TA = 25°C", "0x0028[4:0]", "OPA228", "VCC1_VCO", "3 nV/sqrt(Hz)"])
        self.assertEqual(batch, encode(items))
        self.assertTrue(all(left.end <= right.start for left, right in zip(batch.occurrences, batch.occurrences[1:])))

    def test_url_and_formula_own_embedded_reserved_literals(self) -> None:
        items = (
            TranslationTextItem(id="url", text="https://example.test/{{PH_001}}?x=1, end"),
            TranslationTextItem(id="formula", text="$V={{MD2W_PT_v1_0_1}}$"),
        )
        batch = self.assert_roundtrip(items)
        self.assertEqual([occ.kind for occ in batch.occurrences], [Kind.URL, Kind.FORMULA])
        self.assertEqual(batch.occurrences[0].original_text, "https://example.test/{{PH_001}}?x=1")
        self.assertEqual(batch.items[0].text, f"{batch.occurrences[0].placeholder}, end")

    def test_partial_reserved_prefix_is_not_left_bare_by_higher_priority_structures(self) -> None:
        for prefix in ("{{PH_", "{{MD2W_PT_v1_0_"):
            for suffix in ("https://example.test/a", "TA = 25°C", "$V=IR$"):
                with self.subTest(prefix=prefix, suffix=suffix):
                    source = prefix + " " + suffix
                    batch = self.assert_roundtrip((TranslationTextItem(id="partial", text=source),))
                    self.assertEqual(batch.occurrences[-1].original_text, suffix)
                    self.assertEqual(batch.occurrences[0].kind, Kind.LITERAL_PLACEHOLDER)

    def test_valid_tokens_and_urls_do_not_consume_surrounding_punctuation(self) -> None:
        items = tuple(
            TranslationTextItem(id=str(index), text=source)
            for index, source in enumerate((
                "(25°C)", "[OPA228]", "{3 nV/sqrt(Hz)}", "25°C\t High",
                "https://example.test/{{PH_001}}", "(https://example.test/a(b)).",
                "{{MD2W_PT_v1_0_1}}) suffix", "{{PH_001}}) suffix",
            ))
        )
        batch = self.assert_roundtrip(items)
        self.assertIn("https://example.test/{{PH_001}}", [occ.original_text for occ in batch.occurrences])
        self.assertIn("https://example.test/a(b)", [occ.original_text for occ in batch.occurrences])

    def test_namespace_scans_all_items_and_restoration_is_not_recursive(self) -> None:
        items = (
            TranslationTextItem(id="first", text="OPA228 {{PH_001}}"),
            TranslationTextItem(id="later", text="{{MD2W_PT_v1_0_1}} {{MD2W_PT_v1_1_ {{MD2W_PT_v1_2_9}}"),
        )
        batch = self.assert_roundtrip(items)
        self.assertEqual(batch.namespace, "{{MD2W_PT_v1_3_")
        self.assertEqual([occ.original_text for occ in batch.occurrences], ["OPA228", "{{PH_001}}", "{{MD2W_PT_v1_0_1}}", "{{MD2W_PT_v1_1_", "{{MD2W_PT_v1_2_9}}"])

    def test_reserved_literal_scanner_is_shared_for_partial_and_modified_sources(self) -> None:
        for literal in (
            "{{PH_001}}", "{{PH_", "{{ph_001}}", "{{ PH _ 001 }}",
            "{{MD2W_PT_v1_0_1}}", "{{MD2W_PT_v1_0_", "{{md2w_pt_v1_0_1}}",
            "{{ MD2W_PT_v1_0_1 }}", "{{M D 2 W _ P T_v1_0_1}}",
            "[[MD2W_PT_v1_0_1]]", "(MD2W_PT_v1_0_1)",
            "{{MD2W_PT_v1_0_\u200b1}}", "{{MD2W_PT_v1_0_1}",
        ):
            with self.subTest(literal=literal):
                batch = self.assert_roundtrip((TranslationTextItem(id="literal", text=literal),))
                self.assertEqual([occ.original_text for occ in batch.occurrences], [literal])
                self.assertEqual(batch.occurrences[0].kind, Kind.LITERAL_PLACEHOLDER)

    def test_each_occurrence_is_unique_across_items_and_beyond_999(self) -> None:
        items = (
            TranslationTextItem(id="large", text=" ".join(["25°C"] * 1005)),
            TranslationTextItem(id="again", text="25°C 25°C"),
        )
        batch = self.assert_roundtrip(items)
        placeholders = [occ.placeholder for occ in batch.occurrences]
        self.assertEqual(len(placeholders), 1007)
        self.assertEqual(len(set(placeholders)), 1007)
        self.assertEqual(placeholders[999], "{{MD2W_PT_v1_0_1000}}")
        self.assertEqual([occ.original_text for occ in batch.occurrences], ["25°C"] * 1007)

    def test_empty_and_unicode_roundtrips_are_byte_exact(self) -> None:
        vectors = (
            (), (TranslationTextItem(id="empty", text=""),),
            (TranslationTextItem(id="whitespace", text=" \t\r\n\u00a0"),),
            (TranslationTextItem(id="unicode", text="e\u0301 é\r\nµ μ 1 µA\u00a0−40–+85 °C\n2 μA 中文 Русский"),),
        )
        for items in vectors:
            with self.subTest(items=items):
                self.assert_roundtrip(items)

    def test_input_and_ledger_are_immutable_and_sensitive_repr_is_hidden(self) -> None:
        items = (TranslationTextItem(id="private", text="机密文本 PRIVATE_CONTENT OPA228"),)
        batch = self.assert_roundtrip(items)
        self.assertNotIn("PRIVATE_CONTENT", repr(batch))
        self.assertNotIn("OPA228", repr(batch.occurrences[0]))
        with self.assertRaises(FrozenInstanceError):
            setattr(batch, "namespace", "other")
        with self.assertRaises(FrozenInstanceError):
            setattr(batch.occurrences[0], "original_text", "changed")
        with self.assertRaises(FrozenInstanceError):
            setattr(batch.items[0], "text", "changed")
        self.assertEqual(items[0].text, "机密文本 PRIVATE_CONTENT OPA228")

    def test_interleaved_calls_have_no_shared_state(self) -> None:
        first = (TranslationTextItem(id="first", text="OPA228 25°C"),)
        second = (TranslationTextItem(id="second", text="{{MD2W_PT_v1_0_1}} 10 V/us"),)
        batch_first = encode(first)
        batch_second = encode(second)
        self.assertEqual(batch_first, encode(first))
        self.assertEqual(batch_second, encode(second))
        self.assertEqual(decode(batch_first.items, batch_first), first)
        self.assertEqual(decode(batch_second.items, batch_second), second)

    def test_missing_duplicate_unknown_and_wrong_item_are_rejected(self) -> None:
        batch = encode((TranslationTextItem(id="a", text="OPA228"), TranslationTextItem(id="b", text="25°C")))
        first, second = [occ.placeholder for occ in batch.occurrences]
        vectors = (
            ("protected_token_missing", "", second),
            ("protected_token_duplicate", first + first, second),
            ("protected_token_unknown", first + "{{MD2W_PT_v1_0_99}}", second),
            ("protected_token_wrong_item", second, first),
            ("protected_token_wrong_item", first + second, ""),
            ("protected_token_unknown", first.replace("v1_0_", "v1_99_"), second),
        )
        for code, text_a, text_b in vectors:
            with self.subTest(code=code, text_a=text_a):
                self.assert_error(code, (TranslationTextItem(id="a", text=text_a), TranslationTextItem(id="b", text=text_b)), batch)

    def test_token_tampering_is_never_repaired(self) -> None:
        batch = encode((TranslationTextItem(id="i", text="OPA228"),))
        token = batch.occurrences[0].placeholder
        for tampered in (
            token.lower(), token.replace("_1}}", "_01}}"), token.replace("_1}}", "_2}}"),
            token.replace("MD2W", "MD 2W"), token.replace("_1}}", "_ 1}}"),
            token.replace("_1}}", "_\u200b1}}"), token.replace("{{", "[[").replace("}}", "]]"),
            token[:-1], token[1:], token.replace("MD2W_PT", "MD2W_PX"),
        ):
            with self.subTest(tampered=tampered):
                with self.assertRaises(ProtectedTokenError):
                    decode((TranslationTextItem(id="i", text=tampered),), batch)

    def test_no_token_batch_also_rejects_injected_reserved_syntax(self) -> None:
        batch = encode((TranslationTextItem(id="i", text="ordinary text"),))
        for literal in ("{{MD2W_PT_v1_0_1}}", "{{PH_001}}", "{{md2w_pt_v1_0_1}}", "{{MD2W_PT_v1_0_"):
            with self.subTest(literal=literal):
                with self.assertRaises(ProtectedTokenError):
                    decode((TranslationTextItem(id="i", text="ordinary " + literal),), batch)

    def test_return_item_ids_must_match_the_complete_ordered_envelope(self) -> None:
        batch = encode((TranslationTextItem(id="a", text="OPA228"), TranslationTextItem(id="b", text="25°C")))
        a, b = batch.items
        for items in ((a,), (a, b, TranslationTextItem(id="extra", text="")), (a, a), (b, a), ()):
            with self.subTest(ids=tuple(item.id for item in items)):
                self.assert_error("protected_token_item_mismatch", items, batch)

    def test_invalid_input_is_explicit_without_echoing_content(self) -> None:
        for items in (
            [TranslationTextItem(id="i", text="OPA228")],
            (TranslationTextItem(id="", text="OPA228"),),
            (TranslationTextItem(id=" \t", text="OPA228"),),
            (TranslationTextItem(id="i", text="OPA228"), TranslationTextItem(id="i", text="25°C")),
            (TranslationTextItem(id="i", text=None),), (object(),),
        ):
            with self.subTest(items=items):
                with self.assertRaises(ProtectedTokenError) as context:
                    encode(items)
                self.assertEqual(context.exception.code, "protected_token_invalid_input")
                self.assertNotIn("OPA228", str(context.exception))

    def test_entire_batch_is_validated_before_any_restoration(self) -> None:
        original = (TranslationTextItem(id="a", text="PRIVATE_SOURCE OPA228"), TranslationTextItem(id="b", text="PRIVATE_SECOND 25°C"))
        batch = encode(original)
        returned = (batch.items[0], TranslationTextItem(id="b", text="PRIVATE_RETURN"))
        with patch.object(TranslationTextItem, "__init__", side_effect=AssertionError("整批验证前不得构造还原项")) as constructor:
            with self.assertRaises(ProtectedTokenError) as context:
                decode(returned, batch)
            constructor.assert_not_called()
        self.assertEqual(context.exception.code, "protected_token_missing")
        for sensitive in ("PRIVATE_SOURCE", "PRIVATE_SECOND", "PRIVATE_RETURN", "OPA228", "25°C"):
            self.assertNotIn(sensitive, str(context.exception))
            self.assertNotIn(sensitive, repr(context.exception))
        self.assertEqual(decode(batch.items, batch), original)
        self.assertEqual(batch, encode(original))

    def test_error_priority_is_envelope_then_reserved_syntax_then_missing_then_duplicate(self) -> None:
        batch = encode((TranslationTextItem(id="a", text="OPA228"), TranslationTextItem(id="b", text="25°C")))
        first, second = [occ.placeholder for occ in batch.occurrences]
        self.assert_error("protected_token_item_mismatch", (TranslationTextItem(id="wrong", text="{{PH_001}}"),), batch)
        self.assert_error("protected_token_malformed", (TranslationTextItem(id="a", text=""), TranslationTextItem(id="b", text="{{PH_001}}")), batch)
        self.assert_error("protected_token_missing", (TranslationTextItem(id="a", text=first * 2), TranslationTextItem(id="b", text="")), batch)
        self.assert_error("protected_token_duplicate", (TranslationTextItem(id="a", text=first * 2), TranslationTextItem(id="b", text=second)), batch)

    def test_fake_provider_changes_only_natural_language_and_can_move_whole_tokens(self) -> None:
        batch = encode((TranslationTextItem(id="i", text="Typical OPA228 High 25°C"),))
        provider = FakeEncodedProvider()
        with patch("socket.socket", side_effect=AssertionError("离线测试禁止网络")):
            translated = decode(provider.translate(batch.items), batch)
            self.assertEqual(translated[0].text, "典型值 OPA228 高 25°C")
            with self.assertRaises(ProtectedTokenError):
                decode(provider.translate(batch.items, corrupt=True), batch)
        first, second = [occ.placeholder for occ in batch.occurrences]
        reordered = decode((TranslationTextItem(id="i", text=f"高 {second}，型号 {first}"),), batch)
        self.assertEqual(reordered[0].text, "高 25°C，型号 OPA228")

    def test_opa228_fixture_uses_real_converter_and_extractor_without_translation(self) -> None:
        from app.domains.translation.document_ir_translator import DocumentIRTranslationService
        from app.services.document_ir.mineru_converter import MinerUToDocumentIRService

        fixture = Path(__file__).parent / "fixtures/component_pdf_samples/samples/texas-instruments/op-amp/ti-opamp-opa228-p1-smoke/mineru/component_content_list_v2.json"
        provider = Mock()
        provider.translate.side_effect = AssertionError("Codec 样本不得调用正式翻译")
        with TemporaryDirectory(prefix="protected_token_fixture_") as temp_dir:
            zip_path = Path(temp_dir) / "mineru.zip"
            with ZipFile(zip_path, "w") as archive:
                archive.write(fixture, "component_content_list_v2.json")
            document = MinerUToDocumentIRService().convert_zip(
                zip_path, job_id="codec_fixture", source_file_id="public_fixture", document_language="en"
            ).document
            before = document.model_dump(mode="json")
            _targets, items = DocumentIRTranslationService(provider).extract_translation_items(document)
            batch = self.assert_roundtrip(tuple(items))
            self.assertEqual(document.model_dump(mode="json"), before)
        provider.translate.assert_not_called()
        originals = [occ.original_text for occ in batch.occurrences]
        for expected in ("OPA228", "3 nV/sqrt(Hz)", "10 V/us"):
            self.assertIn(expected, originals)


if __name__ == "__main__":
    unittest.main()
