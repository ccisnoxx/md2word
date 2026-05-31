from __future__ import annotations

# tests/test_local_file_storage_integrity_check.py: 覆盖 local file 存储迁移前只读完整性校验脚本。

import json
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.domains.jobs.models import JobEvent, JobFile, JobRecord, JobStageMessage, SourcePdfJobContext
from app.domains.jobs.paths import build_job_paths, ensure_job_dirs
from scripts.ops.check_local_file_storage_integrity import check_local_file_storage_integrity


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class LocalFileStorageIntegrityCheckTests(TestCase):
    def test_reports_counts_missing_artifacts_and_non_migratable_items(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            job_id = "job_integrity"
            paths = build_job_paths(data_dir, job_id)
            ensure_job_dirs(paths)
            job = JobRecord(
                id=job_id,
                source_filename="source.pdf",
                status="uploaded",
                source_kind="source_pdf",
                lifecycle_status="uploaded",
                execution_status="idle",
                source_pdf_context=SourcePdfJobContext(),
            )
            write_json(paths.job_json, job.model_dump(mode="json"))
            write_json(
                paths.files_json,
                [
                    JobFile(file_type="source_pdf", path="input/source.pdf").model_dump(mode="json"),
                    JobFile(file_type="result_docx", path="../outside.docx").model_dump(mode="json"),
                ],
            )
            paths.events_jsonl.write_text(
                JobEvent(
                    stage="job_created",
                    message="created",
                    status="accepted",
                    trace_id="trace_integrity",
                ).model_dump_json()
                + "\n",
                encoding="utf-8",
            )
            stage_messages_dir = data_dir / "stage_messages"
            write_json(
                stage_messages_dir / "msg_pending.json",
                JobStageMessage(
                    id="msg_pending",
                    job_id=job_id,
                    stage="convert_package",
                    trace_id="trace_integrity",
                    status="pending",
                ).model_dump(mode="json"),
            )
            write_json(
                stage_messages_dir / "msg_running.json",
                JobStageMessage(
                    id="msg_running",
                    job_id=job_id,
                    stage="submit_to_mineru",
                    trace_id="trace_integrity",
                    status="running",
                ).model_dump(mode="json"),
            )
            write_json(
                stage_messages_dir / "msg_failed.json",
                JobStageMessage(
                    id="msg_failed",
                    job_id=job_id,
                    stage="process_callback",
                    trace_id="trace_integrity",
                    status="failed",
                ).model_dump(mode="json"),
            )

            report = check_local_file_storage_integrity(data_dir)

        self.assertTrue(report.read_only)
        self.assertEqual(report.totals["job_records"], 1)
        self.assertEqual(report.totals["job_files"], 2)
        self.assertEqual(report.totals["job_events"], 1)
        self.assertEqual(report.totals["stage_messages"], 3)
        self.assertEqual(report.stage_messages_by_status, {"pending": 1, "running": 1, "failed": 1})
        self.assertEqual(len(report.missing_artifacts), 1)
        self.assertEqual(report.missing_artifacts[0].file_type, "source_pdf")
        self.assertEqual(len(report.non_migratable_items), 1)
        self.assertEqual(report.non_migratable_items[0].code, "job_file_path_invalid")

    def test_empty_data_dir_does_not_create_files(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            before = sorted(path.relative_to(data_dir) for path in data_dir.rglob("*"))

            report = check_local_file_storage_integrity(data_dir)

            after = sorted(path.relative_to(data_dir) for path in data_dir.rglob("*"))

        self.assertEqual(before, after)
        self.assertEqual(report.blocker_count, 0)
        self.assertEqual(report.totals["job_records"], 0)

    def test_reports_fingerprint_mismatches_and_legacy_warning(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            job_id = "job_integrity_fingerprint"
            paths = build_job_paths(data_dir, job_id)
            ensure_job_dirs(paths)
            paths.source_pdf.write_bytes(b"%PDF-1.4\nbody")
            paths.result_docx.write_bytes(b"actual-docx")
            paths.translation_request.write_bytes(b"{}")
            job = JobRecord(
                id=job_id,
                source_filename="source.pdf",
                status="completed",
                progress=100,
            )
            write_json(paths.job_json, job.model_dump(mode="json"))
            write_json(
                paths.files_json,
                [
                    JobFile(
                        file_type="source_pdf",
                        path="input/source.pdf",
                        size_bytes=paths.source_pdf.stat().st_size,
                        sha256=f"sha256:{hashlib.sha256(b'wrong-pdf').hexdigest()}",
                    ).model_dump(mode="json"),
                    JobFile(
                        file_type="result_docx",
                        path="output/result.docx",
                        size_bytes=1,
                        sha256=f"sha256:{hashlib.sha256(b'actual-docx').hexdigest()}",
                    ).model_dump(mode="json"),
                    JobFile(file_type="translation_request", path="translation/request.json").model_dump(mode="json"),
                ],
            )
            before = sorted(path.relative_to(data_dir) for path in data_dir.rglob("*"))

            report = check_local_file_storage_integrity(data_dir)

            after = sorted(path.relative_to(data_dir) for path in data_dir.rglob("*"))

        codes = [item.code for item in report.non_migratable_items]
        warning_codes = [item.code for item in report.warnings]
        self.assertEqual(before, after)
        self.assertIn("artifact_sha256_mismatch", codes)
        self.assertIn("artifact_size_mismatch", codes)
        self.assertIn("artifact_fingerprint_missing", warning_codes)
        self.assertEqual(report.totals["artifacts_fingerprint_mismatch"], 2)
        self.assertEqual(report.totals["artifacts_missing_fingerprint"], 1)
