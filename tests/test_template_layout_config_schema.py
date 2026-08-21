"""验证 Word 模板样式配置的单一 schema 与真实 seed 合同。"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from unittest import TestCase

import yaml

from app.domains.templates.layout_config_schema import (
    GROUP_FIELD_SCHEMA,
    TemplateConfigPackage,
    apply_layout_changes,
    editor_field_schema,
    split_layout_config,
    validate_layout_config,
)

RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources" / "template_configs"
PUBLISHED_V1_PATH = RESOURCE_DIR / "datasheet_template.yaml"
CURRENT_V2_PATH = RESOURCE_DIR / "datasheet_template_v2.yaml"
CANDIDATE_V3_PATH = RESOURCE_DIR / "datasheet_template_v3.yaml"
MANIFEST_PATH = RESOURCE_DIR / "templates_manifest.yaml"
PUBLISHED_V1_SHA256 = "1a9ce13488a491367fbfde8d143d22b6cf7c0ce064c99c224ae09ef93f5b3818"
PUBLISHED_V2_SHA256 = "132d0bb76e71c807912031199e894dfc0e3d50bd7534180f8ceaba7a5fa20b4d"
CANDIDATE_V3_SHA256 = "7e279d561688042330dfd8afab12e432df337680ac537df470f4832e577b366e"


class TemplateLayoutConfigSchemaTests(TestCase):
    def setUp(self) -> None:
        self.path = CURRENT_V2_PATH
        self.raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))

    def test_real_seed_matches_editor_and_renderer_contract(self) -> None:
        package = validate_layout_config(self.raw)
        schema = editor_field_schema()
        meta, config, preview_samples = split_layout_config(self.raw)

        self.assertEqual(package.schema_version, "template-config/v1")
        self.assertEqual(list(schema["groups"]), list(GROUP_FIELD_SCHEMA))
        self.assertEqual(len(schema["groups"]), 18)
        self.assertEqual(set(config), set(schema["groups"]))
        self.assertEqual(
            {group: item["label"] for group, item in schema["group_meta"].items()},
            {
                "page_setup": "页面设置",
                "part_number": "首页型号行",
                "category": "首页品类行",
                "heading1": "一级标题",
                "heading2": "二级标题",
                "heading3": "三级标题",
                "toc_title": "目录标题",
                "toc_level1": "目录一级项",
                "toc_level2": "目录二级项",
                "toc_level3": "目录三级项",
                "normal": "正文",
                "table_content": "表格正文",
                "table_style": "表格样式",
                "table_note": "表格注释",
                "caption": "图注 / 表题",
                "long_table_caption": "续表标题",
                "header": "页眉",
                "footer": "页脚",
            },
        )
        self.assertEqual(meta["template_name"], "数据手册模板")
        self.assertIn("normal_text", preview_samples)
        self.assertTrue(schema["groups"]["page_setup"]["page_width_cm"]["readonly"])
        self.assertTrue(schema["groups"]["header"]["logo_path"]["readonly"])
        self.assertEqual(package.normal.font_name, "宋体")
        self.assertEqual(package.normal.western_font_name, "Arial")
        self.assertEqual(package.normal.complex_script_font_name, "Times New Roman")
        for group_name, fields in GROUP_FIELD_SCHEMA.items():
            if group_name != "footer" and "font_name" in fields:
                self.assertEqual(self.raw[group_name]["western_font_name"], "Arial", group_name)
                self.assertEqual(self.raw[group_name]["complex_script_font_name"], "Times New Roman", group_name)
        self.assertEqual(self.raw["header"]["title_western_font_name"], "Arial")
        self.assertEqual(self.raw["header"]["title_complex_script_font_name"], "Times New Roman")
        self.assertEqual(self.raw["footer"]["font_name"], "宋体")
        self.assertEqual(self.raw["footer"]["western_font_name"], "Arial")
        self.assertEqual(self.raw["footer"]["complex_script_font_name"], "Times New Roman")
        self.assertEqual(schema["groups"]["footer"]["left_text"]["type"], "text")
        self.assertEqual(schema["groups"]["footer"]["right_text"]["type"], "text")
        self.assertEqual(schema["groups"]["table_content"]["min_font_size"]["label"], "最小字号")
        self.assertIsNone(package.table_content.min_font_size)

    def test_published_v1_hash_and_legacy_font_schema_remain_readable(self) -> None:
        self.assertEqual(hashlib.sha256(PUBLISHED_V1_PATH.read_bytes()).hexdigest(), PUBLISHED_V1_SHA256)

        package = validate_layout_config(yaml.safe_load(PUBLISHED_V1_PATH.read_text(encoding="utf-8")))

        self.assertEqual(package.normal.western_font_name, package.normal.font_name)
        self.assertEqual(package.normal.complex_script_font_name, package.normal.font_name)
        self.assertEqual(package.header.title_western_font_name, package.header.title_font_name)
        self.assertEqual(package.footer.font_name, "")
        self.assertEqual(package.footer.western_font_name, "")
        self.assertEqual(package.footer.complex_script_font_name, "")
        self.assertEqual(package.footer.left_text, "")
        self.assertEqual(package.footer.right_text, "")

    def test_published_v2_hash_is_immutable(self) -> None:
        self.assertEqual(hashlib.sha256(CURRENT_V2_PATH.read_bytes()).hexdigest(), PUBLISHED_V2_SHA256)

    def test_candidate_v3_is_immutable_valid_and_not_registered_as_published_seed(self) -> None:
        self.assertEqual(hashlib.sha256(CANDIDATE_V3_PATH.read_bytes()).hexdigest(), CANDIDATE_V3_SHA256)

        package = validate_layout_config(yaml.safe_load(CANDIDATE_V3_PATH.read_text(encoding="utf-8")))
        manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(package.table_content.font_size, 9)
        self.assertEqual(package.table_content.min_font_size, 7)
        self.assertEqual(manifest["templates"][0]["version"], 2)
        self.assertEqual(
            manifest["templates"][0]["layout_config_path"],
            "resources/template_configs/datasheet_template_v2.yaml",
        )

    def test_table_min_font_size_is_editable_only_within_preferred_font_range(self) -> None:
        updated = apply_layout_changes(self.raw, {"table_content": {"min_font_size": 7.5}})
        self.assertEqual(updated["table_content"]["min_font_size"], 7.5)

        invalid = yaml.safe_load(yaml.safe_dump(self.raw))
        invalid["table_content"]["min_font_size"] = 10
        with self.assertRaisesRegex(ValueError, "不能大于 font_size"):
            validate_layout_config(invalid)
        invalid["table_content"]["min_font_size"] = 0.5
        with self.assertRaisesRegex(ValueError, "不能小于 1"):
            validate_layout_config(invalid)
        with self.assertRaisesRegex(ValueError, "不支持字段"):
            apply_layout_changes(self.raw, {"normal": {"min_font_size": 7}})

    def test_footer_text_changes_use_shared_text_validation(self) -> None:
        updated = apply_layout_changes(
            self.raw,
            {"footer": {"left_text": " V1.1 ", "right_text": " www.example.com "}},
        )

        self.assertEqual(updated["footer"]["left_text"], "V1.1")
        self.assertEqual(updated["footer"]["right_text"], "www.example.com")
        with self.assertRaisesRegex(ValueError, "128"):
            apply_layout_changes(self.raw, {"footer": {"left_text": "x" * 129}})

    def test_changes_preserve_readonly_meta_samples_and_page_size(self) -> None:
        updated = apply_layout_changes(
            self.raw,
            {
                "normal": {"font_size": 11, "color": "#abcdef"},
                "page_setup": {"top_margin": 2.2},
            },
        )

        self.assertEqual(updated["schema_version"], self.raw["schema_version"])
        self.assertEqual(updated["page_setup"]["page_width_cm"], 21.0)
        self.assertEqual(updated["page_setup"]["page_height_cm"], 29.7)
        self.assertEqual(updated["normal"]["font_size"], 11)
        self.assertEqual(updated["normal"]["color"], "#ABCDEF")
        self.assertEqual(updated["sample_content"], self.raw["sample_content"])

    def test_legacy_font_fields_are_completed_without_overwriting_explicit_empty_values(self) -> None:
        legacy = yaml.safe_load(yaml.safe_dump(self.raw))
        text_groups = [
            group_name
            for group_name, fields in GROUP_FIELD_SCHEMA.items()
            if group_name != "footer" and "font_name" in fields
        ]
        for group_name in text_groups:
            legacy[group_name].pop("western_font_name")
            legacy[group_name].pop("complex_script_font_name")
        legacy["caption"]["western_font_name"] = ""
        legacy["caption"]["complex_script_font_name"] = ""
        legacy["header"].pop("title_western_font_name")
        legacy["header"].pop("title_complex_script_font_name")
        legacy["footer"].pop("font_name")
        legacy["footer"].pop("western_font_name")
        legacy["footer"].pop("complex_script_font_name")

        _, config, _ = split_layout_config(legacy)
        updated = apply_layout_changes(
            legacy,
            {"normal": {"western_font_name": "", "complex_script_font_name": ""}},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            legacy_path = Path(temp_dir) / "legacy.yaml"
            legacy_path.write_text(yaml.safe_dump(legacy, allow_unicode=True), encoding="utf-8")
            loaded = TemplateConfigPackage.load(legacy_path)

        self.assertEqual(config["heading1"]["western_font_name"], config["heading1"]["font_name"])
        self.assertEqual(config["heading1"]["complex_script_font_name"], config["heading1"]["font_name"])
        self.assertEqual(config["caption"]["western_font_name"], "")
        self.assertEqual(config["caption"]["complex_script_font_name"], "")
        self.assertEqual(config["header"]["title_western_font_name"], config["header"]["title_font_name"])
        self.assertEqual(config["footer"]["font_name"], "")
        self.assertEqual(config["footer"]["western_font_name"], "")
        self.assertEqual(config["footer"]["complex_script_font_name"], "")
        self.assertEqual(updated["normal"]["western_font_name"], "")
        self.assertEqual(updated["normal"]["complex_script_font_name"], "")
        self.assertEqual(loaded.heading1.western_font_name, loaded.heading1.font_name)
        self.assertEqual(loaded.caption.western_font_name, "")
        self.assertEqual(loaded.header.title_western_font_name, loaded.header.title_font_name)
        self.assertEqual(loaded.footer.font_name, "")
        self.assertEqual(loaded.footer.western_font_name, "")
        self.assertEqual(loaded.footer.complex_script_font_name, "")

    def test_readonly_unknown_and_non_finite_changes_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "只读"):
            apply_layout_changes(self.raw, {"page_setup": {"page_width_cm": 20}})
        with self.assertRaisesRegex(ValueError, "不支持字段"):
            apply_layout_changes(self.raw, {"normal": {"unknown": 1}})
        with self.assertRaisesRegex(ValueError, "有限"):
            apply_layout_changes(self.raw, {"normal": {"font_size": float("inf")}})
        with self.assertRaisesRegex(ValueError, "number"):
            apply_layout_changes(self.raw, {"normal": {"font_size": "11"}})
        with self.assertRaisesRegex(ValueError, "RGB"):
            apply_layout_changes(self.raw, {"normal": {"color": "##AABBCC"}})

    def test_renderer_rejects_unknown_fields_but_allows_partial_explicit_config(self) -> None:
        package = TemplateConfigPackage.model_validate(
            {"schema_version": "template-config/v1", "normal": {"font_size": 12}}
        )
        self.assertEqual(package.normal.font_size, 12)
        with self.assertRaisesRegex(ValueError, "Extra"):
            validate_layout_config({**self.raw, "unexpected": True})

    def test_managed_config_rejects_corrupted_existing_values_and_unsafe_logo_path(self) -> None:
        invalid_color = yaml.safe_load(yaml.safe_dump(self.raw))
        invalid_color["normal"]["color"] = "not-a-color"
        with self.assertRaisesRegex(ValueError, "RGB"):
            validate_layout_config(invalid_color)

        invalid_margin = yaml.safe_load(yaml.safe_dump(self.raw))
        invalid_margin["page_setup"]["top_margin"] = -1
        with self.assertRaisesRegex(ValueError, "不能小于"):
            validate_layout_config(invalid_margin)

        unsafe_logo = yaml.safe_load(yaml.safe_dump(self.raw))
        unsafe_logo["header"]["logo_path"] = "../secret.png"
        with self.assertRaisesRegex(ValueError, "相对路径"):
            validate_layout_config(unsafe_logo)
