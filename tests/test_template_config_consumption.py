from __future__ import annotations

import io
import unittest
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import yaml
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import nsmap
from lxml import etree

from app.conversion.runtime.table_html_parser import HtmlCell
from app.domains.templates.layout_config_schema import (
    TemplateConfigPackage,
    TemplateLayoutValidationError,
    apply_layout_changes,
    editor_field_schema,
    validate_layout_config,
)
from app.services.document_ir.models import (
    DocumentIR,
    DocumentIRBlock,
    DocumentIRBlockLayout,
    DocumentIRMetadata,
    DocumentIRPage,
)
from app.services.renderer.word_renderer import DocumentIRWordRenderer
from tests.test_document_ir_word_renderer_layout import MINIMAL_PNG_BYTES
from tests.test_template_package_contract import bundled_template_paths


@dataclass(frozen=True)
class Mutation:
    value: str | float | bool
    expected: str | bool
    xpath: str
    part: str = "document"
    scenario: str = "default"


# 注册表独立于编辑 schema。未登记的新增字段会使覆盖检查失败。
PREVIEW_FIELDS = ("font_name", "western_font_name", "complex_script_font_name", "font_size", "bold", "alignment", "space_after")
READONLY_CONFIG_FIELDS = {
    ("page_setup", "page_width_cm"), ("page_setup", "page_height_cm"), ("header", "logo_path"),
    *((group, field) for group in ("part_number", "category") for field in PREVIEW_FIELDS),
}
METADATA_FIELDS = {"schema_version", "template_name", "output_filename"}

RUN_MUTATIONS = {
    "font_name": ("rFonts/@w:eastAsia", "CFG East Asia", "CFG East Asia"),
    "complex_script_font_name": ("rFonts/@w:cs", "CFG Complex", "CFG Complex"),
    "font_size": ("sz/@w:val", 17.5, "35"),
    "italic": ("i[not(@w:val='0' or @w:val='false' or @w:val='off')]", True, True),
    "color": ("color/@w:val", "#D16D32", "D16D32"),
}
PARAGRAPH_MUTATIONS = {
    "alignment": ("jc/@w:val", "right", "right"),
    "space_before": ("spacing/@w:before", 6.5, "130"),
    "space_after": ("spacing/@w:after", 7.5, "150"),
    "line_spacing": ("spacing/@w:line", 1.75, "420"),
    "first_line_indent_pt": ("ind/@w:firstLine", 4, "80"),
    "left_indent_pt": ("ind/@w:left", 5, "100"),
    "right_indent_pt": ("ind/@w:right", 6, "120"),
}
TOC_GROUPS = ("toc_title", "toc_level1", "toc_level2", "toc_level3")
NARROW_TABLE_FIELDS = {"alignment", "line_spacing", "space_before", "space_after",
                       "first_line_indent_pt", "left_indent_pt", "right_indent_pt"}
TEXT_ANCHORS = {
    "heading1": "Heading Alpha",
    "heading2": "Heading Beta",
    "heading3": "Heading Gamma",
    "toc_title": "Table of Contents",
    "normal": "Plain body sample.",
    "table_content": "CellAlpha",
    "table_note": "Note Alpha sample.",
    "caption": "CaptionAlpha",
    "long_table_caption": "A.1 Continued table sample",
}
TABLE = "./w:body/w:tbl[1]"
HEADER_CELL = f"{TABLE}/w:tr[1]/w:tc[1]"
HEADER_TITLE_RUN = "./w:p[1]/w:r[w:t][1]"
FOOTER_LEFT_RUN = ".//w:r[w:t='Version alpha']"


def _paragraph(marker: str) -> str:
    return f".//w:p[w:r/w:t[contains(., '{marker}')]]"


def _western_fonts(run_properties: str) -> str:
    font = f"{run_properties}/w:rFonts"
    return f"concat(string({font}/@w:ascii), '|', string({font}/@w:hAnsi))"


def _string_at(xpath: str) -> str:
    return f"string(({xpath})[1])"


def _run_mutations(run_properties: str) -> dict[str, Mutation]:
    result = {
        field: Mutation(value, expected, f"boolean({run_properties}/w:{target})" if isinstance(expected, bool)
                        else _string_at(f"{run_properties}/w:{target}"))
        for field, (target, value, expected) in RUN_MUTATIONS.items()
    }
    result["western_font_name"] = Mutation(
        "CFG Western", "CFG Western|CFG Western", _western_fonts(run_properties),
    )
    return result


