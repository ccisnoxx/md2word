from __future__ import annotations

# 正式 DocumentFile 保留期计划只标记过期，不删除对象。

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.domains.files.models import DocumentFileRecord
from app.domains.files.retention import DocumentFileRetentionPlanner
from app.infrastructure.persistence import build_file_persistence_adapters

class DocumentFileRetentionTests(TestCase):
    def test_document_file_retention_plan_marks_expired_without_deleting_objects(self):
        now = datetime(2026, 5, 28, tzinfo=timezone.utc)
        with TemporaryDirectory() as temp_dir:
            adapters = build_file_persistence_adapters(Path(temp_dir))
            old_file = DocumentFileRecord(
                id="file_old",
                tenant_id="tenant_default",
                company_id="company_default",
                job_id="docjob_old",
                file_type="generated_word",
                storage_provider="local_object",
                bucket="local-object",
                object_key="document-jobs/tenant_default/docjob_old/generated_word/file_old/result.docx",
                original_filename="result.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=10,
                status="uploaded",
                expires_at=now - timedelta(seconds=1),
                created_by="operator",
            )
            recent_file = old_file.model_copy(
                update={
                    "id": "file_recent",
                    "job_id": "docjob_recent",
                    "object_key": "document-jobs/tenant_default/docjob_recent/generated_word/file_recent/result.docx",
                    "expires_at": now + timedelta(days=1),
                }
            )
            adapters.document_file_repository.create_document_file(old_file)
            adapters.document_file_repository.create_document_file(recent_file)

            planner = DocumentFileRetentionPlanner(adapters.document_file_repository, retention_days=90)
            plan = planner.build_plan(now=now)
            marked_plan = planner.mark_expired(now=now)
            old_after_mark = adapters.document_file_repository.get_document_file("file_old")
            recent_after_mark = adapters.document_file_repository.get_document_file("file_recent")

        self.assertEqual(plan.totals["files_seen"], 2)
        self.assertEqual(plan.totals["files_with_expires_at"], 2)
        self.assertEqual(plan.totals["candidate_files"], 1)
        self.assertEqual(plan.totals["candidate_local_files"], 1)
        self.assertEqual(plan.candidates[0].file_id, "file_old")
        self.assertEqual(marked_plan.candidates[0].object_key, old_file.object_key)
        self.assertEqual(old_after_mark.status, "expired")
        self.assertEqual(recent_after_mark.status, "uploaded")
