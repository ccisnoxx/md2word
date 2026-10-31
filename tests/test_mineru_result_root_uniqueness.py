"""覆盖 MinerU 结果根与被选版本唯一性及正式转换的失败报告。"""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.services.document_ir import MinerUToDocumentIRService
from app.services.document_ir.artifact_validator import (
    MinerUArtifactValidationError,
    MinerUValidationReport,
)
from app.services.document_ir.mineru_package import MinerUPackageError, find_content_list


class MinerUResultRootUniquenessTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory(prefix="mineru_root_uniqueness_")
        self.addCleanup(temporary_directory.cleanup)
        self.root = Path(temporary_directory.name)
        self.package_root = self.root / "package"
        self.package_root.mkdir()

    def _write_content_lists(self, *relative_paths: str) -> None:
        payload = [{"type": "text", "text": "可用的源正文", "page_idx": 0}]
        for relative_path in relative_paths:
            path = self.package_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _assert_selection_error(self, code: str, reason: str) -> None:
        with self.assertRaises(MinerUPackageError) as caught:
            find_content_list(self.package_root)
        error = caught.exception
        self.assertEqual(error.code, code)
        self.assertEqual(error.facts, {"reason": reason})
        self.assertNotIn(str(self.root), str(error))

    def _convert_package(self):
        zip_path = self.root / "result.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            for path in self.package_root.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(self.package_root).as_posix())
        return MinerUToDocumentIRService().convert_zip(
            zip_path,
            job_id="root_uniqueness_job",
            source_file_id="root_uniqueness_source",
            document_language="zh",
        )

    def _assert_conversion_error(self, code: str, reason: str) -> MinerUValidationReport:
        with self.assertRaises(MinerUArtifactValidationError) as caught:
            self._convert_package()
        error = caught.exception
        report = error.report
        self.assertFalse(report.can_convert)
        self.assertEqual(report.fatal_count, 1)
        self.assertIsNotNone(report.first_fatal)
        self.assertEqual(report.first_fatal.code, code)
        self.assertEqual(report.first_fatal.facts, {"reason": reason})
        self.assertTrue(report.first_fatal.stops_conversion)
        diagnostics = f"{error}\n{report.model_dump_json()}\n{error.__cause__}"
        for temporary_root in (self.root, Path(tempfile.gettempdir()).resolve()):
            self.assertNotIn(str(temporary_root), diagnostics)
        return report

    def test_single_root_prefers_v2_over_legacy(self) -> None:
        self._write_content_lists("result/content_list.json", "result/document_content_list_v2.json")
        self.assertEqual(
            find_content_list(self.package_root),
            self.package_root / "result/document_content_list_v2.json",
        )

    def test_legacy_only_in_single_root_is_selected(self) -> None:
        self._write_content_lists("nested/result/document_content_list.json")
        self.assertEqual(
            find_content_list(self.package_root),
            self.package_root / "nested/result/document_content_list.json",
        )

    def test_unique_v2_ignores_duplicate_legacy_in_same_root(self) -> None:
        self._write_content_lists(
            "result/content_list.json",
            "result/document_content_list.json",
            "result/content_list_v2.json",
        )
        self.assertEqual(find_content_list(self.package_root), self.package_root / "result/content_list_v2.json")

    def test_multiple_v2_roots_are_rejected(self) -> None:
        self._write_content_lists("content_list_v2.json", "nested/result_content_list_v2.json")
        self._assert_selection_error("mineru_content_list_ambiguous", "multiple_result_roots")

    def test_multiple_legacy_roots_are_rejected(self) -> None:
        self._write_content_lists("first/content_list.json", "second/document_content_list.json")
        self._assert_selection_error("mineru_content_list_ambiguous", "multiple_result_roots")

    def test_mixed_version_roots_are_rejected(self) -> None:
        self._write_content_lists("content_list.json", "nested/document_content_list_v2.json")
        self._assert_selection_error("mineru_content_list_ambiguous", "multiple_result_roots")

    def test_multiple_roots_are_rejected_before_duplicate_version(self) -> None:
        self._write_content_lists("content_list_v2.json", "a_content_list_v2.json", "nested/content_list.json")
        self._assert_selection_error("mineru_content_list_ambiguous", "multiple_result_roots")

    def test_duplicate_v2_in_single_root_is_rejected(self) -> None:
        self._write_content_lists("content_list.json", "content_list_v2.json", "document_content_list_v2.json")
        self._assert_selection_error("mineru_content_list_ambiguous", "multiple_content_lists")

    def test_duplicate_legacy_only_in_single_root_is_rejected(self) -> None:
        self._write_content_lists("result/content_list.json", "result/document_content_list.json")
        self._assert_selection_error("mineru_content_list_ambiguous", "multiple_content_lists")

    def test_missing_content_list_keeps_existing_error(self) -> None:
        (self.package_root / "content_list_v2.json").mkdir()
        (self.package_root / "notcontent_list_v2.json").write_text("[]", encoding="utf-8")
        (self.package_root / "full.md").write_text("正文", encoding="utf-8")
        self._assert_selection_error("mineru_content_list_missing", "missing_content_list")

    def test_converter_reports_multiple_roots_without_paths(self) -> None:
        self._write_content_lists("first/content_list_v2.json", "second/content_list.json")
        report = self._assert_conversion_error("mineru_content_list_ambiguous", "multiple_result_roots")
        self.assertIsNone(report.content_list_path)

    def test_converter_reports_duplicate_version_without_paths(self) -> None:
        self._write_content_lists("result/content_list_v2.json", "result/document_content_list_v2.json")
        report = self._assert_conversion_error("mineru_content_list_ambiguous", "multiple_content_lists")
        self.assertIsNone(report.content_list_path)

    def test_converter_reports_missing_content_list_without_paths(self) -> None:
        report = self._assert_conversion_error("mineru_content_list_missing", "missing_content_list")
        self.assertIsNone(report.content_list_path)

    def test_converter_invalid_v2_does_not_fall_back_to_valid_legacy(self) -> None:
        self._write_content_lists("result/content_list.json")
        legacy_result = self._convert_package()
        self.assertTrue(legacy_result.validation_report.can_convert)
        self.assertEqual([block.text for block in legacy_result.document.blocks], ["可用的源正文"])
        self.assertEqual(legacy_result.validation_report.content_list_path, "result/content_list.json")

        v2_path = self.package_root / "result/content_list_v2.json"
        for raw_v2, reason in (("{", "unreadable_json"), ("{}", "unsupported_top_level")):
            with self.subTest(reason=reason):
                v2_path.write_text(raw_v2, encoding="utf-8")
                report = self._assert_conversion_error("mineru_json_invalid", reason)
                self.assertEqual(report.content_list_path, "result/content_list_v2.json")


if __name__ == "__main__":
    unittest.main()
