"""直接加载器保留局部替身，并恢复调用方的真实依赖与父包绑定。"""

from __future__ import annotations

import importlib
import sys
from unittest import TestCase
from unittest.mock import patch

from tests import runtime_direct_loaders


LOADERS = (
    runtime_direct_loaders.load_render_config_module,
    runtime_direct_loaders.load_text_render_module,
    runtime_direct_loaders.load_page_repair_module,
    runtime_direct_loaders.load_page_layout_module,
    runtime_direct_loaders.load_render_table_module,
    runtime_direct_loaders.load_input_adapter_module,
)


class RuntimeDirectLoaderIsolationTests(TestCase):
    def test_loaders_restore_loaded_modules_and_parent_packages(self):
        docx_module = importlib.import_module("docx")
        original_document = docx_module.Document
        importlib.import_module("yaml")
        importlib.import_module("bs4")
        importlib.import_module("loguru")
        for name in (
            "app.conversion.runtime_models",
            "app.conversion.runtime_helpers",
            "app.conversion.runtime.render_config_runtime",
            "app.conversion.runtime.text_rendering",
            "app.conversion.runtime.page_repair_runtime",
            "app.conversion.runtime.page_layout_runtime",
            "app.conversion.runtime.input_adapter_runtime",
            "app.conversion.runtime.translation_runtime",
            "app.conversion.runtime.table_html_parser",
            "app.conversion.runtime.table_long_renderer",
            "app.conversion.runtime.table_render_runtime",
        ):
            importlib.import_module(name)
        parent_packages = tuple(sys.modules[name] for name in (
            "app", "app.conversion", "app.conversion.runtime", "app.conversion.docx_rules",
            "app.services", "app.services.document_ir",
        ))

        for loader in LOADERS:
            with self.subTest(loader=loader.__name__):
                original_modules = dict(sys.modules)
                original_packages = [vars(package).copy() for package in parent_packages]

                module = loader()

                self.assertEqual(set(sys.modules), set(original_modules))
                for name, original_module in original_modules.items():
                    self.assertIs(sys.modules[name], original_module, name)
                for package, original_attributes in zip(parent_packages, original_packages):
                    self.assertEqual(vars(package), original_attributes, package.__name__)
                self.assertIs(docx_module.Document, original_document)
                self.assertEqual(original_document().add_paragraph("真实 DOCX 依赖仍可用").text, "真实 DOCX 依赖仍可用")
                self.assertEqual(module.Block(type="paragraph", bbox=(0, 0, 10, 10), text="局部模型仍可用").text, "局部模型仍可用")

        text_module = runtime_direct_loaders.load_text_render_module()
        table_module = runtime_direct_loaders.load_render_table_module()
        self.assertEqual(text_module.normalize_formula_text("I_{OUT}"), "I<sub>OUT</sub>")
        self.assertEqual(text_module.Pt(2), 2)
        self.assertEqual(table_module.qn("w:p"), "w:p")

    def test_loaders_do_not_leak_missing_modules_or_parent_attributes(self):
        conversion_package = importlib.import_module("app.conversion")
        runtime_package = importlib.import_module("app.conversion.runtime")
        for loader in LOADERS:
            with self.subTest(loader=loader.__name__):
                with patch.dict(sys.modules), patch.dict(vars(conversion_package)), patch.dict(vars(runtime_package)):
                    for name in ("loguru", "app.conversion.runtime_models", "app.conversion.runtime.text_rendering"):
                        sys.modules.pop(name, None)
                    vars(conversion_package).pop("runtime_models", None)
                    vars(runtime_package).pop("text_rendering", None)
                    original_modules = dict(sys.modules)

                    module = loader()

                    self.assertEqual(set(sys.modules), set(original_modules))
                    self.assertNotIn("runtime_models", vars(conversion_package))
                    self.assertNotIn("text_rendering", vars(runtime_package))
                    self.assertEqual(module.Block(type="paragraph", bbox=(0, 0, 10, 10), text="局部模型仍可用").text, "局部模型仍可用")

    def test_loaders_restore_partially_loaded_services_package(self):
        app_package = importlib.import_module("app")
        services_package = importlib.import_module("app.services")
        for loader in (runtime_direct_loaders.load_page_repair_module, runtime_direct_loaders.load_input_adapter_module):
            with self.subTest(loader=loader.__name__):
                with patch.dict(sys.modules), patch.dict(vars(services_package)):
                    for name in sys.modules.copy():
                        if name == "app.services.document_ir" or name.startswith("app.services.document_ir."):
                            sys.modules.pop(name)
                    vars(services_package).pop("document_ir", None)
                    original_modules = dict(sys.modules)

                    module = loader()

                    self.assertEqual(set(sys.modules), set(original_modules))
                    self.assertIs(sys.modules["app.services"], services_package)
                    self.assertIs(app_package.services, services_package)
                    self.assertNotIn("document_ir", vars(services_package))
                    self.assertEqual(module.Block(type="paragraph", bbox=(0, 0, 10, 10), text="局部模型仍可用").text, "局部模型仍可用")

    def test_text_loader_does_not_bind_stub_font_rules_to_real_docx(self):
        docx_module = importlib.import_module("docx")
        qn = importlib.import_module("docx.oxml.ns").qn
        rules_package = importlib.import_module("app.conversion.docx_rules")
        with patch.dict(sys.modules), patch.dict(vars(rules_package)):
            sys.modules.pop("app.conversion.docx_rules.run_fonts", None)
            vars(rules_package).pop("run_fonts", None)

            runtime_direct_loaders.load_text_render_module()

            self.assertNotIn("app.conversion.docx_rules.run_fonts", sys.modules)
            self.assertNotIn("run_fonts", vars(rules_package))
            from app.conversion.docx_rules import run_fonts

            run = docx_module.Document().add_paragraph().add_run("字体槽位仍使用真实 OOXML 名称空间")
            run_fonts.apply_run_fonts(run, font_name="宋体", western_font_name="Arial", complex_script_font_name="Arial")
            fonts = run._element.rPr.rFonts
            self.assertEqual(fonts.get(qn("w:eastAsia")), "宋体")
            self.assertEqual(fonts.get(qn("w:ascii")), "Arial")
            self.assertEqual(fonts.get(qn("w:hAnsi")), "Arial")
            self.assertEqual(fonts.get(qn("w:cs")), "Arial")
