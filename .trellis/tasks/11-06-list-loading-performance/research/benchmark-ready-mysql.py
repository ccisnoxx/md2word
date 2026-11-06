"""在独立 UUID 库比较冻结旧 SQL 与 ready 候选；只输出合成数据摘要。"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from statistics import median
import subprocess
import sys
from time import perf_counter
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import pymysql

from app.domains.document_jobs.list_query import DocumentJobListQuery
from app.infrastructure.persistence import document_job_list_query as candidate
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.document_jobs import MysqlDocumentJobRepository
from app.infrastructure.persistence.mysql.files import MysqlDocumentFileRepository
from tests.test_document_job_list_query_v2 import NOW, bound_job, word
from tests.test_document_job_list_query_v2_mysql import _temporary_schema

BASELINE = "25860865812ef5bb9159a449aaa7df0a6dfcb815"
SQL_PATH = "app/infrastructure/persistence/document_job_list_query.py"


def fingerprint(result):
    """完整结果仅在内存序列化，落盘只保留摘要。"""
    data = json.dumps(asdict(result), default=lambda value: value.model_dump(mode="json"),
                      ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def measure(module, connection, query):
    rows = []
    original = module._ListSql

    class TimedSql(original):
        def read(self, statement, params=()):
            started = perf_counter()
            result = super().read(statement, params)
            rows.append({"ordinal": len(rows), "seconds": perf_counter() - started,
                         "rows": len(result), "sql_sha256": hashlib.sha256(statement.encode()).hexdigest()})
            return result

    with patch.object(module, "_ListSql", TimedSql):
        started = perf_counter()
        result = module.query_document_jobs_sql(connection, query, mysql=True)
        elapsed = perf_counter() - started
    return result, {"total_seconds": elapsed, "select_seconds": sum(row["seconds"] for row in rows),
                    "select_count": len(rows), "selects": rows, "result_sha256": fingerprint(result),
                    "total_items": result.total, "page_items": len(result.items)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    environ = json.loads(args.credentials.read_text())
    old_source = subprocess.check_output(["git", "show", f"{BASELINE}:{SQL_PATH}"], cwd=ROOT)
    old = ModuleType("frozen_document_job_list_query")
    exec(compile(old_source, f"{BASELINE}:{SQL_PATH}", "exec"), old.__dict__)
    report = {"baseline_commit": BASELINE, "baseline_sql_sha256": hashlib.sha256(old_source).hexdigest(),
              "candidate_sql_sha256": hashlib.sha256((ROOT / SQL_PATH).read_bytes()).hexdigest(),
              "as_of": NOW.isoformat(), "synthetic_only": True, "production_version": "8.4.9",
              "fixture": {"jobs": 119, "files": 1928, "receipt_metadata_chars": 35000,
                          "current_metadata_chars": 3500}, "requests": {}}
    with _temporary_schema(environ) as (options, schema):
        report["temporary_schema"] = schema
        backend = MysqlPersistenceBackend(MysqlPersistenceConfig(
            host=options["host"], port=options["port"], user=options["user"],
            password=options["password"], database=schema), initialize=False)
        files = MysqlDocumentFileRepository(backend)
        jobs = MysqlDocumentJobRepository(backend)
        # 保持既有 SQLite 实验的两种 metadata 体积；所有 119 个任务均可见并关联结果。
        with backend.connect() as connection:
            for index in range(1928):
                file = word(f"word-{index:04d}", f"job-{index:04d}", metadata={"synthetic": "x" * 3500})
                files._write_file(connection, file, create=True)
        for index in range(119):
            embedded = word(f"word-{index:04d}", f"job-{index:04d}", metadata={"synthetic": "x" * 35000})
            jobs.create_document_job(bound_job(embedded, receipt=True))
        with pymysql.connect(**options, database=schema, autocommit=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT VERSION() AS version, @@server_uuid AS server_uuid, "
                               "@@transaction_isolation AS isolation")
                report["engine"] = cursor.fetchone()
                report["projection_bytes"] = {}
                for table, column in (("document_jobs", "list_query_json"), ("document_files", "review_query_json")):
                    cursor.execute(f"SELECT COUNT(*) AS n, AVG(OCTET_LENGTH({column})) AS mean_bytes, "
                                   f"MAX(OCTET_LENGTH({column})) AS max_bytes FROM {table}")
                    facts = cursor.fetchone()
                    facts["mean_bytes"] = float(facts["mean_bytes"])
                    report["projection_bytes"][table] = facts
                connection.rollback()
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            base_query = DocumentJobListQuery("T", "C", as_of=NOW, page_size=20)
            for name, query in (("default_page", base_query), ("no_match", replace(base_query, q="absent-search-token"))):
                samples = {"baseline": [], "ready": []}
                reference = None
                # 首轮单独保留，随后三轮交替执行顺序，降低固定顺序造成的偏差。
                for round_index in range(4):
                    order = (("baseline", old), ("ready", candidate))
                    if round_index % 2:
                        order = tuple(reversed(order))
                    for label, module in order:
                        result, timing = measure(module, connection, query)
                        if reference is None:
                            reference = result
                        assert result == reference, "同输入完整列表结果不等价，停止采样"
                        samples[label].append(timing)
                        print(json.dumps({"request": name, "round": round_index, "implementation": label,
                                          "total_seconds": timing["total_seconds"], "select_count": timing["select_count"],
                                          "full_result_equal": True}), flush=True)
                    if round_index == 0:
                        # 单次超过一分钟时继续三轮没有必要，保留明确失败而非扩大负载。
                        assert max(samples[label][0]["total_seconds"] for label in samples) < 60, "首次采样过慢，停止重复"
                report["requests"][name] = {"full_result_equal": True, "first": {key: value[0] for key, value in samples.items()},
                    "warmed": {key: value[1:] for key, value in samples.items()},
                    "median_seconds": {key: median(row["total_seconds"] for row in value[1:]) for key, value in samples.items()}}
            connection.rollback()
    # 不只根据 context manager 返回推断清理成功，明确检查本次 UUID 库已经消失。
    with pymysql.connect(**options, autocommit=True) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s", (schema,))
        report["schema_removed"] = cursor.fetchone()["n"] == 0
    assert report["schema_removed"], "本次 UUID 临时库未清理"
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"report": str(args.output), "schema_removed": True,
                      "medians": {name: value["median_seconds"] for name, value in report["requests"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
