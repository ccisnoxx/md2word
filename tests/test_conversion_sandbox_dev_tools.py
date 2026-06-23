"""Validate local conversion sandbox helper scripts."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

import json

from app.conversion import runtime_facade
from scripts.dev import (
    audit_conversion_sandbox,
    migrate_md2word_main_sandbox,
    run_local_mineru_conversion,
    run_local_mineru_debug_config,
)


class LocalMinerUConversionCliTests(TestCase):
    def test_build_conversion_kwargs_uses_official_runtime_contract(self) -> None:
        args = run_local_mineru_conversion.parse_args(
            [
                "--output",
                "out.docx",
                "--layout-config",
                "layout.yaml",
                "--translation-mode",
                "llm_en_to_zh",
                "--translation-trace-output",
                "trace.json",
                "mineru-package",
            ]
        )

        kwargs = run_local_mineru_conversion.build_conversion_kwargs(args)

        self.assertEqual(kwargs["input_path"], "mineru-package")
        self.assertEqual(kwargs["output_path"], "out.docx")
        self.assertEqual(kwargs["layout_config_path"], "layout.yaml")
        self.assertEqual(kwargs["translation_mode"], "en2zh")
        self.assertEqual(kwargs["translation_trace_output"], "trace.json")

    def test_build_conversion_kwargs_accepts_input_from_environment(self) -> None:
        args = run_local_mineru_conversion.parse_args([])

        kwargs = run_local_mineru_conversion.build_conversion_kwargs(
            args,
            environ={run_local_mineru_conversion.DEFAULT_INPUT_ENV: "/tmp/mineru-package"},
        )

        self.assertEqual(kwargs["input_path"], "/tmp/mineru-package")

    def test_missing_input_fails_before_runtime_call(self) -> None:
        args = run_local_mineru_conversion.parse_args([])

        with self.assertRaises(ValueError):
            run_local_mineru_conversion.build_conversion_kwargs(args, environ={})

    def test_main_calls_shared_runtime_runner(self) -> None:
        with mock.patch.object(run_local_mineru_conversion, "configure_logging") as configure_logging, mock.patch.object(
            run_local_mineru_conversion.runtime_runner,
            "run_conversion",
        ) as run_conversion:
            run_local_mineru_conversion.main(["/tmp/mineru-package", "--document-language", "en"])

        configure_logging.assert_called_once_with("INFO")
        run_conversion.assert_called_once()
        self.assertEqual(run_conversion.call_args.kwargs["input_path"], "/tmp/mineru-package")
        self.assertEqual(run_conversion.call_args.kwargs["document_language"], "en")


class LocalMinerUDebugConfigTests(TestCase):
    def test_build_conversion_kwargs_resolves_relative_paths_from_official_repo(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            config_path = repo_root / "local_mineru_debug_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "input_path": "tests/fixtures/mineru-package",
                        "output_path": "tests/tmp/local_mineru_debug/out.docx",
                        "template": "resources/templates/default/datasheet_template.docx",
                        "layout_config": "resources/template_configs/datasheet_template.yaml",
                        "subscript_config": "resources/term_rules/subscripts_dictionary.yaml",
                        "translation_mode": "llm_en_to_zh",
                        "translation_trace_output": "tests/tmp/local_mineru_debug/trace.json",
                    }
                ),
                encoding="utf-8",
            )

            kwargs = run_local_mineru_debug_config.build_conversion_kwargs(config_path, repo_root=repo_root)

        self.assertEqual(kwargs["input_path"], str((repo_root / "tests/fixtures/mineru-package").resolve()))
        self.assertEqual(kwargs["output_path"], str((repo_root / "tests/tmp/local_mineru_debug/out.docx").resolve()))
        self.assertEqual(kwargs["template_path"], str((repo_root / "resources/templates/default/datasheet_template.docx").resolve()))
        self.assertEqual(kwargs["layout_config_path"], str((repo_root / "resources/template_configs/datasheet_template.yaml").resolve()))
        self.assertEqual(kwargs["translation_mode"], "en2zh")
        self.assertEqual(kwargs["translation_trace_output"], str((repo_root / "tests/tmp/local_mineru_debug/trace.json").resolve()))

    def test_build_conversion_kwargs_keeps_absolute_mineru_asset_path(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            absolute_package = Path(tmp_dir) / "md2word_main" / "mineru_result" / "OPA228_P1.pdf-uuid"
            config_path = repo_root / "local_mineru_debug_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "input_path": str(absolute_package),
                        "output_path": "tests/tmp/out.docx",
                        "document_language": "en",
                        "translation_mode": "direct",
                    }
                ),
                encoding="utf-8",
            )

            kwargs = run_local_mineru_debug_config.build_conversion_kwargs(config_path, repo_root=repo_root)

        self.assertEqual(kwargs["input_path"], str(absolute_package.resolve()))
        self.assertEqual(kwargs["document_language"], "en")
        self.assertEqual(kwargs["translation_mode"], "direct")

    def test_unknown_config_key_fails_before_runtime_call(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "local_mineru_debug_config.json"
            config_path.write_text(json.dumps({"input_path": "mineru", "surprise": True}), encoding="utf-8")

            with self.assertRaises(ValueError):
                run_local_mineru_debug_config.build_conversion_kwargs(config_path)

    def test_main_calls_shared_runtime_runner_from_config(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "local_mineru_debug_config.json"
            config_path.write_text(json.dumps({"input_path": "/tmp/mineru-package", "log_level": "DEBUG"}), encoding="utf-8")

            with mock.patch.object(run_local_mineru_debug_config, "configure_logging") as configure_logging, mock.patch.object(
                run_local_mineru_debug_config.runtime_runner,
                "run_conversion",
            ) as run_conversion:
                run_local_mineru_debug_config.main(["--config", str(config_path)])

        configure_logging.assert_called_once_with("DEBUG")
        run_conversion.assert_called_once()
        self.assertEqual(run_conversion.call_args.kwargs["input_path"], str(Path("/tmp/mineru-package").resolve()))


class ConversionSandboxAuditTests(TestCase):
    def test_drift_report_classifies_changed_and_one_sided_files(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            official = root / "official"
            sandbox = root / "sandbox"
            (official / "app" / "conversion").mkdir(parents=True)
            (sandbox / "app" / "conversion").mkdir(parents=True)
            (official / "app" / "conversion" / "same.py").write_text("same\n", encoding="utf-8")
            (sandbox / "app" / "conversion" / "same.py").write_text("same\n", encoding="utf-8")
            (official / "app" / "conversion" / "changed.py").write_text("official\n", encoding="utf-8")
            (sandbox / "app" / "conversion" / "changed.py").write_text("sandbox\n", encoding="utf-8")
            (official / "app" / "conversion" / "official_only.py").write_text("official\n", encoding="utf-8")
            (sandbox / "app" / "conversion" / "sandbox_only.py").write_text("sandbox\n", encoding="utf-8")
            (sandbox / "app" / "conversion" / "ignored.pyc").write_bytes(b"bytecode")

            report = audit_conversion_sandbox.build_drift_report(
                official,
                sandbox,
                ["app/conversion"],
            )

        self.assertTrue(report.has_drift)
        self.assertEqual(report.same_files, ["app/conversion/same.py"])
        self.assertEqual(report.changed_files, ["app/conversion/changed.py"])
        self.assertEqual(report.official_only_files, ["app/conversion/official_only.py"])
        self.assertEqual(report.sandbox_only_files, ["app/conversion/sandbox_only.py"])

    def test_sample_inventory_reports_pdfs_and_mineru_packages(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            sandbox = Path(tmp_dir)
            (sandbox / "test_pdf").mkdir()
            (sandbox / "test_pdf" / "OPA228_P1.pdf").write_bytes(b"%PDF-1.4\n")
            package = sandbox / "mineru_result" / "OPA228_P1.pdf-uuid"
            (package / "images").mkdir(parents=True)
            (package / "abc_content_list_v2.json").write_text("[]", encoding="utf-8")
            (package / "abc_content_list.json").write_text("[]", encoding="utf-8")
            (package / "abc_model.json").write_text("{}", encoding="utf-8")
            (package / "layout.json").write_text("{}", encoding="utf-8")
            (package / "block_list.json").write_text("[]", encoding="utf-8")
            (package / "full.md").write_text("# title\n", encoding="utf-8")
            (package / "images" / "plot.jpg").write_bytes(b"image")

            report = audit_conversion_sandbox.build_sample_inventory(sandbox)

        self.assertEqual(report.pdfs, ["OPA228_P1.pdf"])
        self.assertEqual(len(report.mineru_packages), 1)
        package_report = report.mineru_packages[0]
        self.assertEqual(package_report.candidate_pdf, "OPA228_P1.pdf")
        self.assertTrue(package_report.has_content_list_v2)
        self.assertTrue(package_report.has_content_list)
        self.assertTrue(package_report.has_model_json)
        self.assertTrue(package_report.has_layout_json)
        self.assertTrue(package_report.has_block_list_json)
        self.assertTrue(package_report.has_full_markdown)
        self.assertEqual(package_report.image_count, 1)

    def test_thin_shell_report_blocks_active_duplicate_sources(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            sandbox = Path(tmp_dir)
            for relative_path in ("mineru_to_docx.py", "sandbox_config.json", "README.md"):
                (sandbox / relative_path).write_text("", encoding="utf-8")
            for relative_path in ("test_pdf", "mineru_result", "out", "app"):
                (sandbox / relative_path).mkdir(parents=True)

            report = audit_conversion_sandbox.build_thin_shell_report(sandbox)

        self.assertFalse(report.ok)
        self.assertEqual(report.active_duplicate_paths, ["app"])
        self.assertEqual(report.missing_expected_paths, [])


class Md2wordMainMigrationTests(TestCase):
    def test_migration_archives_duplicate_sources_and_writes_thin_shell(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            official = root / "official"
            sandbox = root / "md2word_main"
            (official / "app" / "conversion").mkdir(parents=True)
            for relative_path in ("app/conversion", "cli_core", "resources", "tests"):
                (sandbox / relative_path).mkdir(parents=True)
                (sandbox / relative_path / "old.py").write_text("old\n", encoding="utf-8")
            for relative_path in ("test_pdf", "mineru_result", "out"):
                (sandbox / relative_path).mkdir(parents=True)
            (sandbox / "mineru_result" / "OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4").mkdir()

            result = migrate_md2word_main_sandbox.migrate_sandbox(
                sandbox_root=sandbox,
                official_root=official,
                apply=True,
            )

            thin_report = audit_conversion_sandbox.build_thin_shell_report(sandbox)

            self.assertTrue(thin_report.ok)
            self.assertFalse((sandbox / "app").exists())
            self.assertFalse((sandbox / "cli_core").exists())
            self.assertFalse((sandbox / "resources").exists())
            self.assertTrue((sandbox / "_legacy_duplicate_core" / "app" / "conversion" / "old.py").exists())
            self.assertTrue((sandbox / "_legacy_duplicate_core" / "cli_core" / "old.py").exists())
            self.assertTrue((sandbox / "_legacy_duplicate_core" / "resources" / "old.py").exists())
            self.assertTrue((sandbox / "mineru_to_docx.py").exists())
            self.assertTrue((sandbox / "config.py").exists())
            self.assertTrue((sandbox / "sandbox_config.json").exists())
            self.assertTrue((sandbox / "tests" / "test_thin_shell.py").exists())
            self.assertIn("app -> _legacy_duplicate_core/app", result.moved_paths)

            second_result = migrate_md2word_main_sandbox.migrate_sandbox(
                sandbox_root=sandbox,
                official_root=official,
                apply=True,
            )
            readme = (sandbox / "README.md").read_text(encoding="utf-8")
            entrypoint = (sandbox / "mineru_to_docx.py").read_text(encoding="utf-8")

            self.assertEqual(second_result.moved_paths, [])
            self.assertFalse((sandbox / "_legacy_duplicate_core" / "tests.2").exists())
            self.assertIn("run_local_mineru_debug_config.py", readme)
            self.assertIn("已标记为 deprecated", readme)
            self.assertIn("已废弃", entrypoint)
            self.assertIn("run_local_mineru_debug_config.py", entrypoint)
            self.assertNotIn("run_local_mineru_conversion", entrypoint)


class OfficialConversionRuntimeBindingTests(TestCase):
    def test_runtime_facade_load_pages_binds_model_classes(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            package_root = Path(tmp_dir)
            payload = [
                [
                    {
                        "type": "title",
                        "bbox": [0, 0, 10, 10],
                        "content": {
                            "title_content": [{"type": "text", "content": "Title"}],
                            "level": 1,
                        },
                    }
                ]
            ]
            payload_path = package_root / "sample_content_list_v2.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")

            pages, source_path = runtime_facade.load_pages(package_root)

        self.assertEqual(source_path, payload_path)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].blocks[0].text, "Title")
