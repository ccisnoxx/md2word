from __future__ import annotations

# tests/test_metadata_shadow_copy.py: 覆盖 local file metadata 到 database 的 shadow copy 与校验能力。

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.domains.jobs.models import (
    JobEvent,
    JobFile,
    JobRecord,
    JobStageMessage,
    SourcePdfJobContext,
)
from app.infrastructure.persistence import (
    build_file_persistence_adapters,
    build_mysql_persistence_adapters,
    build_sqlite_persistence_adapters,
)
from scripts.ops.shadow_copy_metadata_to_database import (
    shadow_copy_metadata_to_database,
    validate_metadata_shadow_copy,
)
from scripts.ops.shadow_copy_metadata_to_mysql import (
    shadow_copy_metadata_to_mysql,
    validate_metadata_shadow_copy_to_mysql,
)
from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config


class MetadataShadowCopyTests(TestCase):
    def test_shadow_copy_writes_database_and_validates_all_metadata(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            database_path = Path(temp_dir) / "metadata.sqlite3"
            self._seed_file_metadata(data_dir)

            report = shadow_copy_metadata_to_database(data_dir, database_path)
            validation = validate_metadata_shadow_copy(data_dir, database_path)
            target = build_sqlite_persistence_adapters(database_path)
            persisted_job = target.job_repository.get_job("job_shadow")
            files_count = len(target.job_file_repository.list_files("job_shadow"))
            events_count = len(target.job_event_repository.list_events("job_shadow"))
            stage_messages_count = len(target.stage_message_store.list_stage_messages())
            stage_counts = target.stage_message_store.count_stage_messages_by_status()

        self.assertTrue(report.ok)
        self.assertTrue(report.target_replaced)
        self.assertTrue(validation.ok)
        self.assertEqual(report.source_totals, report.target_totals)
        self.assertEqual(persisted_job.mineru_batch_id, "batch_shadow")
        self.assertEqual(files_count, 2)
        self.assertEqual(events_count, 2)
        self.assertEqual(stage_messages_count, 3)
        self.assertEqual(stage_counts, {"pending": 1, "running": 1, "failed": 1})

    def test_shadow_copy_is_idempotent_and_does_not_duplicate_metadata(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            database_path = Path(temp_dir) / "metadata.sqlite3"
            self._seed_file_metadata(data_dir)

            first_report = shadow_copy_metadata_to_database(data_dir, database_path)
            second_report = shadow_copy_metadata_to_database(data_dir, database_path)
            target = build_sqlite_persistence_adapters(database_path)
            jobs_count = len(target.job_repository.list_jobs())
            files_count = len(target.job_file_repository.list_files("job_shadow"))
            events_count = len(target.job_event_repository.list_events("job_shadow"))
            stage_messages_count = len(target.stage_message_store.list_stage_messages())

        self.assertTrue(first_report.ok)
        self.assertTrue(second_report.ok)
        self.assertEqual(jobs_count, 1)
        self.assertEqual(files_count, 2)
        self.assertEqual(events_count, 2)
        self.assertEqual(stage_messages_count, 3)

    def test_validate_reports_mismatched_database_metadata(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            database_path = Path(temp_dir) / "metadata.sqlite3"
            self._seed_file_metadata(data_dir)
            build_sqlite_persistence_adapters(database_path).job_repository.create_job(
                JobRecord(
                    id="job_other",
                    source_filename="other.zip",
                    status="uploaded",
                    lifecycle_status="uploaded",
                    execution_status="idle",
                )
            )

            report = validate_metadata_shadow_copy(data_dir, database_path)

        self.assertFalse(report.ok)
        self.assertIn("job_ids_mismatch", {item.code for item in report.mismatches})

    def test_shadow_copy_writes_mysql_and_validates_all_metadata(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            fake_mysql = _FakeMysqlDatabase()
            self._seed_file_metadata(data_dir)

            report = shadow_copy_metadata_to_mysql(
                data_dir,
                _mysql_config(),
                connect_factory=fake_mysql.connect,
            )
            validation = validate_metadata_shadow_copy_to_mysql(
                data_dir,
                _mysql_config(),
                connect_factory=fake_mysql.connect,
            )
            target = build_mysql_persistence_adapters(_mysql_config(), connect_factory=fake_mysql.connect)
            persisted_job = target.job_repository.get_job("job_shadow")
            files_count = len(target.job_file_repository.list_files("job_shadow"))
            events_count = len(target.job_event_repository.list_events("job_shadow"))
            stage_messages_count = len(target.stage_message_store.list_stage_messages())

        self.assertTrue(report.ok)
        self.assertTrue(report.target_empty_before_copy)
        self.assertTrue(validation.ok)
        self.assertEqual(report.source_totals, report.target_totals)
        self.assertEqual(persisted_job.mineru_batch_id, "batch_shadow")
        self.assertEqual(files_count, 2)
        self.assertEqual(events_count, 2)
        self.assertEqual(stage_messages_count, 3)

    def test_shadow_copy_to_mysql_refuses_non_empty_target_by_default(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            fake_mysql = _FakeMysqlDatabase()
            self._seed_file_metadata(data_dir)
            build_mysql_persistence_adapters(_mysql_config(), connect_factory=fake_mysql.connect).job_repository.create_job(
                JobRecord(
                    id="job_existing",
                    source_filename="existing.zip",
                    status="uploaded",
                    lifecycle_status="uploaded",
                    execution_status="idle",
                )
            )

            report = shadow_copy_metadata_to_mysql(
                data_dir,
                _mysql_config(),
                connect_factory=fake_mysql.connect,
            )

        self.assertFalse(report.ok)
        self.assertFalse(report.target_empty_before_copy)
        self.assertIn("target_not_empty", {item.code for item in report.mismatches})

    def _seed_file_metadata(self, data_dir: Path) -> None:
        adapters = build_file_persistence_adapters(data_dir)
        job = JobRecord(
            id="job_shadow",
            source_filename="source.pdf",
            status="parsed",
            source_kind="source_pdf",
            lifecycle_status="parsed",
            execution_status="idle",
            source_pdf_context=SourcePdfJobContext(batch_id="batch_shadow", data_id="job_shadow"),
        )
        adapters.job_repository.create_job(job)
        adapters.job_file_repository.upsert_file("job_shadow", JobFile(file_type="source_pdf", path="input/source.pdf"))
        adapters.job_file_repository.upsert_file("job_shadow", JobFile(file_type="parsed_result_package", path="input/parsed-result.zip"))
        adapters.job_event_repository.append_event(
            "job_shadow",
            JobEvent(
                stage="job_created",
                message="created",
                status="accepted",
                trace_id="trace_shadow_1",
            ),
        )
        adapters.job_event_repository.append_event(
            "job_shadow",
            JobEvent(
                stage="mineru_callback_processed",
                message="parsed",
                status="succeeded",
                trace_id="trace_shadow_2",
            ),
        )
        for message in (
            JobStageMessage(
                id="msg_shadow_pending",
                job_id="job_shadow",
                stage="convert_package",
                trace_id="trace_shadow",
                status="pending",
            ),
            JobStageMessage(
                id="msg_shadow_running",
                job_id="job_shadow",
                stage="submit_to_mineru",
                trace_id="trace_shadow",
                status="running",
            ),
            JobStageMessage(
                id="msg_shadow_failed",
                job_id="job_shadow",
                stage="process_callback",
                trace_id="trace_shadow",
                status="failed",
            ),
        ):
            adapters.stage_message_store.put_stage_message(message)
