from __future__ import annotations

# tests/test_database_job_repository.py: 校验 sqlite/MySQL metadata adapter 与 file backend 的协议行为一致。

from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.document_job_models import DocumentJobEventRecord, DocumentJobRecord
from app.core.job_models import (
    JobEvent,
    JobFile,
    JobRecord,
    JobStageMessage,
    SourcePdfJobContext,
    build_source_pdf_context_patch,
    utc_now,
)
from app.core.audit_models import AuditEvent
from app.core.config import Settings
from app.core.file_models import DocumentFileRecord
from app.main import build_runtime, create_app
from app.repositories.database_job_repository import DatabaseJobRepository
from app.repositories.file_job_repository import FileJobRepository
from app.repositories.mysql_job_repository import MysqlJobRepository, MysqlJobRepositoryConfig
from app.services.jobs.query import JobQueryService
from tests.test_fastapi_jobs_backend import (
    build_callback_payload,
    build_test_runtime,
    make_zip_bytes,
    publish_default_job_resources,
)


def _mysql_config() -> MysqlJobRepositoryConfig:
    return MysqlJobRepositoryConfig(
        host="127.0.0.1",
        port=3306,
        user="md2word",
        password="",
        database="md2word_test",
    )


class _FakeMysqlDatabase:
    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self.job_events: list[dict[str, Any]] = []
        self.audit_events: list[dict[str, Any]] = []
        self.document_files: dict[str, dict[str, Any]] = {}
        self.document_jobs: dict[str, dict[str, Any]] = {}
        self.job_files: dict[tuple[str, str], dict[str, Any]] = {}
        self.stage_messages: dict[str, dict[str, Any]] = {}
        self.resource_versions: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.resource_default_versions: dict[tuple[str, str], dict[str, Any]] = {}
        self.next_event_id = 1
        self.created_tables: set[str] = set()

    def connect(self) -> "_FakeMysqlConnection":
        return _FakeMysqlConnection(self)