def _text_mutations(group: str, base: dict) -> dict[str, Mutation]:
    if group.startswith("toc_level"):
        part = "styles"
        anchor = f".//w:style[@w:styleId='TOC{group[-1]}']"
        run_properties = f"{anchor}/w:rPr"
    else:
        part = "document"
        anchor = _paragraph(TEXT_ANCHORS[group])
        run_properties = f"{anchor}/w:r[w:t][1]/w:rPr"
    fields = _run_mutations(run_properties)
    if group != "table_note":
        del fields["italic"]
    if group not in {"table_note", "table_content"}:
        bold = not base[group]["bold"]
        fields["bold"] = Mutation(
            bold, bold, f"boolean({run_properties}/w:b[not(@w:val='0' or @w:val='false' or @w:val='off')])",
        )
    fields.update({
        field: Mutation(value, expected, _string_at(f"{anchor}/w:pPr/w:{target}"))
        for field, (target, value, expected) in PARAGRAPH_MUTATIONS.items()
        if group not in TOC_GROUPS or not field.endswith("_indent_pt")
    })
    return {
        field: Mutation(item.value, item.expected, item.xpath, part)
        for field, item in fields.items()
    }


def _consumer_registry(base: dict, table_style_id: str) -> dict[tuple[str, str], Mutation]:
    groups = {
        group: _text_mutations(group, base)
        for group in (*TEXT_ANCHORS, "toc_level1", "toc_level2", "toc_level3")
    }
    groups["page_setup"] = {
        name: Mutation(2.54, "1440", _string_at(f".//w:sectPr/w:pgMar/@w:{attribute}"))
        for name, attribute in {
            "top_margin": "top", "bottom_margin": "bottom", "left_margin": "left", "right_margin": "right",
            "header_distance": "header", "footer_distance": "footer",
        }.items()
    }
    groups["table_content"]["min_font_size"] = Mutation(
        8.5, "17", _string_at(f"{_paragraph('WideCell0')}/w:r[w:t][1]/w:rPr/w:sz/@w:val"),
    )
    groups["table_style"] = {
        "style_name": Mutation("Light Shading", table_style_id, _string_at(f"{TABLE}/w:tblPr/w:tblStyle/@w:val")),
        "header_fill": Mutation("#A0B1C2", "A0B1C2", _string_at(f"{HEADER_CELL}/w:tcPr/w:shd/@w:fill")),
        "border_color": Mutation("#C2A0B1", "C2A0B1", _string_at(f"{TABLE}/w:tblPr/w:tblBorders/w:top/@w:color")),
    }
    groups["header"] = {
        "enabled": Mutation(True, base["header"]["title_text"], _string_at(f"{HEADER_TITLE_RUN}/w:t"), "header"),
        "title_text": Mutation("Edited title", "Edited title", _string_at(f"{HEADER_TITLE_RUN}/w:t"), "header", "header"),
        "logo_height_cm": Mutation(3, "1080000", _string_at("./w:p[1]//wp:extent/@cy"), "header", "logo"),
    }
    groups["footer"] = {
        "enabled": Mutation(True, True, "boolean(.//w:t[.='Version alpha'])", "footer", "footer_disabled"),
        "left_text": Mutation("Version beta", True, "boolean(.//w:t[.='Version beta'])", "footer", "footer_custom"),
        "right_text": Mutation("Company beta", True, "boolean(.//w:t[.='Company beta'])", "footer", "footer_custom"),
        "show_page_number": Mutation(False, False, "boolean(.//w:instrText[normalize-space(.)='PAGE'])", "footer", "footer_custom"),
        "alignment": Mutation("right", "right", _string_at("./w:p[1]/w:pPr/w:jc/@w:val"), "footer", "footer_existing"),
    }
    for group, run, prefix, scenario in (
        ("header", HEADER_TITLE_RUN, "title_", "header"),
        ("footer", FOOTER_LEFT_RUN, "", "footer_custom"),
    ):
        supported_fields = {"font_name", "western_font_name", "complex_script_font_name"}
        if group == "header":
            supported_fields.update(("font_size", "color"))
        for field, item in _run_mutations(f"{run}/w:rPr").items():
            if field in supported_fields:
                groups[group][f"{prefix}{field}"] = Mutation(item.value, item.expected, item.xpath, group, scenario)
    return {(group, field): item for group, fields in groups.items() for field, item in fields.items()}


