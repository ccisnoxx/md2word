"""模板包预检对照真实默认文件及损坏输入。"""

from __future__ import annotations

import io
import json
import posixpath
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from xml.etree import ElementTree
from zipfile import ZipFile

import yaml

from app.domains.resources.integrity import content_sha256
from app.domains.templates.manifest import resolve_bundled_template_seed
from app.domains.templates.package_validator import (
    TemplatePackageValidationError,
    validate_template_package,
    validate_template_package_content,
)


class TemplatePackageValidationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed = resolve_bundled_template_seed(Path(__file__).resolve().parents[1])
        cls.template_path = seed.template_path
        cls.layout_path = seed.layout_config_path
        cls.template_content = cls.template_path.read_bytes()

    def _validate(self, patch: dict, *, template_content: bytes | None = None) -> None:
        raw = {"schema_version": "template-config/v1", **patch}
        validate_template_package_content(
            template_content=self.template_content if template_content is None else template_content,
            layout_config_content=yaml.safe_dump(raw).encode("utf-8"),
        )

    def test_real_default_resources_pass_and_fingerprint_matches_actual_bytes(self) -> None:
        fingerprint = validate_template_package(template_path=self.template_path, layout_config_path=self.layout_path)
        self.assertEqual(fingerprint.docx_sha256, content_sha256(self.template_content))
        self.assertEqual(fingerprint.layout_config_sha256, content_sha256(self.layout_path.read_bytes()))

    def test_invalid_docx_and_missing_required_parts_fail(self) -> None:
        cases = (
            (b"", "docx_package_invalid"),
            (b"Invalid Word document", "docx_package_invalid"),
            (self._change_zip({"[Content_Types].xml": None}), "docx_content_types_invalid"),
            (self._change_zip({"word/document.xml": None}), "docx_main_document_invalid"),
            (self._change_zip({"word/styles.xml": b"<invalid"}), "docx_part_invalid"),
        )
        for content, code in cases:
            with self.subTest(code=code), self.assertRaises(TemplatePackageValidationError) as caught:
                self._validate({}, template_content=content)
            self.assertEqual(caught.exception.code, code)

    def test_missing_header_media_fails(self) -> None:
        with ZipFile(io.BytesIO(self.template_content)) as archive:
            header_relationship = next(name for name in archive.namelist() if "header" in name and name.endswith(".rels"))
            relations = ElementTree.fromstring(archive.read(header_relationship))
            logo = next(rel.attrib["Target"] for rel in relations if rel.attrib["Type"].endswith("/image"))
            media_name = posixpath.normpath(posixpath.join(posixpath.dirname(posixpath.dirname(header_relationship)), logo))
        with self.assertRaises(TemplatePackageValidationError) as caught:
            self._validate({}, template_content=self._change_zip({media_name: None}))
        self.assertEqual(caught.exception.code, "docx_relationship_broken")
        self.assertEqual(caught.exception.path, "docx.header.relationships")

    def test_layout_ranges_style_types_and_unknown_fields(self) -> None:
        cases = (
            ({"schema_version": "other"}, "schema_version", "unsupported_schema_version"),
            ({"normal": {"unknown": 1}}, "normal", "schema_validation_failed"),
            ({"table_style": {"style_name": "Normal"}}, "table_style.style_name", "unknown_word_style"),
            ({"normal": {"word_style_name": "Table Grid"}}, "normal.word_style_name", "unknown_word_style"),
            ({"normal": {"word_style_name": "不存在的样式"}}, "normal.word_style_name", "unknown_word_style"),
            ({"page_setup": {"page_width_cm": 0}}, "page_setup.page_width_cm", "below_minimum"),
            ({"page_setup": {"left_margin": -1}}, "page_setup.left_margin", "below_minimum"),
            ({"page_setup": {"page_width_cm": 1}}, "page_setup", "invalid_page_body"),
            ({"normal": {"font_size": 0}}, "normal.font_size", "below_minimum"),
            ({"part_number": {"line_spacing": 0}}, "part_number.line_spacing", "below_minimum"),
            ({"normal": {"color": "bad"}}, "normal.color", "invalid_color"),
            (
                {"language_overrides": {"en": {"normal": {"word_style_name": "Table Grid"}}}},
                "language_overrides.normal.word_style_name", "unknown_word_style",
            ),
            (
                {"language_overrides": {"en": {"header": {"logo_path": "../secret.png"}}}},
                "language_overrides.header.logo_path", "invalid_relative_path",
            ),
            (
                {"language_overrides": {"en": {"page_setup": {"right_margin": -1}}}},
                "language_overrides.page_setup.right_margin", "below_minimum",
            ),
        )
        for patch, path, code in cases:
            with self.subTest(path=path, code=code):
                with self.assertRaises(TemplatePackageValidationError) as caught:
                    self._validate(patch)
                self.assertEqual((caught.exception.path, caught.exception.code), (path, code))

    def test_sparse_layout_uses_real_word_styles_and_optional_override_image(self) -> None:
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "layout.yaml"
            config_path.write_text(
                "schema_version: template-config/v1\n"
                "normal: {word_style_name: Normal}\n"
                "header: {enabled: true, title_text: 示例, logo_path: optional.png}\n",
                encoding="utf-8",
            )
            validate_template_package(template_path=self.template_path, layout_config_path=config_path)

            logo = config_path.with_name("optional.png")
            logo.write_bytes(b"not an image")
            with self.assertRaises(TemplatePackageValidationError) as caught:
                validate_template_package(template_path=self.template_path, layout_config_path=config_path)
            self.assertEqual(caught.exception.code, "invalid_override_logo")
            self.assertNotIn(directory, str(caught.exception))

            logo.unlink()
            logo.symlink_to(self.template_path)
            with self.assertRaises(TemplatePackageValidationError) as caught:
                validate_template_package(template_path=self.template_path, layout_config_path=config_path)
            self.assertEqual(caught.exception.code, "invalid_relative_path")
            self.assertNotIn(str(self.template_path), str(caught.exception))

    def test_error_omits_filesystem_paths_and_untrusted_yaml_keys(self) -> None:
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "private-layout.yaml"
            for text in (
                "schema_version: template-config/v1\n" + json.dumps(directory) + ": true",
                f"schema_version: template-config/v1\nnormal: [\n{directory}",
            ):
                config_path.write_text(text, encoding="utf-8")
                with self.assertRaises(TemplatePackageValidationError) as caught:
                    validate_template_package(template_path=self.template_path, layout_config_path=config_path)
                self.assertNotIn(directory, str(caught.exception))
                self.assertNotIn(directory, caught.exception.path)

            config_path.unlink()
            with self.assertRaises(TemplatePackageValidationError) as caught:
                validate_template_package(template_path=self.template_path, layout_config_path=config_path)
            self.assertEqual(caught.exception.code, "template_layout_config_unavailable")
            self.assertNotIn(directory, str(caught.exception))

    def _change_zip(self, updates: dict[str, bytes | None]) -> bytes:
        buffer = io.BytesIO()
        with ZipFile(io.BytesIO(self.template_content)) as original, ZipFile(buffer, "w") as changed:
            for name in original.namelist():
                content = updates[name] if name in updates else original.read(name)
                if content is not None:
                    changed.writestr(name, content)
        return buffer.getvalue()