class _FakeMysqlConnection:
    def __init__(self, database: _FakeMysqlDatabase) -> None:
        self.database = database

    def cursor(self) -> "_FakeMysqlCursor":
        return _FakeMysqlCursor(self.database)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeMysqlCursor:
    def __init__(self, database: _FakeMysqlDatabase) -> None:
        self.database = database
        self._rows: list[dict[str, Any]] = []

    def __enter__(self) -> "_FakeMysqlCursor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        normalized = " ".join(sql.lower().split())
        if normalized.startswith("create table"):
            for table in (
                "jobs",
                "job_events",
                "job_files",
                "stage_messages",
                "resource_versions",
                "resource_default_versions",
                "audit_events",
                "document_files",
                "document_jobs",
            ):
                if f" {table} " in normalized:
                    self.database.created_tables.add(table)
            self._rows = []
            return
        if normalized.startswith("insert into jobs"):
            job_id, payload, created_at, updated_at = params
            self.database.jobs[job_id] = {
                "job_id": job_id,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from jobs where job_id"):
            row = self.database.jobs.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from jobs order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(self.database.jobs.values(), key=lambda item: (item["created_at"], item["job_id"]))
            ]
            return
        if normalized.startswith("insert into job_events"):
            job_id, payload, created_at = params
            self.database.job_events.append(
                {
                    "id": self.database.next_event_id,
                    "job_id": job_id,
                    "payload": payload,
                    "created_at": created_at,
                }
            )
            self.database.next_event_id += 1
            self._rows = []
            return
        if normalized.startswith("select payload from job_events where job_id"):
            rows = [row for row in self.database.job_events if row["job_id"] == params[0]]
            self._rows = [{"payload": row["payload"]} for row in sorted(rows, key=lambda item: item["id"])]
            return
        if normalized.startswith("insert into audit_events"):
            audit_id, payload, created_at = params
            self.database.audit_events.append(
                {
                    "id": self.database.next_event_id,
                    "audit_id": audit_id,
                    "payload": payload,
                    "created_at": created_at,
                }
            )
            self.database.next_event_id += 1
            self._rows = []
            return
        if normalized.startswith("select payload from audit_events order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(self.database.audit_events, key=lambda item: (item["created_at"], item["id"]))
            ]
            return
        if normalized.startswith("insert into document_files"):
            file_id, payload, created_at, updated_at = params
            self.database.document_files[file_id] = {
                "file_id": file_id,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from document_files where file_id"):
            row = self.database.document_files.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from document_files order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(
                    self.database.document_files.values(),
                    key=lambda item: (item["created_at"], item["file_id"]),
                )
            ]
            return
        if normalized.startswith("insert into document_jobs"):
            job_id, payload, created_at, updated_at = params
            self.database.document_jobs[job_id] = {
                "job_id": job_id,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from document_jobs where job_id"):
            row = self.database.document_jobs.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("select payload from document_jobs order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(
                    self.database.document_jobs.values(),
                    key=lambda item: (item["created_at"], item["job_id"]),
                )
            ]
            return
        if normalized.startswith("insert into job_files"):
            job_id, file_type, payload, created_at = params
            self.database.job_files[(job_id, file_type)] = {
                "job_id": job_id,
                "file_type": file_type,
                "payload": payload,
                "created_at": created_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from job_files where job_id"):
            rows = [row for row in self.database.job_files.values() if row["job_id"] == params[0]]
            self._rows = [{"payload": row["payload"]} for row in sorted(rows, key=lambda item: (item["created_at"], item["file_type"]))]
            return
        if normalized.startswith("insert into stage_messages"):
            message_id, job_id, status, payload, created_at, updated_at = params
            self.database.stage_messages[message_id] = {
                "message_id": message_id,
                "job_id": job_id,
                "status": status,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if normalized.startswith("select payload from stage_messages where message_id"):
            row = self.database.stage_messages.get(params[0])
            self._rows = [{"payload": row["payload"]}] if row is not None else []
            return
        if normalized.startswith("update stage_messages"):
            job_id, status, payload, created_at, updated_at, message_id = params
            self.database.stage_messages[message_id] = {
                "message_id": message_id,
                "job_id": job_id,
                "status": status,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from stage_messages where status in" in normalized:
            rows = [
                row
                for row in self.database.stage_messages.values()
                if row["status"] in {"pending", "running"}
            ]
            self._rows = [{"payload": row["payload"]} for row in sorted(rows, key=lambda item: (item["created_at"], item["message_id"]))]
            return
        if normalized.startswith("select payload from stage_messages order by"):
            self._rows = [
                {"payload": row["payload"]}
                for row in sorted(self.database.stage_messages.values(), key=lambda item: (item["created_at"], item["message_id"]))
            ]
            return
        if normalized.startswith("select status, count(*) as count from stage_messages"):
            counts: dict[str, int] = {}
            for row in self.database.stage_messages.values():
                counts[row["status"]] = counts.get(row["status"], 0) + 1
            self._rows = [{"status": status, "count": count} for status, count in counts.items()]
            return
        if normalized.startswith("delete from stage_messages"):
            self.database.stage_messages.pop(params[0], None)
            self._rows = []
            return
        if normalized.startswith("insert into resource_versions"):
            resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, created_at, updated_at = params
            self.database.resource_versions[(resource_type, resource_id, version)] = {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "version": version,
                "status": status,
                "snapshot_hash": snapshot_hash,
                "payload_ref": payload_ref,
                "payload": payload,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from resource_versions where resource_type" in normalized and "and version" in normalized:
            resource_type, resource_id, version = params
            row = self.database.resource_versions.get((resource_type, resource_id, version))
            self._rows = [row] if row is not None else []
            return
        if "from resource_versions where resource_type" in normalized and "order by created_at" in normalized:
            resource_type, resource_id = params
            rows = [
                row
                for key, row in self.database.resource_versions.items()
                if key[0] == resource_type and key[1] == resource_id
            ]
            self._rows = sorted(rows, key=lambda item: (item["created_at"], item["version"]))
            return
        if normalized.startswith("insert into resource_default_versions"):
            resource_type, resource_id, version, updated_at = params
            self.database.resource_default_versions[(resource_type, resource_id)] = {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "version": version,
                "updated_at": updated_at,
            }
            self._rows = []
            return
        if "from resource_default_versions" in normalized and "join resource_versions" in normalized:
            resource_type, resource_id = params
            pointer = self.database.resource_default_versions.get((resource_type, resource_id))
            row = None
            if pointer is not None:
                row = self.database.resource_versions.get((resource_type, resource_id, pointer["version"]))
            self._rows = [row] if row is not None else []
            return
        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self._rows)


class DatabaseJobRepositoryTests(TestCase):
    def test_metadata_repository_contract_matches_file_backend(self):
        for repository_name, build_repository in (
            ("file", lambda data_dir: FileJobRepository(data_dir / "file")),
            ("database", lambda data_dir: DatabaseJobRepository(data_dir / "metadata.sqlite3")),
            (
                "mysql",
                lambda data_dir: MysqlJobRepository(
                    _mysql_config(),
                    connect_factory=_FakeMysqlDatabase().connect,
                ),
            ),
        ):
            with self.subTest(repository=repository_name):
                with TemporaryDirectory() as temp_dir:
                    repository = build_repository(Path(temp_dir))

                    self._exercise_metadata_contract(repository)

    def test_mysql_schema_bootstrap_includes_resource_versions(self):
        fake_mysql = _FakeMysqlDatabase()

        MysqlJobRepository(_mysql_config(), connect_factory=fake_mysql.connect)

        self.assertEqual(
            fake_mysql.created_tables,
            {
                "jobs",
                "job_events",
                "job_files",
                "stage_messages",
                "resource_versions",
                "resource_default_versions",
                "audit_events",
                "document_files",
                "document_jobs",
            },
        )

    def test_document_job_status_machine_rejects_invalid_stage(self):
        with self.assertRaises(ValidationError):
            DocumentJobRecord(
                id="docjob_invalid",
                tenant_id="tenant_default",
                company_id="company_default",
                created_by="operator",
                source_file_id="file_invalid",
                template_version_id="default",
                status="succeeded",
                stage="uploaded",
            )

    def test_database_repository_persists_records_across_instances(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "metadata.sqlite3"
            first_repository = DatabaseJobRepository(database_path)
            job = self._build_source_pdf_job("job_persisted")

            first_repository.create_job(job)
            first_repository.append_event(
                job.id,
                JobEvent(
                    stage="job_created",
                    message="created",
                    status="accepted",
                    trace_id="trace_persisted",
                ),
            )

            second_repository = DatabaseJobRepository(database_path)
            persisted_job = second_repository.get_job(job.id)
            persisted_events = second_repository.list_events(job.id)

        self.assertIsNotNone(persisted_job)
        self.assertEqual(persisted_job.id, job.id)
        self.assertEqual([event.stage for event in persisted_events], ["job_created"])

    def test_jobs_api_pdf_callback_flow_uses_database_repository(self):
        with TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token",
                jobs_repository_backend="database",
            )
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\n", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                callback_payload, _content = build_callback_payload(
                    batch_id="batch_test_001",
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                callback_response = client.post("/api/v1/mineru-callbacks/result", json=callback_payload)
                detail_response = client.get(f"/api/v1/jobs/{job_id}")

            persisted_job = runtime.repository.get_job(job_id)
            persisted_files = runtime.repository.list_files(job_id)
            replayable_messages = runtime.stage_message_store.list_replayable_stage_messages()

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(callback_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertIsInstance(runtime.repository, DatabaseJobRepository)
        self.assertEqual(detail_response.json()["status"], "completed")
        self.assertEqual(persisted_job.status, "completed")
        self.assertEqual(
            {file.file_type for file in persisted_files},
            {"source_pdf", "parsed_result_package", "result_docx"},
        )
        self.assertEqual(replayable_messages, [])

    def test_jobs_api_pdf_callback_flow_uses_mysql_repository(self):
        with TemporaryDirectory() as temp_dir:
            fake_mysql = _FakeMysqlDatabase()
            runtime = build_test_runtime(
                Path(temp_dir),
                mineru_api_token="token",
                jobs_repository_backend="mysql",
                repository_factory=lambda data_dir: MysqlJobRepository(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
            )
            publish_default_job_resources(runtime)
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs/pdf",
                    files={"pdf": ("source.pdf", b"%PDF-1.4\n", "application/pdf")},
                )
                job_id = create_response.json()["job_id"]
                callback_payload, _content = build_callback_payload(
                    batch_id="batch_test_001",
                    data_id=job_id,
                    state="done",
                    full_zip_url="https://mineru.net/result.zip",
                )
                callback_response = client.post("/api/v1/mineru-callbacks/result", json=callback_payload)
                detail_response = client.get(f"/api/v1/jobs/{job_id}")

            checks = runtime.health_service.build_dependency_checks()
            persisted_job = runtime.repository.get_job(job_id)
            persisted_files = runtime.repository.list_files(job_id)
            replayable_messages = runtime.stage_message_store.list_replayable_stage_messages()

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(callback_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertIsInstance(runtime.repository, MysqlJobRepository)
        self.assertEqual(detail_response.json()["status"], "completed")
        self.assertEqual(persisted_job.status, "completed")
        self.assertEqual(
            {file.file_type for file in persisted_files},
            {"source_pdf", "parsed_result_package", "result_docx"},
        )
        self.assertEqual(replayable_messages, [])
        self.assertEqual(checks["configured_repository_backend"], "mysql")
        self.assertEqual(checks["effective_repository_backend"], "mysql")
        self.assertEqual(checks["stage_message_store"], "mysql")
        self.assertTrue(checks["stage_spool_dir_exists"])

    def test_jobs_api_retry_flow_uses_database_repository(self):
        with TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                jobs_repository_backend="database",
                admin_token="secret-admin",
            )
            runtime.stage_service.conversion_entrypoint.raise_error = True
            app = create_app(runtime)
            with TestClient(app) as client:
                create_response = client.post(
                    "/api/v1/jobs",
                    files={"package": ("mineru-output.zip", make_zip_bytes(), "application/zip")},
                )
                job_id = create_response.json()["job_id"]
                failed_detail = client.get(f"/api/v1/jobs/{job_id}").json()

                runtime.stage_service.conversion_entrypoint.raise_error = False
                retry_response = client.post(
                    f"/api/v1/jobs/{job_id}/retry",
                    data={"reason": "retry-database"},
                    headers={"X-Admin-Token": "secret-admin"},
                )
                completed_detail = client.get(f"/api/v1/jobs/{job_id}").json()

            persisted_job = runtime.repository.get_job(job_id)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(failed_detail["status"], "failed")
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(completed_detail["status"], "completed")
        self.assertEqual(persisted_job.status, "completed")

    def test_replay_pending_flow_uses_database_repository(self):
        with TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir), jobs_repository_backend="database")
            job = JobRecord(
                id="job_database_replay",
                source_filename="source.pdf",
                status="queued",
                progress=10,
                source_kind="source_pdf",
                lifecycle_status="uploaded",
                execution_status="queued",
                source_pdf_context=SourcePdfJobContext(),
            )
            runtime.repository.create_job(job)
            for message in (
                JobStageMessage(
                    id="msg_database_pending",
                    job_id=job.id,
                    stage="submit_to_mineru",
                    trace_id="trace_database_pending",
                    status="pending",
                ),
                JobStageMessage(
                    id="msg_database_running",
                    job_id=job.id,
                    stage="process_callback",
                    trace_id="trace_database_running",
                    status="running",
                ),
                JobStageMessage(
                    id="msg_database_failed",
                    job_id=job.id,
                    stage="convert_package",
                    trace_id="trace_database_failed",
                    status="failed",
                ),
            ):
                runtime.stage_message_store.put_stage_message(message)
            dispatched: list[str] = []
            runtime.stage_service.dispatch_message = lambda message_id: dispatched.append(message_id)

            runtime.stage_dispatcher.replay_pending()

        self.assertEqual(dispatched, ["msg_database_pending", "msg_database_running"])

    def test_build_runtime_switches_to_database_repository_and_readiness(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            settings = Settings(
                _env_file=None,
                data_dir=str(data_dir),
                jobs_repository_backend="database",
                jobs_metadata_database_path=str(data_dir / "metadata.sqlite3"),
            )
            runtime = build_runtime(settings)
            checks = runtime.health_service.build_dependency_checks()

        self.assertIsInstance(runtime.repository, DatabaseJobRepository)
        self.assertIs(runtime.job_repository, runtime.repository)
        self.assertIs(runtime.stage_message_store, runtime.repository)
        self.assertEqual(checks["configured_repository_backend"], "database")
        self.assertEqual(checks["effective_repository_backend"], "database")
        self.assertEqual(checks["stage_message_store"], "database")
        self.assertEqual(checks["artifact_storage"], "local_file")
        self.assertTrue(checks["jobs_dir_exists"])
        self.assertTrue(checks["stage_spool_dir_exists"])

    def test_build_runtime_switches_to_mysql_repository_and_readiness(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            fake_mysql = _FakeMysqlDatabase()
            settings = Settings(
                _env_file=None,
                data_dir=str(data_dir),
                jobs_repository_backend="mysql",
                jobs_mysql_database="md2word_test",
            )
            with patch(
                "app.main.MysqlJobRepository",
                lambda config: MysqlJobRepository(config, connect_factory=fake_mysql.connect),
            ):
                runtime = build_runtime(settings)
            checks = runtime.health_service.build_dependency_checks()

        self.assertIsInstance(runtime.repository, MysqlJobRepository)
        self.assertIs(runtime.job_repository, runtime.repository)
        self.assertIs(runtime.stage_message_store, runtime.repository)
        self.assertEqual(checks["configured_repository_backend"], "mysql")
        self.assertEqual(checks["effective_repository_backend"], "mysql")
        self.assertEqual(checks["stage_message_store"], "mysql")
        self.assertEqual(checks["artifact_storage"], "local_file")
        self.assertTrue(checks["jobs_dir_exists"])
        self.assertTrue(checks["stage_spool_dir_exists"])

    def test_build_runtime_keeps_file_repository_as_local_default(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            settings = Settings(_env_file=None, data_dir=str(data_dir))
            runtime = build_runtime(settings)
            checks = runtime.health_service.build_dependency_checks()
            database_file_exists = settings.jobs_metadata_database_file.exists()

        self.assertEqual(settings.jobs_repository_backend, "file")
        self.assertIsInstance(runtime.repository, FileJobRepository)
        self.assertEqual(checks["configured_repository_backend"], "file")
        self.assertEqual(checks["effective_repository_backend"], "file")
        self.assertEqual(checks["stage_message_store"], "file")
        self.assertFalse(database_file_exists)

    def _exercise_metadata_contract(self, repository: Any) -> None:
        job = self._build_source_pdf_job("job_contract")
        repository.create_job(job)

        stored_job = repository.get_job(job.id)
        self.assertIsNotNone(stored_job)
        self.assertEqual(stored_job.read_mineru_batch_id(), "batch_1")
        self.assertEqual(stored_job.mineru_batch_id, "batch_1")

        updated_job = repository.update_job(
            job.id,
            status="parsed",
            lifecycle_status="parsed",
            **build_source_pdf_context_patch(stored_job, result_zip_url="https://mineru.net/result.zip"),
        )
        self.assertEqual(updated_job.status, "parsed")
        self.assertEqual(updated_job.read_mineru_result_zip_url(), "https://mineru.net/result.zip")
        self.assertEqual(repository.get_job(job.id).mineru_result_zip_url, "https://mineru.net/result.zip")

        repository.upsert_file(job.id, JobFile(file_type="source_pdf", path="input/source.pdf"))
        repository.upsert_file(job.id, JobFile(file_type="result_docx", path="output/result.docx"))
        repository.upsert_file(job.id, JobFile(file_type="source_pdf", path="input/replaced-source.pdf"))
        files_by_type = {file.file_type: file for file in repository.list_files(job.id)}
        self.assertEqual(set(files_by_type), {"source_pdf", "result_docx"})
        self.assertEqual(files_by_type["source_pdf"].path, "input/replaced-source.pdf")

        repository.append_event(
            job.id,
            JobEvent(
                stage="job_created",
                message="created",
                status="accepted",
                trace_id="trace_1",
            ),
        )
        repository.append_event(
            job.id,
            JobEvent(
                stage="translation_completed",
                message="completed",
                status="succeeded",
                trace_id="trace_2",
            ),
        )
        self.assertEqual(
            [event.stage for event in repository.list_events(job.id)],
            ["job_created", "translation_completed"],
        )

        repository.append_audit_event(
            AuditEvent(
                audit_id="audit_contract",
                actor_id="admin",
                actor_role="admin",
                action="job.retry",
                target_type="job",
                target_id=job.id,
                reason="contract",
                trace_id="trace_audit",
            )
        )
        audit_events = repository.list_audit_events()
        self.assertEqual([event.action for event in audit_events], ["job.retry"])
        self.assertEqual(audit_events[0].reason, "contract")

        document_file = DocumentFileRecord(
            id="file_contract",
            tenant_id="tenant_default",
            company_id="company_default",
            job_id=job.id,
            file_type="source_pdf",
            storage_provider="local_object",
            bucket="local-object",
            object_key="document-files/tenant_default/file_contract/source.pdf",
            original_filename="source.pdf",
            mime_type="application/pdf",
            size_bytes=123,
            checksum_sha256="sha256:contract",
            expires_at=utc_now() + timedelta(days=90),
            created_by="operator",
        )
        repository.create_document_file(document_file)
        self.assertEqual(repository.get_document_file("file_contract").object_key, document_file.object_key)
        updated_document_file = repository.update_document_file(
            "file_contract",
            status="uploaded",
            etag="etag_contract",
        )
        self.assertEqual(updated_document_file.status, "uploaded")
        self.assertEqual(updated_document_file.etag, "etag_contract")
        self.assertEqual(
            [record.id for record in repository.list_document_files()],
            ["file_contract"],
        )

        document_job = DocumentJobRecord(
            id="docjob_contract",
            tenant_id="tenant_default",
            company_id="company_default",
            created_by="operator",
            source_file_id=document_file.id,
            mode="direct_pdf_to_word",
            document_language="auto",
            status="pending",
            stage="uploaded",
            progress=0,
            template_version_id="default",
            timeout_at=utc_now() + timedelta(seconds=1200),
        )
        repository.create_document_job(document_job)
        self.assertEqual(repository.get_document_job(document_job.id).source_file_id, document_file.id)
        updated_document_job = repository.update_document_job(
            document_job.id,
            status="queued",
            stage="uploaded",
            progress=0,
        )
        self.assertEqual(updated_document_job.status, "queued")
        with self.assertRaises(ValidationError):
            repository.update_document_job(document_job.id, status="succeeded", stage="uploaded")
        self.assertEqual([record.id for record in repository.list_document_jobs()], [document_job.id])
        repository.append_document_job_event(
            document_job.id,
            DocumentJobEventRecord(
                id="event_docjob_contract",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id=document_job.id,
                created_by="operator",
                stage="uploaded",
                event_type="job_created",
                message="created",
                trace_id="trace_docjob",
            ),
        )
        document_job_events = repository.list_document_job_events(document_job.id)
        self.assertEqual([event.event_type for event in document_job_events], ["job_created"])
        self.assertEqual(document_job_events[0].trace_id, "trace_docjob")

        pending = JobStageMessage(
            id="msg_pending",
            job_id=job.id,
            stage="convert_package",
            trace_id="trace_stage",
            status="pending",
        )
        running = JobStageMessage(
            id="msg_running",
            job_id=job.id,
            stage="submit_to_mineru",
            trace_id="trace_stage",
            status="running",
        )
        failed = JobStageMessage(
            id="msg_failed",
            job_id=job.id,
            stage="process_callback",
            trace_id="trace_stage",
            status="failed",
        )
        for message in (pending, running, failed):
            repository.put_stage_message(message)

        lease_expires_at = utc_now() + timedelta(seconds=900)
        updated_message = repository.update_stage_message(
            "msg_pending",
            status="running",
            attempts=1,
            lease_owner="in_process",
            leased_at=utc_now(),
            lease_expires_at=lease_expires_at,
        )
        self.assertEqual(updated_message.status, "running")
        self.assertEqual(updated_message.attempts, 1)
        self.assertEqual(updated_message.lease_owner, "in_process")
        self.assertEqual(updated_message.lease_expires_at, lease_expires_at)
        self.assertEqual(
            {message.id for message in repository.list_replayable_stage_messages()},
            {"msg_pending", "msg_running"},
        )
        self.assertEqual(repository.count_stage_messages_by_status(), {"pending": 0, "running": 2, "failed": 1})
        repository.delete_stage_message("msg_running")
        self.assertIsNone(repository.get_stage_message("msg_running"))
        self.assertEqual(repository.count_stage_messages_by_status(), {"pending": 0, "running": 1, "failed": 1})

        query_service = JobQueryService(repository, repository, repository)
        detail_job, detail_files, detail_events = query_service.get_job_detail(job.id)
        listed_jobs, total, summary = query_service.list_jobs(
            page=1,
            page_size=10,
            status_filter="parsed",
            query_text="source",
            sort="updated_at_desc",
        )
        self.assertEqual(detail_job.id, job.id)
        self.assertEqual(len(detail_files), 2)
        self.assertEqual(len(detail_events), 2)
        self.assertEqual(total, 1)
        self.assertEqual([listed_job.id for listed_job in listed_jobs], [job.id])
        self.assertEqual(summary["parsed"], 1)

    def _build_source_pdf_job(self, job_id: str) -> JobRecord:
        return JobRecord(
            id=job_id,
            source_filename="source.pdf",
            status="uploaded",
            source_kind="source_pdf",
            lifecycle_status="uploaded",
            execution_status="idle",
            source_pdf_context=SourcePdfJobContext(batch_id="batch_1", data_id="data_1"),
        )
