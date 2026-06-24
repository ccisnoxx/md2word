from __future__ import annotations

# tests/test_golden_sample_manifest.py: 校验 P0 Golden Sample 清单和回归脚本基础合同。

import json
import subprocess
import sys
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from tempfile import TemporaryDirectory
from unittest import TestCase

import yaml

from app.services.renderer.docx_quality import build_docx_quality_flags
from scripts.ops.run_golden_sample_regression import (
    DEFAULT_MANIFEST_PATH,
    RegressionConfig,
    SampleInventory,
    SampleResult,
    apply_manual_signoff_to_report,
    analyze_docx_quality,
    build_preflight_report,
    build_report,
    build_sample_inventory,
    evaluate_manual_quality_signoff,
    format_preflight_report,
    format_manual_signoff_template,
    format_markdown_report,
    load_manifest,
    resolve_sample_root,
    write_preflight_report,
)


class GoldenSampleManifestTests(TestCase):
    def test_manifest_defines_required_sample_coverage(self):
        manifest = load_manifest(DEFAULT_MANIFEST_PATH)
        samples = manifest["samples"]
        all_tags = {tag for sample in samples for tag in sample.get("tags", [])}

        self.assertEqual(len(samples), 4)
        self.assertIn("datasheet", all_tags)
        self.assertIn("double_column", all_tags)
        self.assertIn("headings", all_tags)
        self.assertIn("parameter_table", all_tags)
        self.assertIn("wide_table", all_tags)

    def test_manifest_filenames_are_unique_and_under_sample_root(self):
        manifest = load_manifest(DEFAULT_MANIFEST_PATH)
        sample_root = resolve_sample_root(DEFAULT_MANIFEST_PATH, manifest)
        filenames = [sample["filename"] for sample in manifest["samples"]]

        self.assertEqual(len(filenames), len(set(filenames)))
        self.assertTrue(sample_root.is_absolute())
        for filename in filenames:
            self.assertEqual(Path(filename).name, filename)

    def test_manifest_is_plain_yaml_file(self):
        raw_manifest = DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8")
        decoded = yaml.safe_load(raw_manifest)

        self.assertEqual(decoded["schema_version"], 1)
        self.assertEqual(decoded["target_success_rate"], 1.0)

    def test_regression_config_defaults_to_admin_reviewer_owner(self):
        config = RegressionConfig()

        self.assertEqual(config.username, "admin")
        self.assertEqual(config.required_role, "admin")

    def test_current_sample_inventory_reports_four_runnable_samples(self):
        manifest = load_manifest(DEFAULT_MANIFEST_PATH)
        sample_root = resolve_sample_root(DEFAULT_MANIFEST_PATH, manifest)
        samples = [item for item in manifest["samples"] if item.get("enabled", True)]

        inventory = build_sample_inventory(sample_root, samples, manifest["samples"])

        self.assertEqual(inventory.manifest_samples, 4)
        self.assertEqual(
            inventory.manifest_matched_pdf_files,
            ["OPA228_P1.pdf", "OPA228_P2.pdf", "OPA228_P6.pdf", "OPA228_P7.pdf"],
        )
        self.assertEqual(inventory.missing_pdf_files, [])
        self.assertEqual(inventory.orphan_pdf_files, [])

    def test_inventory_does_not_count_orphan_pdf_as_runnable(self):
        with TemporaryDirectory() as tmp_dir:
            sample_root = Path(tmp_dir)
            (sample_root / "expected.pdf").write_bytes(b"%PDF-1.4\n")
            (sample_root / "orphan.pdf").write_bytes(b"%PDF-1.4\n")
            samples = [
                {"id": "gs-a", "filename": "expected.pdf"},
                {"id": "gs-b", "filename": "missing.pdf"},
            ]

            inventory = build_sample_inventory(sample_root, samples, samples)

        self.assertEqual(inventory.manifest_matched_pdf_files, ["expected.pdf"])
        self.assertEqual(inventory.missing_pdf_files, ["missing.pdf"])
        self.assertEqual(inventory.orphan_pdf_files, ["orphan.pdf"])

    def test_report_summary_includes_inventory_fields(self):
        with TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir)
            config = RegressionConfig(runs_dir=run_dir)
            inventory = SampleInventory(
                manifest_samples=1,
                manifest_matched_pdf_files=[],
                missing_pdf_files=["missing.pdf"],
                orphan_pdf_files=["orphan.pdf"],
            )
            report = build_report(
                config,
                {"target_success_rate": 0.9},
                run_dir,
                [
                    SampleResult(
                        sample_id="gs-a",
                        filename="missing.pdf",
                        title="Missing sample",
                        tags=[],
                        status="missing_pdf",
                        acceptance_focus=["Word 可打开", "人工质量签字"],
                    )
                ],
                inventory,
            )

        summary = report["summary"]
        self.assertEqual(summary["manifest_samples"], 1)
        self.assertEqual(summary["manifest_matched_pdfs"], 0)
        self.assertEqual(summary["runnable_samples"], 0)
        self.assertEqual(summary["missing_pdf_samples"], 1)
        self.assertEqual(summary["orphan_pdf_count"], 1)
        self.assertEqual(summary["orphan_pdf_files"], ["orphan.pdf"])
        self.assertFalse(summary["met_target"])
        self.assertFalse(summary["automated_chain_met_target"])
        self.assertTrue(summary["manual_quality_required"])
        self.assertFalse(summary["p0_release_ready"])
        self.assertEqual(summary["p0_release_blocker"], "automated_chain_target_not_met")
        markdown_report = format_markdown_report(report)
        self.assertIn("Manifest 外 PDF: `orphan.pdf`", markdown_report)
        self.assertIn("P0 发布阻断: `automated_chain_target_not_met`", markdown_report)
        self.assertIn("## Admin 人工验收关注点", markdown_report)
        self.assertIn("- Word 可打开", markdown_report)

    def test_preflight_passes_with_mysql_celery_ready_runtime(self):
        server, thread = _start_ready_server(
            {
                "deployment_init_ready": True,
                "p0_document_jobs_ready": True,
                "effective_repository_backend": "mysql",
                "document_jobs_worker_backend": "celery",
                "readiness_blockers": [],
                "p0_document_jobs_blockers": [],
            }
        )
        try:
            config = RegressionConfig(
                base_url=f"http://127.0.0.1:{server.server_port}",
                bearer_token="token",
                request_timeout_seconds=2,
            )

            report = build_preflight_report(config)
        finally:
            _stop_ready_server(server, thread)

        self.assertTrue(report["ok"])
        self.assertEqual(report["blockers"], [])
        formatted = format_preflight_report(report)
        self.assertIn("Golden Sample preflight", formatted)
        self.assertIn("ok: True", formatted)

    def test_preflight_blocks_non_admin_golden_sample_actor(self):
        server, thread = _start_ready_server(
            {
                "deployment_init_ready": True,
                "p0_document_jobs_ready": True,
                "effective_repository_backend": "mysql",
                "document_jobs_worker_backend": "celery",
                "readiness_blockers": [],
                "p0_document_jobs_blockers": [],
            },
            auth_role="operator",
            auth_username="operator",
        )
        try:
            config = RegressionConfig(
                base_url=f"http://127.0.0.1:{server.server_port}",
                username="operator",
                password="password",
                request_timeout_seconds=2,
            )

            report = build_preflight_report(config)
        finally:
            _stop_ready_server(server, thread)

        self.assertFalse(report["ok"])
        self.assertIn("golden_sample_auth_role_not_admin", report["blockers"])
        self.assertEqual(report["checks"][1]["details"]["role"], "operator")
        self.assertEqual(report["checks"][1]["details"]["required_role"], "admin")

    def test_preflight_blocks_non_mysql_non_celery_runtime(self):
        server, thread = _start_ready_server(
            {
                "deployment_init_ready": True,
                "p0_document_jobs_ready": False,
                "effective_repository_backend": "file",
                "document_jobs_worker_backend": "eager",
                "readiness_blockers": ["document_jobs_worker_backend_eager_in_production"],
                "p0_document_jobs_blockers": ["document_jobs_metadata_store_not_mysql"],
            }
        )
        try:
            config = RegressionConfig(
                base_url=f"http://127.0.0.1:{server.server_port}",
                bearer_token="token",
                request_timeout_seconds=2,
            )

            report = build_preflight_report(config)
        finally:
            _stop_ready_server(server, thread)

        self.assertFalse(report["ok"])
        self.assertIn("document_jobs_metadata_store_not_mysql", report["blockers"])
        self.assertIn("document_jobs_worker_backend_not_celery", report["blockers"])
        self.assertIn("p0_document_jobs_not_ready", report["blockers"])

    def test_write_preflight_report_creates_machine_readable_evidence(self):
        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "nested" / "preflight.json"
            report = {
                "ok": False,
                "blockers": ["golden_sample_api_unreachable"],
                "checks": [],
            }

            write_preflight_report(output_path, report)
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(saved["ok"], False)
        self.assertEqual(saved["blockers"], ["golden_sample_api_unreachable"])

    def test_preflight_script_path_invocation_can_import_project_modules(self):
        with TemporaryDirectory() as tmp_dir:
            repo_root = DEFAULT_MANIFEST_PATH.parents[3]
            output_path = Path(tmp_dir) / "preflight.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(repo_root / "scripts" / "ops" / "run_golden_sample_regression.py"),
                    "--preflight",
                    "--preflight-output",
                    str(output_path),
                ],
                cwd=repo_root,
                check=False,
                capture_output=True,
                text=True,
            )

            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 1)
        self.assertIn("Golden Sample preflight", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)
        self.assertEqual(saved["checks"][0]["name"], "manifest")
        self.assertTrue(saved["checks"][0]["ok"])

    def test_admin_manual_signoff_can_mark_existing_report_release_ready(self):
        with TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir)
            config = RegressionConfig(runs_dir=run_dir)
            inventory = SampleInventory(
                manifest_samples=1,
                manifest_matched_pdf_files=["sample.pdf"],
                missing_pdf_files=[],
                orphan_pdf_files=[],
            )
            report = build_report(
                config,
                {"target_success_rate": 1.0},
                run_dir,
                [
                    SampleResult(
                        sample_id="gs-a",
                        filename="sample.pdf",
                        title="Sample",
                        tags=[],
                        status="succeeded",
                        job_id="docjob_a",
                        docx_sha256="sha256:abc",
                        docx_openable=True,
                        docx_quality={
                            "editable_content_available": True,
                            "image_only_suspected": False,
                            "heading_like_unstyled_paragraphs": 1,
                            "manual_list_marker_paragraphs": 1,
                            "plain_toc_entry_paragraphs": 1,
                            "wide_table_count": 1,
                            "landscape_sections": 0,
                            "latex_residue_count": 1,
                        },
                        docx_quality_flags=[
                            "docx_latex_residue:1",
                            "docx_manual_list_markers:1",
                            "docx_plain_toc_entries:1",
                            "docx_unstyled_heading_candidates:1",
                        ],
                    )
                ],
                inventory,
            )
            signoff = {
                "schema_version": 1,
                "reviewer_role": "admin",
                "reviewer": "admin@example.com",
                "signed_at": "2026-06-16T12:00:00Z",
                "final_signoff": True,
                "samples": [
                    {
                        "sample_id": "gs-a",
                        "filename": "sample.pdf",
                        "job_id": "docjob_a",
                        "docx_sha256": "sha256:abc",
                        "verdict": "pass",
                        "notes": "Admin accepted this residual after checking the generated Word manually.",
                    }
                ],
            }

            apply_manual_signoff_to_report(report, signoff)

        summary = report["summary"]
        self.assertTrue(summary["automated_chain_met_target"])
        self.assertEqual(summary["editable_content_available_samples"], 1)
        self.assertEqual(summary["image_only_suspected_samples"], 0)
        self.assertEqual(summary["docx_quality_flagged_samples"], 1)
        self.assertEqual(
            summary["docx_quality_flags"],
            [
                "docx_latex_residue:1",
                "docx_manual_list_markers:1",
                "docx_plain_toc_entries:1",
                "docx_unstyled_heading_candidates:1",
            ],
        )
        self.assertEqual(summary["heading_like_unstyled_paragraphs_total"], 1)
        self.assertEqual(summary["manual_list_marker_paragraphs_total"], 1)
        self.assertEqual(summary["plain_toc_entry_paragraphs_total"], 1)
        self.assertEqual(summary["wide_table_count_total"], 1)
        self.assertTrue(summary["manual_quality"]["valid"])
        self.assertTrue(summary["p0_release_ready"])
        self.assertIsNone(summary["p0_release_blocker"])
        markdown_report = format_markdown_report(report)
        self.assertIn("P0 发布阻断: `none`", markdown_report)
        self.assertIn("Admin 人工签字有效: `True`", markdown_report)
        self.assertIn("DOCX 质量标记: `docx_latex_residue:1", markdown_report)
        self.assertIn("疑似标题未样式化段落总数: `1`", markdown_report)
        self.assertIn("手写列表符号段落总数: `1`", markdown_report)
        self.assertIn("纯文本目录项段落总数: `1`", markdown_report)
        self.assertIn("宽表总数: `1`", markdown_report)
        self.assertIn("| gs-a | sample.pdf | succeeded | docjob_a", markdown_report)
        self.assertIn("| True | docx_latex_residue:1, docx_manual_list_markers:1", markdown_report)

    def test_admin_manual_signoff_requires_notes_for_passed_docx_quality_flags(self):
        result_payloads = [
            {
                "sample_id": "gs-a",
                "filename": "sample.pdf",
                "status": "succeeded",
                "job_id": "docjob_a",
                "docx_sha256": "sha256:abc",
                "docx_openable": True,
                "docx_quality_flags": ["docx_latex_residue:1"],
            }
        ]
        signoff = {
            "schema_version": 1,
            "reviewer_role": "admin",
            "reviewer": "admin@example.com",
            "signed_at": "2026-06-16T12:00:00Z",
            "final_signoff": True,
            "samples": [
                {
                    "sample_id": "gs-a",
                    "filename": "sample.pdf",
                    "job_id": "docjob_a",
                    "docx_sha256": "sha256:abc",
                    "verdict": "pass",
                    "notes": "",
                }
            ],
        }

        manual_quality = evaluate_manual_quality_signoff(result_payloads, signoff)

        self.assertFalse(manual_quality["valid"])
        self.assertEqual(manual_quality["flagged_without_notes_sample_ids"], ["gs-a"])
        self.assertIn("admin_manual_quality_flag_notes_required", manual_quality["blockers"])

    def test_admin_manual_signoff_requires_matching_job_and_docx_hash(self):
        result_payloads = [
            {
                "sample_id": "gs-a",
                "filename": "sample.pdf",
                "status": "succeeded",
                "job_id": "docjob_a",
                "docx_sha256": "sha256:abc",
                "docx_openable": True,
            }
        ]
        signoff = {
            "schema_version": 1,
            "reviewer_role": "admin",
            "reviewer": "admin@example.com",
            "signed_at": "2026-06-16T12:00:00Z",
            "final_signoff": True,
            "samples": [
                {
                    "sample_id": "gs-a",
                    "filename": "sample.pdf",
                    "job_id": "docjob_other",
                    "docx_sha256": "sha256:abc",
                    "verdict": "pass",
                }
            ],
        }

        manual_quality = evaluate_manual_quality_signoff(result_payloads, signoff)

        self.assertFalse(manual_quality["valid"])
        self.assertEqual(manual_quality["mismatch_sample_ids"], ["gs-a"])
        self.assertIn("admin_manual_word_quality_signoff_incomplete", manual_quality["blockers"])

    def test_manual_signoff_template_contains_current_result_hashes(self):
        report = {
            "run_dir": "tests/tmp/golden_sample_runs/run",
            "results": [
                {
                    "sample_id": "gs-a",
                    "filename": "sample.pdf",
                    "status": "succeeded",
                    "job_id": "docjob_a",
                    "docx_sha256": "sha256:abc",
                    "docx_quality_flags": ["docx_latex_residue:1"],
                    "docx_quality": {
                        "editable_content_available": True,
                        "image_only_suspected": False,
                        "heading_like_unstyled_paragraphs": 1,
                        "manual_list_marker_paragraphs": 1,
                        "plain_toc_entry_paragraphs": 1,
                        "wide_table_count": 1,
                        "landscape_sections": 0,
                        "latex_residue_count": 1,
                    },
                }
            ],
        }

        template = format_manual_signoff_template(report)

        self.assertIn("manual-signoff.yaml", template)
        self.assertIn("docjob_a", template)
        self.assertIn("sha256:abc", template)
        self.assertIn("docx_latex_residue:1", template)
        self.assertIn("latex_residue_count", template)
        self.assertIn("heading_like_unstyled_paragraphs", template)
        self.assertIn("manual_list_marker_paragraphs", template)
        self.assertIn("plain_toc_entry_paragraphs", template)
        self.assertIn("wide_table_count", template)
        self.assertIn("landscape_sections", template)

    def test_docx_quality_analysis_reads_ooxml_structure_without_python_docx(self):
        with TemporaryDirectory() as tmp_dir:
            docx_path = Path(tmp_dir) / "sample.docx"
            with zipfile.ZipFile(docx_path, "w") as package:
                package.writestr("[Content_Types].xml", "<Types/>")
                package.writestr(
                    "word/document.xml",
                    (
                        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
                        "<w:body>"
                        '<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Heading</w:t></w:r></w:p>'
                        '<w:p><w:pPr><w:pStyle w:val="4"/></w:pPr><w:r><w:t>Styled heading</w:t></w:r></w:p>'
                        '<w:p><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Bullet</w:t></w:r></w:p>'
                        '<w:p><w:pPr><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="8504"/></w:tabs></w:pPr>'
                        "<w:r><w:t>Contents</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>2</w:t></w:r></w:p>"
                        '<w:p><w:pPr><w:keepNext/></w:pPr><w:r><w:t>Table 1</w:t></w:r></w:p>'
                        '<w:p><w:r><w:t>$R_{\\theta JA}$</w:t></w:r></w:p>'
                        "<w:tbl><w:tr><w:trPr><w:cantSplit/><w:tblHeader w:val=\"true\"/></w:trPr>"
                        '<w:tc><w:tcPr><w:shd w:fill="EEF3F8"/></w:tcPr>'
                        '<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr></w:p></w:tc>'
                        '<w:tc><w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr></w:p></w:tc>'
                        "</w:tr></w:tbl>"
                        "<w:p><w:r><w:drawing><wp:inline/></w:drawing></w:r></w:p>"
                        '<w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/></w:sectPr>'
                        "</w:body></w:document>"
                    ),
                )
                package.writestr(
                    "word/styles.xml",
                    (
                        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                        '<w:style w:type="paragraph" w:styleId="4"><w:name w:val="heading 2"/></w:style>'
                        "</w:styles>"
                    ),
                )
                package.writestr("word/media/image1.png", b"fake")

            quality = analyze_docx_quality(docx_path)

        self.assertEqual(quality["heading_paragraphs"], 2)
        self.assertEqual(quality["heading_like_unstyled_paragraphs"], 0)
        self.assertEqual(quality["numbering_paragraphs"], 1)
        self.assertEqual(quality["manual_list_marker_paragraphs"], 0)
        self.assertEqual(quality["toc_tab_leader_paragraphs"], 1)
        self.assertEqual(quality["plain_toc_entry_paragraphs"], 0)
        self.assertEqual(quality["keep_next_paragraphs"], 1)
        self.assertEqual(quality["table_header_rows"], 1)
        self.assertEqual(quality["table_no_split_rows"], 1)
        self.assertEqual(quality["shaded_table_cells"], 1)
        self.assertEqual(quality["table_cell_zero_spacing_paragraphs"], 2)
        self.assertEqual(quality["landscape_sections"], 1)
        self.assertEqual(quality["wide_table_count"], 0)
        self.assertEqual(quality["latex_residue_count"], 1)
        self.assertEqual(quality["table_shapes"], ["1x2"])
        self.assertEqual(quality["media_count"], 1)
        self.assertEqual(quality["inline_shape_count"], 1)
        self.assertTrue(quality["editable_text_available"])
        self.assertTrue(quality["editable_content_available"])
        self.assertFalse(quality["image_only_suspected"])
        self.assertEqual(build_docx_quality_flags(quality), ["docx_latex_residue:1"])

    def test_docx_quality_flags_obvious_word_semantics_risks(self):
        with TemporaryDirectory() as tmp_dir:
            docx_path = Path(tmp_dir) / "semantic-risks.docx"
            wide_cells = "".join(f"<w:tc><w:p><w:r><w:t>H{index}</w:t></w:r></w:p></w:tc>" for index in range(6))
            with zipfile.ZipFile(docx_path, "w") as package:
                package.writestr("[Content_Types].xml", "<Types/>")
                package.writestr(
                    "word/document.xml",
                    (
                        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                        "<w:body>"
                        "<w:p><w:r><w:t>6.5 Thermal Information</w:t></w:r></w:p>"
                        "<w:p><w:r><w:t>• Low noise</w:t></w:r></w:p>"
                        "<w:p><w:r><w:t>1 Features........................ 1</w:t></w:r></w:p>"
                        f"<w:tbl><w:tr>{wide_cells}</w:tr></w:tbl>"
                        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>'
                        "</w:body></w:document>"
                    ),
                )

            quality = analyze_docx_quality(docx_path)

        self.assertEqual(quality["heading_like_unstyled_paragraphs"], 1)
        self.assertEqual(quality["manual_list_marker_paragraphs"], 1)
        self.assertEqual(quality["plain_toc_entry_paragraphs"], 1)
        self.assertEqual(quality["wide_table_count"], 1)
        self.assertEqual(
            build_docx_quality_flags(quality),
            [
                "docx_manual_list_markers:1",
                "docx_plain_toc_entries:1",
                "docx_unstyled_heading_candidates:1",
            ],
        )

    def test_docx_quality_analysis_flags_image_only_docx(self):
        with TemporaryDirectory() as tmp_dir:
            docx_path = Path(tmp_dir) / "image-only.docx"
            with zipfile.ZipFile(docx_path, "w") as package:
                package.writestr("[Content_Types].xml", "<Types/>")
                package.writestr(
                    "word/document.xml",
                    (
                        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
                        "<w:body>"
                        "<w:p><w:r><w:drawing><wp:inline/></w:drawing></w:r></w:p>"
                        "</w:body></w:document>"
                    ),
                )
                package.writestr("word/media/page1.png", b"fake")

            quality = analyze_docx_quality(docx_path)

        self.assertEqual(quality["paragraph_count"], 1)
        self.assertEqual(quality["table_count"], 0)
        self.assertEqual(quality["media_count"], 1)
        self.assertEqual(quality["inline_shape_count"], 1)
        self.assertEqual(quality["text_chars"], 0)
        self.assertFalse(quality["editable_text_available"])
        self.assertFalse(quality["editable_content_available"])
        self.assertTrue(quality["image_only_suspected"])
        self.assertEqual(
            build_docx_quality_flags(quality),
            ["docx_no_editable_content", "docx_image_only_suspected"],
        )


def _start_ready_server(
    dependency_checks: dict[str, object],
    *,
    auth_role: str = "admin",
    auth_username: str = "admin",
) -> tuple[HTTPServer, Thread]:
    responses = {
        "/api/v1/health/ready": {
            "status": "ok",
            "dependency_checks": dependency_checks,
        },
        "/api/v1/auth/me": {
            "id": f"user-{auth_username}",
            "username": auth_username,
            "role": auth_role,
            "roles": [auth_role],
            "permissions": ["document_jobs:create"],
            "tenant_id": "tenant",
            "company_id": "company",
            "display_name": auth_username,
        }
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            payload = responses.get(self.path)
            if payload is None:
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            if self.path != "/api/v1/auth/login":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length") or "0")
            if length:
                self.rfile.read(length)
            body = json.dumps(
                {
                    "access_token": "token",
                    "token_type": "bearer",
                    "expires_in": 3600,
                    "role": auth_role,
                    "roles": [auth_role],
                    "permissions": ["document_jobs:create"],
                    "user_id": f"user-{auth_username}",
                    "username": auth_username,
                    "tenant_id": "tenant",
                    "company_id": "company",
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_ready_server(server: HTTPServer, thread: Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
