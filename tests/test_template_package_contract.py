from __future__ import annotations

import hashlib
import io
import posixpath
import unittest
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import yaml
from docx import Document
from docx.enum.section import WD_ORIENTATION, WD_SECTION_START
from docx.oxml.ns import qn

from app.core.config import Settings
from app.domains.templates.manifest import BUNDLED_TEMPLATE_MANIFEST, resolve_bundled_template_seed
from app.domains.templates.read_service import TemplateReadService
from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRBlock,
    DocumentIRBlockLayout,
    DocumentIRMetadata,
    DocumentIRPage,
)
from app.services.renderer.word_renderer import DocumentIRWordRenderer
from tests.test_template_layout_config_schema import PUBLISHED_V2_SHA256


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCX_SHA256 = "7b3efd9ce7f19f19ed3a667d10d34995cc6a5b574b24abd85c52a23901577a88"
RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def bundled_template_paths() -> tuple[Path, Path]:
    """从仓库 manifest 取得当前默认模板的回归测试输入。"""

    seed = resolve_bundled_template_seed(ROOT)
    return seed.template_path, seed.layout_config_path


def mixed_section_document() -> DocumentIR:
    """用正文实际触发纵向单栏、双栏、横向和恢复纵向。"""

    blocks = [
        ("源页眉", 0, (0, 0, 400, 30), "page_header", None),
        ("纵向单栏", 0, (0, 45, 400, 60), "body", "wide"),
        ("左栏", 0, (0, 80, 150, 120), "body", "left"),
        ("右栏", 0, (220, 80, 380, 120), "body", "right"),
        ("源页脚", 0, (0, 560, 400, 590), "page_footer", None),
        ("横向单栏", 1, (0, 60, 600, 100), "body", "wide"),
        ("恢复纵向单栏", 2, (0, 60, 400, 100), "body", "wide"),
    ]
    return DocumentIR(
        schema_version="document-ir/v2",
        metadata=DocumentIRMetadata(
            job_id="docjob_template_contract", source_file_id="file_template_contract", document_language="zh",
        ),
        pages=[
            DocumentIRPage(index=0, width=400, height=600),
            DocumentIRPage(index=1, width=600, height=400),
            DocumentIRPage(index=2, width=400, height=600),
        ],
        blocks=[
            DocumentIRBlock(
                id=f"block_{index}",
                type="paragraph",
                order=index,
                text=text,
                layout=DocumentIRBlockLayout(page_index=page, bbox=bbox, role=role, column_hint=column),
            )
            for index, (text, page, bbox, role, column) in enumerate(blocks)
        ],
    )


