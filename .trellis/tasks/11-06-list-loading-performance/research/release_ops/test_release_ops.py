"""仅验证运维载体本身；不连接数据库、不运行产品测试或容器。"""
from __future__ import annotations

from contextlib import redirect_stdout
import copy
import io
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import migrate
import query_diff
import snapshot


class Connection:
    def __init__(self, *, uuid="restore", readonly=True, tables=None):
        self.uuid, self.readonly, self.tables = uuid, readonly, tables
        self.statements, self.rows = [], []
        self.closed, self.rollbacks = False, 0

    def cursor(self, *args):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, params=()):
        self.statements.append(statement)
        if statement.startswith("SELECT DATABASE()"):
            self.rows = [{"db": "restored", "uuid": self.uuid}]
        elif statement.startswith("SELECT @@session"):
            self.rows = [{"ro": int(self.readonly), "isolation_level": "REPEATABLE-READ",
                          "row_wait": 10, "ddl_wait": 10}]
        elif "INFORMATION_SCHEMA.TABLES" in statement:
            self.rows = [{"name": name, "kind": "BASE TABLE", "engine": "InnoDB"} for name in self.tables]
        elif "INFORMATION_SCHEMA.COLUMNS" in statement:
            self.rows = self.tables[params[0]]["columns"]
        elif statement.startswith("SHOW CREATE TABLE"):
            self.rows = [{"Create Table": self.tables[statement.split("`")[1]]["ddl"]}]
        elif statement.startswith("SELECT CAST("):
            table = statement.rsplit("`", 2)[1]
            names = set(re.findall(r"AS BINARY\) AS `([^`]+)`", statement))
            self.rows = [{key: value for key, value in row.items() if key in names}
                         for row in self.tables[table]["rows"]]
        elif "INFORMATION_SCHEMA.SCHEMATA" in statement:
            self.rows = [{"DEFAULT_CHARACTER_SET_NAME": "utf8mb4", "DEFAULT_COLLATION_NAME": "utf8mb4_0900_ai_ci"}]
        else:
            self.rows = []

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows

    def fetchmany(self, size):
        rows, self.rows = self.rows[:size], self.rows[size:]
        return rows

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def tables():
    result = {}
    for name in ("document_jobs", "document_files", "audit_events"):
        names = ["payload", "created_at"]
        if name in snapshot.PROJECTIONS:
            names.append(snapshot.PROJECTIONS[name])
        columns = [dict(name=key, type="longtext", data_type="longtext", nullable="YES",
                        default_value=None, extra="", generation="", charset="utf8mb4",
                        collation="utf8mb4_0900_ai_ci", comment="", position=index + 1)
                   for index, key in enumerate(names)]
        result[name] = {"columns": columns, "ddl": "CREATE TABLE `" + name + "` (\n"
            + ",\n".join("  `" + key + "` longtext" for key in names) + "\n) ENGINE=InnoDB",
            "rows": [dict.fromkeys(names, b"{\"original\": 1}"), dict.fromkeys(names, b"{\"original\": 1}")]}
    return result


