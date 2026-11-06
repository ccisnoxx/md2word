"""冻结异常旧路径完整对照；真实 MySQL 计时不注入人工建连延迟。"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import pymysql
from app.core.config import Settings
from app.domains.document_jobs import service as current_service, incidents as current_incidents
from app.domains.document_jobs.base_quality import BaseQualityContribution, DegradedPageSummary
from app.infrastructure.persistence.mysql import backend as current_backend, files as current_files
from app.infrastructure.persistence.mysql.document_jobs import MysqlDocumentJobRepository
from app.infrastructure.persistence.mysql.schema import MYSQL_SCHEMA_STATEMENTS
from tests import test_document_job_list_query_v2_service as fixtures
from tests.test_document_job_incident_publish_light_check import query_values
from tests.test_document_job_list_query_v2_mysql import _temporary_schema


def frozen_modules():
    directory = Path(__file__).with_name("data") / "incident-source-freeze"
    manifest = json.loads((directory / "manifest.json").read_text())
    for path, expected in manifest["files"].items():
        assert hashlib.sha256((directory / "files" / path).read_bytes()).hexdigest() == expected
    modules = {}
    for label, path in (
        ("service", "app/domains/document_jobs/service.py"),
        ("incidents", "app/domains/document_jobs/incidents.py"),
        ("backend", "app/infrastructure/persistence/mysql/backend.py"),
        ("files", "app/infrastructure/persistence/mysql/files.py"),
    ):
        spec = importlib.util.spec_from_file_location("frozen_incident_" + label, directory / "files" / path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules[label] = module
    return modules, manifest


class TimedCursor:
    def __init__(self, cursor, measurements):
        self.cursor, self.measurements = cursor, measurements

    def __enter__(self):
        self.cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self.cursor.__exit__(*args)

    def execute(self, sql, params=()):
        if sql.startswith("SELECT payload FROM document_files WHERE"):
            self.measurements["file_gets"] += 1
        elif sql.startswith("SELECT protected_file_ids"):
            self.measurements["protection_reads"] += 1
        started = perf_counter()
        try:
            return self.cursor.execute(sql, params)
        finally:
            self.measurements["execute_seconds"] += perf_counter() - started

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


class TimedConnection:
    def __init__(self, connection, measurements):
        self.connection, self.measurements = connection, measurements

    def cursor(self):
        return TimedCursor(self.connection.cursor(), self.measurements)

    def commit(self):
        self.measurements["commits"] += 1
        self.connection.commit()

    def rollback(self):
        self.measurements["rollbacks"] += 1
        self.connection.rollback()

    def close(self):
        self.measurements["closes"] += 1
        self.connection.close()


def measure(modules, config, options, schema, query):
    measurements = dict(file_gets=0, protection_reads=0, connections=0, commits=0,
                        rollbacks=0, closes=0, connect_seconds=0.0, execute_seconds=0.0,
                        visible_seconds=0.0, classification_seconds=0.0, page_actions_seconds=0.0)
    def connect():
        started = perf_counter()
        connection = pymysql.connect(**options, database=schema, autocommit=False)
        measurements["connect_seconds"] += perf_counter() - started
        measurements["connections"] += 1
        return TimedConnection(connection, measurements)
    backend = modules["backend"].MysqlPersistenceBackend(config, initialize=False, connect_factory=connect)
    files = modules["files"].MysqlDocumentFileRepository(backend)
    jobs = MysqlDocumentJobRepository(backend)
    service = modules["service"].DocumentJobService(Settings.model_construct(document_publication_enabled=False),
        jobs, SimpleNamespace(), files)
    incidents = modules["incidents"].DocumentJobIncidentService(service)
    def timed(method, key):
        def call(*args, **kwargs):
            started = perf_counter()
            before = {field: measurements[field] for field in ("file_gets", "protection_reads", "connections")}
            try:
                return method(*args, **kwargs)
            finally:
                measurements[key] += perf_counter() - started
                for field, value in before.items():
                    stage_key = key.removesuffix("_seconds") + "_" + field
                    measurements[stage_key] = measurements.get(stage_key, 0) + measurements[field] - value
        return call
    with ExitStack() as stack:
        stack.enter_context(patch.object(modules["service"], "utc_now", return_value=fixtures.NOW))
        stack.enter_context(patch.object(modules["incidents"], "utc_now", return_value=fixtures.NOW))
        for method, key in (("list_visible_jobs", "visible_seconds"),
                            ("build_incident_classification_view", "classification_seconds"),
                            ("build_job_read_view", "page_actions_seconds")):
            stack.enter_context(patch.object(service, method, timed(getattr(service, method), key)))
        started = perf_counter()
        try:
            result = incidents.list_incidents(**query).model_dump(mode="json")
            outcome = ("response", result)
        except Exception as error:
            # 差分必须同时失败且类型/消息一致；不能将失败当成成功性能样本。
            outcome = ("error", type(error).__name__, str(error))
        measurements["total_seconds"] = perf_counter() - started
    measurements["outcome_sha256"] = hashlib.sha256(json.dumps(outcome, sort_keys=True,
        ensure_ascii=False).encode()).hexdigest()
    measurements["outcome_type"] = outcome[0]
    if outcome[0] == "response":
        measurements["total_items"] = outcome[1]["total"]
        measurements["page_items"] = len(outcome[1]["items"])
    return outcome, measurements


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old, manifest = frozen_modules()
    current = dict(service=current_service, incidents=current_incidents, backend=current_backend, files=current_files)
    report = dict(synthetic_only=True, artificial_delay_seconds=0, as_of=fixtures.NOW.isoformat(),
                  frozen=manifest, candidate_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                                                    for p in manifest["files"]}, comparisons={})
    with _temporary_schema(json.loads(args.credentials.read_text())) as (options, schema):
        report["temporary_schema"] = schema
        config = current_backend.MysqlPersistenceConfig(options["host"], options["port"], options["user"],
                                                       options["password"], schema)
        backend = current_backend.MysqlPersistenceBackend(config, initialize=False,
            connect_factory=lambda: pymysql.connect(**options, database=schema, autocommit=False))
        jobs = MysqlDocumentJobRepository(backend)
        files = current_files.MysqlDocumentFileRepository(backend)
        with backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute(next(sql for sql in MYSQL_SCHEMA_STATEMENTS
                if sql.strip().startswith("CREATE TABLE IF NOT EXISTS document_job_publications (")))
            cursor.execute("SELECT VERSION() AS version, @@server_uuid AS server_uuid, @@transaction_isolation AS isolation")
            report["engine"] = cursor.fetchone()
            assert report["engine"]["isolation"] == "REPEATABLE-READ"
            for index in range(1928):
                record = fixtures.make_file(f"job-{index:04}", f"file-{index:04}", metadata={"synthetic": "x" * 3500})
                if index < 24:
                    record = record.model_copy(update={"expires_at": fixtures.NOW - timedelta(days=1)})
                files._write_file(connection, record, create=True)
        degraded = BaseQualityContribution(generation=0, degraded_pages=[
            DegradedPageSummary(page_number=2, trigger="render", reason_codes=["render_failed"])]).model_dump(mode="json")
        for index in range(119):
            if index < 68:
                record = fixtures.make_job(f"job-{index:04}", status="succeeded", stage="completed",
                    result_file_id=f"file-{index:04}", quality_status="passed",
                    quality_summary={"checks_v1": {"document_base": degraded}} if index < 8 else {})
            else:
                record = fixtures.make_job(f"job-{index:04}", status="failed", stage="failed",
                                          failed_stage="rendering", error_code="render_failed")
                if index >= 74:
                    record = record.model_copy(update={"tenant_id": "hidden"})
            jobs.create_document_job(record)
        report["fixture"] = dict(jobs=119, files=1928, visible_jobs=74, completed=68,
                                 expired=24, failed=6, degraded=8, verified_binding=0)
        requests = {"default_admin": query_values(fixtures.ADMIN, page_size=20),
                    "default_operator": query_values(fixtures.USER, page_size=20),
                    "page_2": query_values(page=2, page_size=3),
                    "empty_page": query_values(page=99), "no_match": query_values(q="absent-token")}
        for name, query in requests.items():
            samples = {"old": [], "session": []}
            for round_index in range(4 if name == "default_admin" else 1):
                pair = {}
                order = (("old", old), ("session", current))
                if round_index % 2:
                    order = tuple(reversed(order))
                for label, modules in order:
                    pair[label], timing = measure(modules, config, options, schema, query)
                    assert pair[label][0] == "response", "正常差分样本失败"
                    assert timing["classification_file_gets"] == 68 and timing["classification_protection_reads"] == 24
                    assert timing["classification_connections"] == (92 if label == "old" else 1)
                    # 页内 clone 动作另读源文件，保持原路径；不能并入分类读取的计数。
                    page_reads = timing.get("page_actions_file_gets", 0)
                    assert timing["connections"] == (93 if label == "old" else 2) + page_reads
                    assert timing["commits"] == 93 + page_reads and timing["closes"] == timing["connections"]
                    samples[label].append(timing)
                assert pair["old"] == pair["session"], "冻结旧异常响应与候选不等价"
            report["comparisons"][name] = dict(full_response_equal=True, samples=samples)
            if name == "default_admin":
                report["comparisons"][name]["warmed_median_seconds"] = {
                    label: median(row["total_seconds"] for row in values[1:]) for label, values in samples.items()}
            print(json.dumps({"case": name, "equal": True,
                              "first_seconds": {label: values[0]["total_seconds"] for label, values in samples.items()}}), flush=True)
        # 损坏边界只在合成 UUID 库注入，逐项恢复同一 payload。
        with backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM document_files WHERE file_id='file-0000'")
            original = cursor.fetchone()["payload"]
        broken_id = json.loads(original)
        broken_id["id"] = "wrong-id"
        naive = json.loads(original)
        naive["expires_at"] = fixtures.NOW.replace(tzinfo=None).isoformat()
        for name, payload in (("bad_json", "{broken"), ("bad_model", "{}"),
                              ("wrong_id", json.dumps(broken_id)), ("naive_expiry", json.dumps(naive))):
            with backend.connect() as connection, connection.cursor() as cursor:
                cursor.execute("UPDATE document_files SET payload=%s WHERE file_id='file-0000'", (payload,))
            pair = {label: measure(modules, config, options, schema, requests["default_admin"])
                    for label, modules in (("old", old), ("session", current))}
            assert pair["old"][0] == pair["session"][0] and pair["old"][0][0] == "error", "错误边界差分不等价"
            report["comparisons"][name] = dict(error_equal=True, samples={label: value[1] for label, value in pair.items()})
        with backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE document_files SET payload=%s WHERE file_id='file-0000'", (original,))
    with pymysql.connect(**options, autocommit=True) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=%s", (schema,))
        report["schema_removed"] = cursor.fetchone()["n"] == 0
    assert report["schema_removed"], "本次合成 UUID 库未清理"
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"schema_removed": True, "default_medians":
                      report["comparisons"]["default_admin"]["warmed_median_seconds"]}))


if __name__ == "__main__":
    main()
