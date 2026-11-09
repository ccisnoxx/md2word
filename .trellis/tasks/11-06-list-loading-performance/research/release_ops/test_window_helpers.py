"""窗口辅助的直接离线夹具；不访问生产、数据库或容器。"""
from __future__ import annotations

from contextlib import redirect_stdout
import copy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import window_helpers as helpers
from common import OpsError


class FilesystemManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "source"
        self.root.mkdir()
        (self.root / "private-文件").write_bytes(b"complete\x00content")
        (self.root / "outside-link").symlink_to("/outside/private-secret")
        os.link(self.root / "private-文件", self.root / "hardlink")
        self.attrs = {"user.example": "AAE=", "system.posix_acl_access": "AA=="}
        self.attribute_patch = patch.object(helpers, "_read_xattrs", return_value=self.attrs)
        self.attribute_patch.start()
        self.addCleanup(self.attribute_patch.stop)

    def test_capture_restored_content_metadata_links_and_ignore_atime(self):
        before = helpers.filesystem_manifest(self.root)
        os.utime(self.root / "private-文件", ns=(1, (self.root / "private-文件").stat().st_mtime_ns))
        after = helpers.filesystem_manifest(self.root)
        self.assertEqual(helpers.compare_filesystems(before, after)["exit_code"], 0)
        entry = before["entries"]["private-文件"]
        self.assertEqual(entry["hardlink_to"], "hardlink")
        self.assertEqual(entry["acl"], {"system.posix_acl_access": "AA=="})
        self.assertEqual(before["entries"]["outside-link"]["symlink_target"], "/outside/private-secret")
        self.assertNotIn("atime", json.dumps(before))
        self.assertNotIn(str(self.root), json.dumps(before))
        restored = self.root.parent / "restored"
        shutil.copytree(self.root, restored, symlinks=True)
        (restored / "private-文件").unlink()
        os.link(restored / "hardlink", restored / "private-文件")
        shutil.copystat(self.root, restored)
        self.assertEqual(helpers.compare_filesystems(before, helpers.filesystem_manifest(restored))["exit_code"], 0)

    def test_each_metadata_content_and_entry_change_fails_without_path_output(self):
        before = helpers.filesystem_manifest(self.root)
        for key, value in dict(size=999, mode=0, uid=-1, gid=-1, mtime_ns=0,
                sha256="different", xattrs={}, acl={}, hardlink_to="different").items():
            after = copy.deepcopy(before)
            after["entries"]["private-文件"][key] = value
            after["entries_sha256"] = helpers._digest(after["entries"])
            report = helpers.compare_filesystems(before, after)
            self.assertEqual(report["exit_code"], 1, key)
            self.assertNotIn("private", json.dumps(report))
        (self.root / "private-文件").write_bytes(b"changed\x00content!")
        after = helpers.filesystem_manifest(self.root)
        self.assertEqual(helpers.compare_filesystems(before, after)["exit_code"], 1)
        with self.assertRaises(OpsError):
            helpers.compare_filesystems(before, {**after, "entries_sha256": "corrupt"})

    def test_private_publication_is_exclusive_complete_and_requires_owned_0700(self):
        private = self.root.parent / "evidence"
        private.mkdir(mode=0o700)
        target = private / "manifest.json"
        helpers.write_private_json(target, {"private": "值"})
        self.assertEqual(json.loads(target.read_text()), {"private": "值"})
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            helpers.write_private_json(target, {})
        self.assertEqual(len(list(private.iterdir())), 1)
        private.chmod(0o755)
        with self.assertRaises(OpsError):
            helpers.write_private_json(private / "other.json", {})

    def test_directory_allocation_size_is_diagnostic_but_other_metadata_and_file_size_are_strict(self):
        before = helpers.filesystem_manifest(self.root)
        after = copy.deepcopy(before)
        after["entries"]["."]["size"] += 4096
        after["entries_sha256"] = helpers._digest(after["entries"])
        unchanged_inputs = copy.deepcopy((before, after))
        self.assertEqual(helpers.compare_filesystems(before, after)["exit_code"], 0)
        self.assertEqual((before, after), unchanged_inputs)
        for field, value in dict(type="file", mode=0, uid=-1, gid=-1, mtime_ns=0,
                                xattrs={}, acl={}).items():
            changed = copy.deepcopy(after)
            changed["entries"]["."][field] = value
            changed["entries_sha256"] = helpers._digest(changed["entries"])
            self.assertEqual(helpers.compare_filesystems(before, changed)["exit_code"], 1, field)
        after["entries"]["private-文件"]["size"] += 1
        after["entries_sha256"] = helpers._digest(after["entries"])
        report = helpers.compare_filesystems(before, after)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["changed"], 1)

    def test_cli_prints_only_counts_and_digest(self):
        output = self.root.parent / "manifest.json"
        os.chmod(output.parent, 0o700)
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["window_helpers.py", "filesystem-capture", "--root",
                str(self.root), "--output", str(output)]), redirect_stdout(stdout):
            self.assertEqual(helpers.main(), 0)
        self.assertNotIn("private", stdout.getvalue())
        self.assertNotIn(str(self.root), stdout.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())["files"], 2)

    def test_linux_acl_and_xattr_boundary_reads_raw_bytes_without_following_links(self):
        self.attribute_patch.stop()
        with patch.object(helpers.sys, "platform", "linux"), \
                patch.object(os, "listxattr", return_value=["user.value", "system.posix_acl_access"], create=True) as names, \
                patch.object(os, "getxattr", return_value=b"\x00\xff", create=True) as values:
            attrs = helpers._read_xattrs(self.root / "outside-link")
        self.assertEqual(attrs, {"user.value": "AP8=", "system.posix_acl_access": "AP8="})
        self.assertFalse(names.call_args.kwargs["follow_symlinks"])
        self.assertTrue(all(not call.kwargs["follow_symlinks"] for call in values.call_args_list))