class ReleaseOpsTests(unittest.TestCase):
    def test_each_connection_binds_actual_target_before_return(self):
        first, second = Connection(), Connection(uuid="wrong")
        factory = common.connection_factory(dict(database="restored"), "restored", "restore",
            readonly=True, connector=unittest.mock.Mock(side_effect=[first, second]))
        self.assertIs(factory(), first)
        with self.assertRaisesRegex(common.OpsError, "database_identity_mismatch"):
            factory()
        self.assertTrue(second.closed)
        self.assertEqual(len(second.statements), 1)
        self.assertEqual(first.rollbacks, 1)

    def test_session_protection_must_actually_take_effect(self):
        connection = Connection(readonly=False)
        factory = common.connection_factory(dict(database="restored"), "restored", "restore",
            readonly=True, connector=lambda **kw: connection)
        with self.assertRaisesRegex(common.OpsError, "session_protection_not_effective"):
            factory()
        self.assertTrue(connection.closed)

    def test_explicit_environment_and_secret_safe_failure(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(common.OpsError):
                common.mysql_environment()
        output = io.StringIO()
        with redirect_stdout(output):
            code = common.safe_main(lambda: (_ for _ in ()).throw(ValueError("secret payload")))
        self.assertEqual(code, 1)
        self.assertNotIn("secret", output.getvalue())

    def test_migration_forwards_cursors_and_original_report(self):
        report = {"exit_code": 7, "tables": {"document_files": {"last_successful_file_id": "cursor"}}}
        values = dict(host="isolated", port=3306, user="fixture", password="fixture", database="restored")
        output = io.StringIO()
        with patch.object(sys, "argv", ["migrate.py", "--expect-database", "restored", "--expect-server-uuid",
                "restore", "--apply", "--batch-size", "12", "--after-file-id", "f", "--after-job-id", "j"]), \
                patch.object(migrate, "mysql_environment", return_value=values), \
                patch("scripts.ops.migrate_document_job_list_query.migrate_document_job_list_query", return_value=report) as owner, \
                redirect_stdout(output):
            self.assertEqual(migrate.main(), 7)
        self.assertEqual(json.loads(output.getvalue()), report)
        self.assertEqual(owner.call_args.kwargs["after_file_id"], "f")
        self.assertEqual(owner.call_args.kwargs["after_job_id"], "j")
        self.assertEqual(owner.call_args.kwargs["batch_size"], 12)
        self.assertEqual(owner.call_args.kwargs["mode"], "apply")

    def test_encoding_preserves_null_type_length_order_and_duplicates(self):
        encode = snapshot.row_digest
        self.assertNotEqual(encode(["text"], [None]), encode(["text"], [b""]))
        self.assertNotEqual(encode(["text"], [b"1"]), encode(["int"], [b"1"]))
        self.assertNotEqual(encode(["text", "text"], [b"ab", b"c"]),
                            encode(["text", "text"], [b"a", b"bc"]))
        a, b = encode(["text"], [b"a "]), encode(["text"], [b"a"])
        self.assertNotEqual(a, b)
        self.assertEqual(snapshot.multiset_digest([a, b, a]), snapshot.multiset_digest([a, a, b]))
        self.assertNotEqual(snapshot.multiset_digest([a, b, a]), snapshot.multiset_digest([a, b]))

    def test_full_snapshot_allows_only_projection_and_new_keys(self):
        before_tables = tables()
        after_tables = copy.deepcopy(before_tables)
        for name, keys in snapshot.KEYS.items():
            table = after_tables[name]
            for key in sorted(keys):
                column = {**table["columns"][0], "name": key, "position": len(table["columns"]) + 1}
                table["columns"].append(column)
                table["ddl"] = table["ddl"].replace("\n) ENGINE", ",\n  `" + key + "` longtext\n) ENGINE")
            for row in table["rows"]:
                row[snapshot.PROJECTIONS[name]] = b"new projection"
                row.update(dict.fromkeys(keys, b"new full key"))
        before = snapshot.snapshot(Connection(tables=before_tables))
        after = snapshot.snapshot(Connection(tables=after_tables))
        self.assertEqual(snapshot.compare(before, after, require_new_keys=True)["exit_code"], 0)
        self.assertEqual(before["tables"]["audit_events"]["rows"], 2)
        self.assertNotIn('{"original": 1}', json.dumps(before))
        after_tables["audit_events"]["rows"].pop()
        changed = snapshot.snapshot(Connection(tables=after_tables))
        self.assertEqual(snapshot.compare(before, changed, require_new_keys=True)["changed_structure_or_tables"], ["audit_events"])

    def test_schema_and_original_payload_changes_fail(self):
        original = tables()
        before = snapshot.snapshot(Connection(tables=original))
        for modification in ("payload", "schema", "inventory"):
            changed = copy.deepcopy(original)
            if modification == "payload":
                changed["document_jobs"]["rows"][0]["payload"] += b" "
            elif modification == "schema":
                changed["document_jobs"]["ddl"] += " ROW_FORMAT=COMPRESSED"
            else:
                del changed["audit_events"]
            after = snapshot.snapshot(Connection(tables=changed))
            self.assertEqual(snapshot.compare(before, after, require_new_keys=False)["exit_code"], 1)
        self.assertEqual(snapshot.compare(before, before, require_new_keys=True)["exit_code"], 1)

    def test_restore_snapshot_includes_derived_values_and_rejects_scope_mix(self):
        original = tables()
        before = snapshot.snapshot(Connection(tables=original), include_derived=True)
        original["document_jobs"]["rows"][0]["list_query_json"] = b"different projection"
        after = snapshot.snapshot(Connection(tables=original), include_derived=True)
        self.assertEqual(snapshot.compare(before, after, require_new_keys=False)["exit_code"], 1)
        partial = snapshot.snapshot(Connection(tables=original))
        with self.assertRaisesRegex(common.OpsError, "snapshot_scope_mismatch"):
            snapshot.compare(before, partial, require_new_keys=False)

    def test_real_read_runtime_constructs_without_db_bootstrap(self):
        from app.core.config import Settings
        backend = unittest.mock.Mock()
        backend.connect.side_effect = AssertionError("构造服务不应读取或初始化数据库")
        runtime = query_diff.build_read_runtime(Settings(_env_file=None, document_jobs_worker_backend="celery"), backend)
        service = runtime.document_job_service
        self.assertIs(service.job_repository.backend, backend)
        self.assertIs(service.file_upload_service.repository, service.file_repository)
        self.assertIsNotNone(service.job_resource_snapshot_service)
        self.assertIsNotNone(service.word_preview_service)
        self.assertTrue(callable(service.job_repository.list_document_job_publications))
        backend.connect.assert_not_called()

    def test_fixed_clock_requires_aware_time_and_restores_owners(self):
        from app.domains.document_jobs import service
        original = service.utc_now
        instant = query_diff.aware_time("2026-11-07T12:00:00+08:00")
        with query_diff.frozen_clock(instant):
            self.assertEqual(service.utc_now(), instant)
        self.assertIs(service.utc_now, original)
        with self.assertRaises(common.OpsError):
            query_diff.aware_time("2026-11-07T12:00:00")

    def test_router_compare_requires_complete_success_and_identical_full_digest(self):
        report = dict(exit_code=0, format="md2word-router-diff-v1", as_of="fixed", matrix_sha256="matrix",
                      cases=[dict(response_sha256="full", total=1, items=1)])
        self.assertEqual(query_diff.compare(report, report)["exit_code"], 0)
        changed = copy.deepcopy(report)
        changed["cases"][0]["response_sha256"] = "different_action"
        self.assertEqual(query_diff.compare(report, changed)["exit_code"], 1)
        with self.assertRaises(common.OpsError):
            query_diff.compare(dict(exit_code=1), dict(exit_code=1))
        with self.assertRaises(common.OpsError):
            query_diff.compare({**report, "cases": []}, {**report, "cases": []})

    def test_io_guard_blocks_write_external_network_and_process(self):
        # 审计 hook 不可卸载，因此在仅本地的短进程验证，不污染 unittest 进程。
        source = """
import socket, subprocess
from query_diff import install_io_guard
from common import OpsError
denied = install_io_guard('127.0.0.1', 3306)
for operation in (lambda: open('/tmp/md2word-release-ops-forbidden', 'w'),
                  lambda: socket.socket().connect(('127.0.0.1', 3307)),
                  lambda: subprocess.run(['true'])):
    try:
        operation()
    except OpsError:
        pass
    else:
        raise AssertionError('保护未生效')
assert len(denied) == 3
"""
        result = subprocess.run([sys.executable, "-B", "-c", source],
            cwd=Path(__file__).resolve().parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