def _document_ir() -> DocumentIR:
    """用一页真实 IR 触发标题、目录样式、表格和两类题注的写入分支。"""

    headers = "".join(f"<th>W{index}</th>" for index in range(6))
    cells = "".join(f"<td>WideCell{index}</td>" for index in range(6))
    blocks = [
        {"type": "paragraph", "text": TEXT_ANCHORS["toc_title"]},
        {"type": "paragraph", "text": "1 Features........................ 1"},
        {"type": "heading", "level": 1, "text": TEXT_ANCHORS["heading1"]},
        {"type": "heading", "level": 2, "text": TEXT_ANCHORS["heading2"]},
        {"type": "heading", "level": 3, "text": TEXT_ANCHORS["heading3"]},
        {"type": "paragraph", "text": TEXT_ANCHORS["normal"]},
        {
            "type": "table",
            "html": "<table><tr><th>HeaderA</th></tr><tr><td>CellAlpha</td></tr></table>",
            "captions": ["Table 1 CaptionAlpha"],
            "footnotes": [TEXT_ANCHORS["table_note"]],
        },
        {
            "type": "table",
            "html": "<table><tr><th>HeaderB</th></tr><tr><td>CellBeta</td></tr></table>",
            "captions": [TEXT_ANCHORS["long_table_caption"]],
        },
        {"type": "table", "html": f"<table><tr>{headers}</tr><tr>{cells}</tr></table>"},
    ]
    return DocumentIR(
        schema_version="document-ir/v2",
        metadata=DocumentIRMetadata(
            job_id="docjob_template_consumer", source_file_id="file_template_consumer", document_language="en",
        ),
        pages=[DocumentIRPage(index=0, width=612, height=792)],
        blocks=[
            DocumentIRBlock(id=f"cfg_{index}", order=index,
                layout=DocumentIRBlockLayout(page_index=0, bbox=(42, 30 + 60 * index, 560, 50 + 60 * index),
                    role="body", column_hint="wide"), **block)
            for index, block in enumerate(blocks)
        ],
    )


class TemplateConfigConsumptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template_path, config_path = bundled_template_paths()
        cls.base = validate_layout_config(yaml.safe_load(config_path.read_bytes())).model_dump(
            mode="json", exclude={"terminology"}, exclude_none=True,
        )
        cls.styles = Document(cls.template_path).styles
        cls.registry = _consumer_registry(cls.base, cls.styles["Light Shading"].style_id)

    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        self.config_path = directory / "layout.yaml"
        (directory / "override-logo.png").write_bytes(MINIMAL_PNG_BYTES)
        self.renderer = DocumentIRWordRenderer()
        self.document = _document_ir()

    def _render(self, config: dict) -> bytes:
        self.config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        return self.renderer.render_to_bytes(
            self.document, template_path=self.template_path, config_path=self.config_path, image_loader=lambda _: None,
        )

    @staticmethod
    def _read(content: bytes, mutation: Mutation) -> str | bool:
        if mutation.part in {"header", "footer"}:
            section = Document(io.BytesIO(content)).sections[0]
            part = getattr(section, mutation.part).part.blob
        else:
            with ZipFile(io.BytesIO(content)) as package:
                part = package.read(f"word/{mutation.part}.xml")
        return etree.fromstring(part).xpath(mutation.xpath, namespaces=nsmap)

    def test_editor_schema_matches_consumer_registry(self) -> None:
        schema = editor_field_schema()
        readonly = {(group, field) for group, fields in schema["groups"].items()
                    for field, rules in fields.items() if rules["readonly"]}
        editable = {(group, field) for group, fields in schema["groups"].items()
                    for field, rules in fields.items() if not rules["readonly"]}
        self.assertSetEqual(editable, set(self.registry))
        self.assertEqual(readonly, READONLY_CONFIG_FIELDS)
        self.assertEqual(set(schema["meta"]), METADATA_FIELDS)
        self.assertTrue(all(rules["readonly"] for rules in schema["meta"].values()))

    def test_readonly_fields_preserve_historical_values_and_reject_draft_edits(self) -> None:
        for group, field in sorted(READONLY_CONFIG_FIELDS):
            with self.subTest(field=f"{group}.{field}"):
                self.assertIn(field, self.base[group])
                with self.assertRaises(TemplateLayoutValidationError) as raised:
                    apply_layout_changes(self.base, {group: {field: self.base[group][field]}})
                self.assertEqual(raised.exception.path, f"{group}.{field}")
                self.assertEqual(raised.exception.code, "readonly_field")

    def test_single_editable_field_changes_registered_ooxml(self) -> None:
        # 每个场景只准备使字段生效所需的开关和内容。待验变化始终只有一个字段。
        scenarios = {
            "default": {},
            "header": {"header": {"enabled": True}},
            "logo": {"header": {"enabled": True, "logo_path": "override-logo.png"}},
            "footer_disabled": {"footer": {"left_text": "Version alpha", "right_text": "Company alpha"}},
            "footer_custom": {"footer": {"enabled": True, "left_text": "Version alpha", "right_text": "Company alpha"}},
            "footer_existing": {"footer": {"enabled": True}},
        }
        baselines = {}
        for scenario, settings in scenarios.items():
            config = deepcopy(self.base)
            for group, fields in settings.items():
                config[group].update(fields)
            baselines[scenario] = (config, self._render(config))
        for (group, field), mutation in self.registry.items():
            with self.subTest(field=f"{group}.{field}"):
                config, before = baselines[mutation.scenario]
                updated = apply_layout_changes(config, {group: {field: mutation.value}})
                expected_changes = deepcopy(config)
                expected_changes[group][field] = mutation.value
                self.assertEqual(updated, expected_changes)
                after = self._render(updated)
                actual = self._read(after, mutation)
                self.assertEqual(actual, mutation.expected)
                self.assertNotEqual(self._read(before, mutation), actual)
                if group == "table_content" and field in NARROW_TABLE_FIELDS:
                    wide = Mutation(mutation.value, mutation.expected, mutation.xpath.replace("CellAlpha", "WideCell0"))
                    self.assertEqual(self._read(before, wide), self._read(after, wide))

    def test_render_consumes_dimensions_and_hidden_word_styles(self) -> None:
        baseline = self._render(self.base)
        for group, field, mutation in (
            ("page_setup", "page_width_cm", Mutation(22.86, "12960", _string_at(".//w:sectPr/w:pgSz/@w:w"))),
            ("page_setup", "page_height_cm", Mutation(30.48, "17280", _string_at(".//w:sectPr/w:pgSz/@w:h"))),
            ("heading2", "word_style_name", Mutation("Body Text", self.styles["Body Text"].style_id,
                _string_at(f"{_paragraph(TEXT_ANCHORS['heading2'])}/w:pPr/w:pStyle/@w:val"))),
            ("table_style", "header_bold", Mutation(False, False,
                f"boolean({HEADER_CELL}/w:p/w:r[w:t]/w:rPr/w:b[not(@w:val='0')])")),
        ):
            with self.subTest(field=f"{group}.{field}"):
                config = deepcopy(self.base)
                config[group][field] = mutation.value
                rendered = self._render(config)
                self.assertEqual(self._read(rendered, mutation), mutation.expected)
                self.assertNotEqual(self._read(baseline, mutation), mutation.expected)

    def test_html_table_writer_applies_narrow_cell_format(self) -> None:
        config = TemplateConfigPackage.model_validate(apply_layout_changes(self.base, {
            "table_content": {"alignment": "right", "space_before": 6.5, "space_after": 7.5},
        }))
        document = Document(self.template_path)
        table = document.add_table(rows=2, cols=1)
        for index in range(2):
            self.renderer._fill_table_cell(table.cell(index, 0), HtmlCell(text="Cell"), index == 0, config)

        header = table.cell(0, 0).paragraphs[0]
        body = table.cell(1, 0).paragraphs[0]
        self.assertEqual(header.alignment, WD_ALIGN_PARAGRAPH.CENTER)
        self.assertEqual(body.alignment, WD_ALIGN_PARAGRAPH.RIGHT)
        for paragraph in (header, body):
            self.assertEqual(paragraph.paragraph_format.space_before.pt, 6.5)
            self.assertEqual(paragraph.paragraph_format.space_after.pt, 7.5)


if __name__ == "__main__":
    unittest.main()
