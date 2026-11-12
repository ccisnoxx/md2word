from __future__ import annotations

import hashlib
import io
import json
import posixpath
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path, PurePosixPath
from unittest.mock import patch
from zipfile import ZipFile

from docx import Document
from docx.document import Document as DocxDocument
from docx.enum.section import WD_SECTION_START
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from app.domains.document_jobs.http_responses import build_document_file_quality_evidence
from app.domains.files.models import DocumentFileRecord
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.ooxml_package import DocxPackageError, inspect_docx_package
from app.services.renderer.image_evidence import finish_image_report
from app.services.renderer.render_event_summary import build_renderer_event_summary
from app.services.renderer.render_evidence import build_renderer_evidence, validate_persisted_renderer_content
from app.services.renderer.render_evidence_validation import ensure_renderer_integrity
from app.services.renderer.template_conformance import build_template_conformance_report
from app.services.renderer.word_renderer import DocumentIRWordRenderer
from tests.test_template_package_contract import bundled_template_paths, mixed_section_document


def _rewrite(content: bytes, changes: dict[str, bytes | None]) -> bytes:
    """重写测试包成员，使错误只来自本用例变异。"""

    output = io.BytesIO()
    with ZipFile(io.BytesIO(content)) as source, ZipFile(output, "w") as package:
        for member in source.infolist():
            blob = changes[member.filename] if member.filename in changes else source.read(member)
            if blob is not None:
                package.writestr(member, blob)
        for name in changes.keys() - set(source.namelist()):
            if (blob := changes[name]) is not None:
                package.writestr(name, blob)
    return output.getvalue()


def _rel_part(name: str) -> str:
    part = PurePosixPath(name)
    return str(part.parent / "_rels" / f"{part.name}.rels")


def _member(content: bytes, name: str) -> bytes:
    with ZipFile(io.BytesIO(content)) as package:
        return package.read(name)


def _target(part: str, target: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(part), target)).lstrip("/")


def _decoration_part(content: bytes, relation_type: str) -> str:
    document = "word/document.xml"
    relationships = etree.fromstring(_member(content, _rel_part(document)))
    relationship = next(relation for relation in relationships if relation.get("Type") == relation_type)
    return _target(document, relationship.get("Target"))


def _header_media(content: bytes) -> tuple[str, str, str]:
    header = _decoration_part(content, RT.HEADER)
    relations = _rel_part(header)
    relationships = etree.fromstring(_member(content, relations))
    relationship = next(relation for relation in relationships if relation.get("Type") == RT.IMAGE)
    return header, relations, _target(header, relationship.get("Target"))


class TemplateConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template, cls.config = bundled_template_paths()
        cls.source = cls.template.read_bytes()
        cls.result = DocumentIRWordRenderer().render_to_result(
            mixed_section_document(), template_path=cls.template, config_path=cls.config, image_loader=lambda _: None,
        )

    def test_renderer_attaches_success_report_for_real_mixed_section_output(self) -> None:
        report = self.result.template_conformance
        self.assertEqual(report.schema_version, "template-conformance/v1")
        self.assertEqual(report.mode, "preserve_template")
        self.assertEqual(report.result_docx_sha256, hashlib.sha256(self.result.content).hexdigest())
        self.assertEqual(report.template_docx_sha256, hashlib.sha256(self.source).hexdigest())
        self.assertEqual(report.layout_config_sha256, hashlib.sha256(self.config.read_bytes()).hexdigest())
        self.assertIsNone(report.template_docx_hash_match)
        self.assertIsNone(report.layout_config_hash_match)
        self.assertEqual(report.blocking_flags, [])
        self.assertTrue(report.header_parts_preserved)
        self.assertTrue(report.footer_parts_preserved)
        self.assertTrue(report.header_media_preserved)
        self.assertTrue(report.section_settings_preserved)
        self.assertEqual(len(inspect_docx_package(self.result.content).sections), 5)

    def test_missing_media_relationship_and_bad_target_block(self) -> None:
        content = self.result.content
        _, relations, logo = _header_media(content)
        relationship_xml = etree.fromstring(_member(content, relations))
        image = next(rel for rel in relationship_xml if rel.get("Type") == RT.IMAGE)
        image.set("Target", "missing.png")
        for changes in ({logo: None}, {relations: None}, {relations: etree.tostring(relationship_xml)}):
            with self.subTest(changes=tuple(changes)):
                report = build_template_conformance_report(_rewrite(content, changes), template_content=self.source)
                self.assertIn("template_conformance:relationship_broken", report.blocking_flags)
                self.assertIn("template_conformance:header_media_missing", report.blocking_flags)
                self.assertEqual(report.broken_relationship_count, 1)
                self.assertEqual(report.missing_header_media_sha256, [hashlib.sha256(_member(content, logo)).hexdigest()])
                self.assertTrue(report.footer_parts_preserved)

    def test_replaced_logo_fails_even_when_part_and_relationship_still_exist(self) -> None:
        content = self.result.content
        _, _, logo = _header_media(content)
        changed = _rewrite(content, {logo: _member(content, logo) + b"different"})
        report = build_template_conformance_report(changed, template_content=self.source)
        self.assertTrue(report.header_parts_preserved)
        self.assertFalse(report.header_media_preserved)
        self.assertEqual(report.broken_relationship_count, 0)
        self.assertIn("template_conformance:header_media_missing", report.blocking_flags)

    def test_corrupt_raster_with_valid_relationship_is_rejected_in_both_modes(self) -> None:
        content = self.result.content
        _, _, logo = _header_media(content)
        # 保留 PNG 签名、MIME、关系及有效 ZIP CRC，只破坏图片本身。
        damaged = _rewrite(content, {logo: _member(content, logo)[:25]})
        for verify_all_parts in (False, True):
            with self.subTest(verify_all_parts=verify_all_parts):
                inspection = inspect_docx_package(damaged, verify_all_parts=verify_all_parts)
                self.assertEqual(
                    [(issue.code, issue.path) for issue in inspection.issues],
                    [("docx_media_invalid", "docx.header.media")],
                )
        report = build_template_conformance_report(damaged, template_content=damaged)
        self.assertIn("template_conformance:template_package_invalid", report.blocking_flags)
        self.assertIn("template_conformance:relationship_broken", report.blocking_flags)

    def test_embedded_word_vector_is_preserved_without_raster_validation(self) -> None:
        content = self.result.content
        header, relation_part, _ = _header_media(content)
        with ZipFile(io.BytesIO(content)) as package:
            vector = next(name for name in package.namelist() if name.endswith(".wmf"))
        relationships = etree.fromstring(_member(content, relation_part))
        next(rel for rel in relationships if rel.get("Type") == RT.IMAGE).set(
            "Target", posixpath.relpath(vector, posixpath.dirname(header)),
        )
        vector_docx = _rewrite(content, {relation_part: etree.tostring(relationships)})
        self.assertEqual(inspect_docx_package(vector_docx, verify_all_parts=True).issues, ())
        report = build_template_conformance_report(vector_docx, template_content=vector_docx)
        self.assertTrue(report.header_media_preserved)
        self.assertEqual(report.blocking_flags, [])

    def test_deleted_section_reference_fails_even_when_decoration_parts_remain(self) -> None:
        content = self.result.content
        part = "word/document.xml"
        for kind in ("header", "footer"):
            with self.subTest(kind=kind):
                root = etree.fromstring(_member(content, part))
                reference = next(root.iter(qn(f"w:{kind}Reference")))
                reference.getparent().remove(reference)
                report = build_template_conformance_report(
                    _rewrite(content, {part: etree.tostring(root)}), template_content=self.source,
                )
                self.assertIn(f"template_conformance:section_{kind}_reference_invalid", report.blocking_flags)
                self.assertIn(f"template_conformance:{kind}_part_missing", report.blocking_flags)

    def test_relative_targets_and_renumbered_rid_do_not_change_conformance(self) -> None:
        content = self.result.content
        header, old_rels, logo = _header_media(content)
        relocated_header = "word/decorations/top.xml"
        relation_xml = etree.fromstring(_member(content, old_rels))
        image = next(rel for rel in relation_xml if rel.get("Type") == RT.IMAGE)
        old_id = image.get("Id")
        image.set("Id", "rId42")
        image.set("Target", posixpath.relpath(logo, posixpath.dirname(relocated_header)))

        decoration = etree.fromstring(_member(content, header))
        for element in decoration.iter():
            if element.get(qn("r:embed")) == old_id:
                element.set(qn("r:embed"), "rId42")
        doc_rels = _rel_part("word/document.xml")
        document_relationships = etree.fromstring(_member(content, doc_rels))
        next(rel for rel in document_relationships if rel.get("Type") == RT.HEADER).set("Target", "decorations/top.xml")
        content_types = etree.fromstring(_member(content, "[Content_Types].xml"))
        next(item for item in content_types if item.get("PartName") == f"/{header}").set("PartName", f"/{relocated_header}")

        changed = _rewrite(content, {
            header: None,
            old_rels: None,
            relocated_header: etree.tostring(decoration),
            _rel_part(relocated_header): etree.tostring(relation_xml),
            doc_rels: etree.tostring(document_relationships),
            "[Content_Types].xml": etree.tostring(content_types),
        })
        self.assertFalse(inspect_docx_package(changed, verify_all_parts=True).issues)
        self.assertEqual(build_template_conformance_report(changed, template_content=self.source).blocking_flags, [])

    def test_package_traversal_and_unrelated_broken_relationship_are_distinguished(self) -> None:
        content = self.result.content
        _, header_rels, logo = _header_media(content)
        relationships = etree.fromstring(_member(content, header_rels))
        next(rel for rel in relationships if rel.get("Type") == RT.IMAGE).set("Target", f"../../{logo}")
        report = build_template_conformance_report(
            _rewrite(content, {header_rels: etree.tostring(relationships)}), template_content=self.source,
        )
        self.assertIn("template_conformance:relationship_broken", report.blocking_flags)

        name = "word/_rels/styles.xml.rels"
        extra = (
            b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            b'<Relationship Id="rId1" Type="urn:test:reference" Target="missing.xml"/>'
            b'</Relationships>'
        )
        unrelated = _rewrite(content, {name: extra})
        self.assertFalse(inspect_docx_package(unrelated).issues)
        issues = inspect_docx_package(unrelated, verify_all_parts=True).issues
        self.assertEqual([(issue.code, issue.path) for issue in issues], [
            ("docx_relationship_broken", "docx.relationships"),
        ])

    def test_missing_section_and_malformed_package_are_rejected(self) -> None:
        part = "word/document.xml"
        root = etree.fromstring(_member(self.result.content, part))
        section = root.find(qn("w:body")).find(qn("w:sectPr"))
        section.getparent().remove(section)
        invalid = _rewrite(self.result.content, {part: etree.tostring(root)})
        with self.assertRaises(DocxPackageError) as error:
            inspect_docx_package(invalid, verify_all_parts=True)
        self.assertEqual((error.exception.code, error.exception.path), ("docx_section_missing", "docx.sections"))
        report = build_template_conformance_report(b"not a ZIP", template_content=self.source)
        self.assertIn("template_conformance:output_package_invalid", report.blocking_flags)

    def test_header_override_may_change_header_but_must_keep_footer_and_valid_media(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, _, logo = _header_media(self.source)
            (root / "logo.png").write_bytes(_member(self.source, logo))
            config = root / "override.yaml"
            config.write_text(
                "schema_version: template-config/v1\nheader:\n  enabled: true\n  logo_path: logo.png\n  title_text: 覆盖页眉\n",
                encoding="utf-8",
            )
            result = DocumentIRWordRenderer().render_to_result(
                mixed_section_document(), template_path=self.template, config_path=config, image_loader=lambda _: None,
            )
        report = result.template_conformance
        self.assertEqual(report.mode, "override")
        self.assertIsNone(report.header_parts_preserved)
        self.assertTrue(report.footer_parts_preserved)
        self.assertEqual(report.blocking_flags, [])
        footer = _decoration_part(result.content, RT.FOOTER)
        _, _, actual_logo = _header_media(result.content)
        for missing, code in (
            (footer, "template_conformance:footer_part_missing"),
            (actual_logo, "template_conformance:relationship_broken"),
        ):
            with self.subTest(missing=missing):
                changed = _rewrite(result.content, {missing: None})
                mutated = build_template_conformance_report(changed, template_content=self.source, header_override=True)
                self.assertIn(code, mutated.blocking_flags)

    def test_final_source_section_preserves_inherited_default_first_and_even_references(self) -> None:
        source = Document()
        source.add_paragraph("模板正文")
        source.add_section(WD_SECTION_START.NEW_PAGE)
        source.add_paragraph("第二节正文")
        source.add_section(WD_SECTION_START.NEW_PAGE)
        first, middle, last = source.sections
        source.settings.odd_and_even_pages_header_footer = True
        last.different_first_page_header_footer = True
        first.header.paragraphs[0].text = "旧默认页眉"
        first.first_page_header.paragraphs[0].text = "首页页眉"
        first.even_page_header.paragraphs[0].text = "偶数页眉"
        first.footer.paragraphs[0].text = "默认页脚"
        first.first_page_footer.paragraphs[0].text = "首页页脚"
        first.even_page_footer.paragraphs[0].text = "偶数页脚"
        middle.header.is_linked_to_previous = False
        header = middle.header.paragraphs[0]
        header.text = "当前默认页眉"
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), header.part.relate_to("https://example.invalid/", RT.HYPERLINK, is_external=True))
        run = OxmlElement("w:r")
        run.append(OxmlElement("w:t"))
        hyperlink.append(run)
        header._p.append(hyperlink)
        self.assertTrue(last.header.is_linked_to_previous)

        with tempfile.TemporaryDirectory() as temp:
            template = Path(temp) / "custom.docx"
            source.save(template)
            result = DocumentIRWordRenderer().render_to_result(
                mixed_section_document(), template_path=template, config_path=None, image_loader=lambda _: None,
            )
        self.assertEqual(result.template_conformance.blocking_flags, [])
        output = Document(io.BytesIO(result.content))
        self.assertTrue(output.settings.odd_and_even_pages_header_footer)
        for section in output.sections:
            self.assertTrue(section.different_first_page_header_footer)
            for field, expected in (
                ("header", "当前默认页眉"), ("first_page_header", "首页页眉"), ("even_page_header", "偶数页眉"),
                ("footer", "默认页脚"), ("first_page_footer", "首页页脚"), ("even_page_footer", "偶数页脚"),
            ):
                self.assertEqual(getattr(section, field).paragraphs[0].text, expected)
        self.assertEqual(output.sections[0].header.paragraphs[0].hyperlinks[0].address, "https://example.invalid/")

    def test_no_template_mode_allows_valid_plain_package(self) -> None:
        result = DocumentIRWordRenderer().render_to_result(
            mixed_section_document(), template_path=None, config_path=None, image_loader=lambda _: None,
        )
        report = result.template_conformance
        self.assertEqual(report.mode, "no_template")
        self.assertIsNone(report.expected_decoration)
        self.assertIsNone(report.header_parts_preserved)
        self.assertIsNone(report.footer_parts_preserved)
        self.assertEqual(report.blocking_flags, [])

    def test_damaged_saved_output_blocks_formal_renderer_quality_gate(self) -> None:
        document_ir = mixed_section_document()
        save = DocxDocument.save

        def save_without_logo(document, target):
            buffer = io.BytesIO()
            save(document, buffer)
            content = buffer.getvalue()
            _, _, logo = _header_media(content)
            target.write(_rewrite(content, {logo: None}))

        with patch.object(DocxDocument, "save", save_without_logo):
            result = DocumentIRWordRenderer().render_to_result(
                document_ir, template_path=self.template, config_path=self.config, image_loader=lambda _: None,
            )
        evidence = build_renderer_evidence(document_ir, result.content, render_result=result)
        self.assertIn("template_conformance:header_media_missing", evidence["blocking_quality_flags"])
        with self.assertRaises(DocumentIntegrityError) as error:
            ensure_renderer_integrity(evidence)
        summary = error.exception.evidence["template_conformance"]
        self.assertEqual(summary["status"], "blocked")
        self.assertIn("template_conformance:header_media_missing", summary["blocking_flags"])
        self.assertNotIn("missing_header_media_sha256", summary)

    def test_persisted_evidence_rechecks_report_and_accepts_old_evidence_without_it(self) -> None:
        document_ir = mixed_section_document()
        original = build_renderer_evidence(document_ir, self.result.content, render_result=self.result)
        persisted = json.loads(json.dumps(original))
        verified = validate_persisted_renderer_content(document_ir, self.result.content, persisted)
        self.assertEqual(verified["template_conformance"], original["template_conformance"])
        ensure_renderer_integrity(verified)

        del persisted["template_conformance"]
        verified = validate_persisted_renderer_content(document_ir, self.result.content, persisted)
        self.assertNotIn("template_conformance", verified)

    def test_missing_same_run_report_cannot_fall_back_to_legacy(self) -> None:
        result = replace(self.result, template_conformance=None)
        with self.assertRaises(DocumentIntegrityError) as error:
            build_renderer_evidence(mixed_section_document(), result.content, render_result=result)
        self.assertEqual(error.exception.evidence["blocking_quality_flags"], ["template_conformance:report_invalid"])

    def test_persisted_output_and_resource_identities_and_recomputed_flags_are_required(self) -> None:
        document_ir = mixed_section_document()
        original = build_renderer_evidence(document_ir, self.result.content, render_result=self.result)
        for field, changed in (
            ("result_docx_sha256", "0" * 64), ("template_docx_sha256", "0" * 64),
            ("layout_config_sha256", "0" * 64), ("header_media_preserved", False),
            ("blocking_flags", ["template_conformance:header_media_missing"]),
        ):
            with self.subTest(field=field):
                persisted = json.loads(json.dumps(original))
                persisted["template_conformance"][field] = changed
                with self.assertRaises(DocumentIntegrityError) as error:
                    validate_persisted_renderer_content(document_ir, self.result.content, persisted)
                self.assertEqual(error.exception.evidence["blocking_quality_flags"], ["template_conformance:binding_mismatch"])

        # 篡改者即使重新计算图片报告的输入哈希，仍无法通过真实 RenderPlan 的资源对账。
        persisted = json.loads(json.dumps(original))
        persisted["template_conformance"]["template_docx_sha256"] = "0" * 64
        image_report = persisted["image_layout_report"]
        image_report["render_inputs"]["template"]["docx"]["sha256"] = "0" * 64
        finish_image_report(image_report)
        with self.assertRaises(DocumentIntegrityError) as error:
            validate_persisted_renderer_content(document_ir, self.result.content, persisted)
        self.assertEqual(error.exception.evidence["blocking_quality_flags"], ["template_conformance:binding_mismatch"])

    def test_unknown_report_version_and_explicit_false_yaml_hash_block_safely(self) -> None:
        document_ir = mixed_section_document()
        evidence = build_renderer_evidence(document_ir, self.result.content, render_result=self.result)
        for field, changed, flag in (
            ("schema_version", "/private/template/version", "template_conformance:report_invalid"),
            ("layout_config_hash_match", False, "template_conformance:layout_config_hash_mismatch"),
        ):
            with self.subTest(field=field):
                persisted = json.loads(json.dumps(evidence))
                persisted["template_conformance"][field] = changed
                # 嵌套报告必须独立阻断，即使顶层列表没有同步记录错误码。
                for check in (lambda: ensure_renderer_integrity(persisted),
                              lambda: validate_persisted_renderer_content(document_ir, self.result.content, persisted)):
                    with self.assertRaises(DocumentIntegrityError) as error:
                        check()
                    self.assertEqual(error.exception.evidence["blocking_quality_flags"], [flag])
                    self.assertNotIn("/private/template/version", str(error.exception))

    def test_event_and_management_projections_strip_private_report_fields_idempotently(self) -> None:
        document_ir = mixed_section_document()
        metadata = build_renderer_evidence(document_ir, self.result.content, render_result=self.result)
        summary = build_renderer_event_summary(metadata)
        conformance = summary["template_conformance"]
        self.assertEqual(conformance["status"], "passed")
        self.assertEqual(build_renderer_event_summary(summary)["template_conformance"], conformance)
        self.assertTrue(conformance["header_media_preserved"])
        for private_key in ("expected_decoration", "result_docx_sha256", "template_docx_sha256", "layout_config_sha256"):
            self.assertNotIn(private_key, conformance)
        self.assertNotIn(metadata["template_conformance"]["template_docx_sha256"], json.dumps(summary))

        file = DocumentFileRecord(
            id="file_quality", tenant_id="tenant", company_id="company", file_type="generated_word",
            storage_provider="local_file", bucket="files", object_key="generated/result.docx",
            original_filename="result.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=len(self.result.content), metadata=metadata,
        )
        self.assertEqual(build_document_file_quality_evidence(file)["template_conformance"], conformance)
        metadata["template_conformance"]["blocking_flags"] = ["/private/raw/path"]
        safe = build_renderer_event_summary(metadata)["template_conformance"]
        self.assertEqual(safe["status"], "blocked")
        self.assertEqual(safe["blocking_flags"], ["template_conformance:report_invalid"])
        self.assertNotIn("/private/raw/path", json.dumps(safe))