class TemplatePackageContractTests(unittest.TestCase):
    def test_local_defaults_follow_bundled_binding_and_runtime_uses_configured_manifest(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            bundled_manifest = root / BUNDLED_TEMPLATE_MANIFEST
            bundled_manifest.parent.mkdir(parents=True)
            runtime_manifest = root / "deployment.yaml"
            sources = {}
            for version, manifest in ((3, bundled_manifest), (7, runtime_manifest)):
                template_path = root / f"relocated-{version}.docx"
                config_path = root / f"relocated-{version}.yaml"
                template_path.touch()
                config_path.touch()
                manifest.write_text(yaml.safe_dump({"templates": [{
                    "id": "default", "name": "模板", "is_default_seed": True, "version": version,
                    "template_path": template_path.name, "layout_config_path": config_path.name,
                }]}), encoding="utf-8")
                sources[version] = (template_path, config_path)

            with patch("app.core.config.REPO_ROOT", root):
                settings = Settings(_env_file=None, templates_manifest_path=runtime_manifest.name)
                self.assertEqual((settings.default_template_path, settings.layout_config_path), sources[3])

                runtime = TemplateReadService(settings).resolve_template_version("default@7")
                self.assertEqual((runtime.template_path, runtime.layout_config_path), sources[7])

                fallback = Settings(_env_file=None, templates_manifest_path="absent.yaml")
                restored = TemplateReadService(fallback).resolve_template_version("default@3")
                self.assertEqual((restored.template_path, restored.layout_config_path), sources[3])

    def test_bundled_template_carries_default_decorations_and_logo(self) -> None:
        seed = resolve_bundled_template_seed(ROOT)
        self.assertEqual((seed.item.id, seed.item.version), ("default", 2))
        template_path, config_path = seed.template_path, seed.layout_config_path
        config_content = config_path.read_bytes()
        self.assertEqual(hashlib.sha256(config_content).hexdigest(), PUBLISHED_V2_SHA256)
        config = yaml.safe_load(config_content)
        self.assertIs(config["header"]["enabled"], False)
        self.assertIs(config["footer"]["enabled"], False)

        template = template_path.read_bytes()
        self.assertEqual(hashlib.sha256(template).hexdigest(), DEFAULT_DOCX_SHA256)
        document = Document(io.BytesIO(template))
        self.assertEqual(len(document.sections), 1)
        self.assertFalse(document.sections[0].different_first_page_header_footer)
        self.assertFalse(document.settings.odd_and_even_pages_header_footer)

        with ZipFile(io.BytesIO(template)) as package:
            [decorations] = self._section_decorations(package)
        self.assertEqual(set(decorations), {("header", "default"), ("footer", "default")})
        self.assertTrue(decorations[("header", "default")][1])

    def test_renderer_preserves_template_decorations_across_section_transitions(self) -> None:
        template_path, config_path = bundled_template_paths()
        template = template_path.read_bytes()
        source = Document(io.BytesIO(template))
        rendered = DocumentIRWordRenderer().render_to_bytes(
            mixed_section_document(), template_path=template_path, config_path=config_path, image_loader=lambda _: None,
        )
        self.assertEqual(template_path.read_bytes(), template)
        output = Document(io.BytesIO(rendered))
        self.assertEqual(
            [paragraph.text for paragraph in output.paragraphs if paragraph.text],
            ["纵向单栏", "左栏", "右栏", "横向单栏", "恢复纵向单栏"],
        )

        # 双栏结束先连续恢复单栏，随后才以新页节切换方向。
        self.assertEqual(
            [
                (section.orientation, section.start_type, int(section._sectPr.find(qn("w:cols")).attrib[qn("w:num")]))
                for section in output.sections
            ],
            [
                (WD_ORIENTATION.PORTRAIT, WD_SECTION_START.NEW_PAGE, 1),
                (WD_ORIENTATION.PORTRAIT, WD_SECTION_START.CONTINUOUS, 2),
                (WD_ORIENTATION.PORTRAIT, WD_SECTION_START.CONTINUOUS, 1),
                (WD_ORIENTATION.LANDSCAPE, WD_SECTION_START.NEW_PAGE, 1),
                (WD_ORIENTATION.PORTRAIT, WD_SECTION_START.NEW_PAGE, 1),
            ],
        )
        self.assertEqual(output.settings.odd_and_even_pages_header_footer, source.settings.odd_and_even_pages_header_footer)
        for index, section in enumerate(output.sections):
            with self.subTest(section=index):
                self.assertEqual(
                    section.different_first_page_header_footer, source.sections[0].different_first_page_header_footer,
                )
                self.assertEqual(section.header.is_linked_to_previous, index > 0)
                self.assertEqual(section.footer.is_linked_to_previous, index > 0)

        with ZipFile(io.BytesIO(template)) as template_package, ZipFile(io.BytesIO(rendered)) as rendered_package:
            [expected] = self._section_decorations(template_package)
            self.assertEqual(self._section_decorations(rendered_package), [expected] * len(output.sections))

    def _section_decorations(self, package: ZipFile) -> list[dict[tuple[str, str], tuple[str, tuple[str, ...]]]]:
        """沿各类 Section 引用查找实际生效的装饰及媒体。"""

        document = ET.fromstring(package.read("word/document.xml"))
        relations = self._relationships(package, "word/document.xml")
        inherited = {}
        sections = []
        for section in document.iter(qn("w:sectPr")):
            for kind in ("header", "footer"):
                for reference in section.findall(qn(f"w:{kind}Reference")):
                    relation_type, part, external = relations[reference.attrib[qn("r:id")]]
                    self.assertEqual(relation_type, f"{RELATIONSHIP_NAMESPACE}/{kind}")
                    self.assertFalse(external)
                    inherited[(kind, reference.attrib[qn("w:type")])] = self._decoration(package, part)
            sections.append(inherited.copy())
        return sections

    def _decoration(self, package: ZipFile, part: str) -> tuple[str, tuple[str, ...]]:
        """按被引用媒体的哈希比对装饰，允许生成包重新分配关系 ID。"""

        decoration = ET.fromstring(package.read(part))
        relations = self._relationships(package, part)
        media_hashes = []
        for element in decoration.iter():
            for attribute, relation_id in element.attrib.items():
                if attribute.startswith(f"{{{RELATIONSHIP_NAMESPACE}}}"):
                    relation_type, target, external = relations[relation_id]
                    if relation_type == f"{RELATIONSHIP_NAMESPACE}/image":
                        self.assertFalse(external)
                        target = hashlib.sha256(package.read(target)).hexdigest()
                        media_hashes.append(target)
                    element.set(attribute, target)
        return ET.canonicalize(ET.tostring(decoration)), tuple(media_hashes)

    def _relationships(self, package: ZipFile, part: str) -> dict[str, tuple[str, str, bool]]:
        source = PurePosixPath(part)
        relationship_part = source.parent / "_rels" / f"{source.name}.rels"
        if str(relationship_part) not in package.namelist():
            return {}
        relationships = {}
        for relation in ET.fromstring(package.read(str(relationship_part))):
            target = relation.attrib["Target"]
            external = relation.get("TargetMode") == "External"
            if not external:
                target = posixpath.normpath(posixpath.join(str(source.parent), target)).lstrip("/")
                self.assertIn(target, package.namelist())
            relationships[relation.attrib["Id"]] = (relation.attrib["Type"], target, external)
        return relationships