class MatrixConnection:
    def __init__(self, users, jobs):
        self.users, self.jobs = users, jobs
        self.statements = []
        self.rows = []
        self.closed, self.rolled_back = False, False

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, params=()):
        self.statements.append((statement, params))
        self.rows = self.users if "FROM internal_users" in statement else self.jobs

    def fetchall(self):
        return self.rows

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class QueryMatrixTests(unittest.TestCase):
    def setUp(self):
        from app.domains.document_jobs.models import DocumentJobRecord
        from app.domains.users.models import InternalUserRecord
        self.instant = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)
        self.users = [InternalUserRecord(id=identity, username=identity, password_hash="fixture-only",
            role=role, tenant_id=tenant, company_id="company", created_at=self.instant, updated_at=self.instant)
            for identity, role, tenant in (("admin-private", "admin", "tenant"),
                ("operator-private", "operator", "tenant"), ("other-admin", "admin", "other"))]
        self.jobs = [DocumentJobRecord(id=f"job-private-{number:03}", tenant_id="tenant", company_id="company",
            created_by="operator-private", source_file_id="source-private", template_version_id="fixture",
            status="failed" if number % 2 else "succeeded", stage="failed" if number % 2 else "completed",
            created_at=self.instant,
            updated_at=self.instant, request_snapshot={"source_file": {"original_filename": "中文-文档.pdf"}})
            for number in range(41)]
        self.jobs.extend([self.jobs[0].model_copy(update=dict(id="other-owner", created_by="other-owner")),
            self.jobs[0].model_copy(update=dict(id="other-company", company_id="other")),
            self.jobs[0].model_copy(update=dict(id="deleted", deleted_at=self.instant)),
            self.jobs[0].model_copy(update=dict(id="archived", archived_at=self.instant))])

    def test_all_actual_users_scope_bound_pages_sorts_status_qa_and_dates(self):
        from app.domains.document_jobs.schemas import DocumentJobIncidentSort
        from typing import get_args
        cases, summary = helpers.build_case_matrix(self.users, self.jobs)
        self.assertEqual(summary["users"], 3)
        self.assertEqual(summary["users_without_visible_jobs"], 1)
        self.assertEqual(summary["representatives_without_unicode_samples"], 1)
        self.assertNotIn("private", json.dumps(summary))
        for user in self.users:
            for endpoint in ("jobs", "incidents"):
                selected = [case for case in cases if case["user_id"] == user.id and case["endpoint"] == endpoint]
                self.assertTrue(any(case["params"] == {} for case in selected))
                pages = [case["params"]["page"] for case in selected if case["label"] == "all_default_pages"]
                self.assertEqual(pages, [] if user.id == "other-admin" else [2, 3])
                out = [case for case in selected if case["label"] == "out_of_range_empty_page"]
                self.assertEqual(out[0]["params"]["page"], max([1, *pages]) + 1)
                statuses = {case["params"]["status_filter"] for case in selected if case["label"] == "actual_status"}
                self.assertEqual(statuses, set() if user.id == "other-admin" else {"failed", "succeeded"})
                sorts = {case["params"]["sort"] for case in selected if case["label"] == "sort"}
                self.assertEqual(sorts, set(get_args(DocumentJobIncidentSort)) - {"priority"} if endpoint == "incidents" else
                    {"created_at_asc", "updated_at_asc", "updated_at_desc"})
        selected = [case for case in cases if case["user_id"] == "operator-private"]
        qa = {case["params"]["translation_qa_status"] for case in selected if case["label"] == "translation_qa"}
        self.assertEqual(qa, {"unreviewed", "approved", "needs_fix", "blocked", "all"})
        for case in cases:
            if case["label"] == "inclusive_date_boundary":
                params = case["params"]
                if "created_from" in params and "created_to" in params:
                    self.assertLessEqual(datetime.fromisoformat(params["created_from"]),
                                         datetime.fromisoformat(params["created_to"]))
        with self.assertRaisesRegex(OpsError, "actual_admin_and_operator_required"):
            helpers.build_case_matrix(self.users[:1], self.jobs)

    def test_extra_filters_use_one_representative_per_role_tenant_company(self):
        extra = self.users[1].model_copy(update=dict(id="empty-operator", username="empty-operator"))
        cases, summary = helpers.build_case_matrix([extra, *self.users], self.jobs)
        self.assertEqual(summary["users"], 4)
        self.assertEqual(summary["extra_dimension_representatives"], 3)
        selected = [case for case in cases if case["user_id"] == "empty-operator"]
        self.assertEqual(len(selected), 6)
        self.assertEqual({case["label"] for case in selected}, {"default", "out_of_range_empty_page", "no_match"})
        self.assertEqual(summary["dimension_cases"]["default"], 8)

    def test_loader_is_readonly_snapshot_checks_primary_keys_and_always_closes(self):
        user_rows = [dict(user_id=user.id, payload=user.model_dump_json()) for user in self.users]
        job_rows = [dict(job_id=job.id, payload=job.model_dump_json()) for job in self.jobs]
        connection = MatrixConnection(user_rows, job_rows)
        users, jobs = helpers.load_matrix_records(lambda: connection)
        self.assertEqual([user.id for user in users], [user.id for user in self.users])
        self.assertEqual(len(jobs), len(self.jobs))
        self.assertTrue(connection.rolled_back and connection.closed)
        self.assertTrue(all(statement.startswith(("SELECT ", "START TRANSACTION "))
                            for statement, _ in connection.statements))
        self.assertEqual(connection.statements[1][1], ("active", "admin", "operator"))
        job_rows[0]["job_id"] = "mismatched-id"
        failed = MatrixConnection(user_rows, job_rows)
        with self.assertRaisesRegex(OpsError, "actual_job_identity_mismatch"):
            helpers.load_matrix_records(lambda: failed)
        self.assertTrue(failed.rolled_back and failed.closed)

    def test_cli_denies_production_before_environment_or_connection_and_saves_only_private_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            arguments = ["window_helpers.py", "query-cases", "--expect-database", "restored",
                "--expect-server-uuid", "production", "--deny-server-uuid", "production",
                "--output", str(root / "cases.json")]
            with patch.object(sys, "argv", arguments), patch.object(helpers, "mysql_environment") as env:
                with self.assertRaisesRegex(OpsError, "production_instance_forbidden"):
                    helpers.main()
                env.assert_not_called()
            arguments[5] = "restored-uuid"
            output = io.StringIO()
            with patch.object(sys, "argv", arguments), \
                    patch.object(helpers, "mysql_environment", return_value={}), \
                    patch.object(helpers, "connection_factory") as factory, \
                    patch.object(helpers, "load_matrix_records", return_value=(self.users, self.jobs)), \
                    redirect_stdout(output):
                self.assertEqual(helpers.main(), 0)
            factory.assert_called_once_with({}, "restored", "restored-uuid", readonly=True)
            self.assertNotIn("private", output.getvalue())
            self.assertNotIn("中文", output.getvalue())
            cases = json.loads((root / "cases.json").read_text())
            self.assertEqual(json.loads(output.getvalue())["cases"], len(cases))
            self.assertEqual(stat.S_IMODE((root / "cases.json").stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
