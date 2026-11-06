"""直接验证正式 renderer 复用的术语规则加载合同。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from app.conversion.docx_rules.terminology import TerminologyReplacer


class RenderConfigCharacterizationTests(unittest.TestCase):
    def test_terminology_replacer_sorts_rules_by_priority_then_length(self):
        raw_config = {
            "case_sensitive": True,
            "categories": {
                "precise": {"priority": 10},
                "fallback": {"priority": 20},
            },
            "subscript_rules": {
                "fallback": {"V": "VOLT"},
                "precise": {"VIN": "PIN", "VOUT": "OUTPUT"},
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "format-rules.yaml"
            config_path.write_text(yaml.safe_dump(raw_config), encoding="utf-8")
            replacer = TerminologyReplacer(config_path)

        self.assertEqual([rule.source for rule in replacer.rules], ["VOUT", "VIN", "V"])
        self.assertEqual(replacer.replace_text("VIN VOUT V"), "PIN OUTPUT VOLT")

    def test_terminology_replacer_respects_rules_meta_apply_scope_and_case_sensitivity(self):
        raw_config = {
            "case_sensitive": True,
            "categories": {
                "mixed": {"priority": 100},
            },
            "subscript_rules": {
                "mixed": {
                    "VIN": "V<sub>IN</sub>",
                    "vout": "V<sub>OUT</sub>",
                    "OFF": "SHOULD_NOT_APPEAR",
                }
            },
            "rules_meta": {
                "VIN": {"apply_scope": "table", "case_sensitive": True, "enabled": True, "priority": 10},
                "vout": {"apply_scope": "markdown", "case_sensitive": False, "enabled": True, "priority": 20},
                "OFF": {"enabled": False, "priority": 1},
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "format-rules.yaml"
            config_path.write_text(yaml.safe_dump(raw_config), encoding="utf-8")
            replacer = TerminologyReplacer(config_path)

        self.assertEqual([(rule.source, rule.priority) for rule in replacer.rules], [("VIN", 10), ("vout", 20)])
        self.assertEqual(replacer.replace_text("VIN vout VOUT OFF"), "VIN V<sub>OUT</sub> V<sub>OUT</sub> OFF")
        self.assertEqual(replacer._replace_text_for_output_mode("VIN vin vOut OFF", "table"), "V<sub>IN</sub> vin vOut OFF")
        self.assertEqual(
            replacer.replace_html("<table><tr><td>VIN vin vOut OFF</td></tr></table>"),
            "<table><tr><td>V<sub>IN</sub> vin vOut OFF</td></tr></table>",
        )

    def test_terminology_replacer_rejects_invalid_yaml(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "invalid-format-rules.yaml"
            config_path.write_text("subscript_rules: [\n", encoding="utf-8")

            with self.assertRaises(yaml.YAMLError):
                TerminologyReplacer(config_path)

    def test_terminology_replacer_keeps_missing_or_non_mapping_rules_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "format-rules.yaml"
            missing = TerminologyReplacer(config_path)
            config_path.write_text("subscript_rules: []\n", encoding="utf-8")
            unsupported = TerminologyReplacer(config_path)

        for name, replacer in (("missing", missing), ("non_mapping_rules", unsupported)):
            with self.subTest(name=name):
                self.assertEqual(replacer.rules, [])
                self.assertEqual(replacer.replace_text("VIN"), "VIN")


if __name__ == "__main__":
    unittest.main()
