"""冻结旧/ready 查询与组合候选在同一合成输入上的完整结果对照。"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
from statistics import median
import subprocess
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("ready_benchmark_helpers", Path(__file__).with_name("benchmark-ready-mysql.py"))
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)

from app.core.config import Settings
from app.domains.document_jobs.list_query import (
    document_job_list_projection_from_raw, document_file_review_projection_from_raw,
)
from scripts.ops.migrate_document_job_list_query import migrate_document_job_list_query


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    environ = json.loads(args.credentials.read_text())
    old_source = subprocess.check_output(["git", "show", f"{helpers.BASELINE}:{helpers.SQL_PATH}"], cwd=ROOT)
    ready_source = Path(__file__).with_name("data").joinpath("key-source-freeze/ready-sql.py").read_bytes()
    assert hashlib.sha256(ready_source).hexdigest() == "061ab44e5b9c88490103ee7701dcd96f389d5d2bda2f349dd6f1ea9923fd6aeb"
    modules = {}
    for label, source in (("baseline", old_source), ("ready", ready_source)):
        module = ModuleType("frozen_" + label)
        exec(compile(source, "frozen_" + label, "exec"), module.__dict__)
        modules[label] = module
    report = {"synthetic_only": True, "as_of": helpers.NOW.isoformat(),
              "baseline_sql_sha256": hashlib.sha256(old_source).hexdigest(),
              "ready_sql_sha256": hashlib.sha256(ready_source).hexdigest(),
              "combined_sql_sha256": hashlib.sha256((ROOT / helpers.SQL_PATH).read_bytes()).hexdigest(),
              "fixture": {"jobs": 119, "files": 1928, "receipt_metadata_chars": 35000,
                          "current_metadata_chars": 3500}, "requests": {}}
    with helpers._temporary_schema(environ) as (options, schema):
        report["temporary_schema"] = schema
        backend = helpers.MysqlPersistenceBackend(helpers.MysqlPersistenceConfig(
            host=options["host"], port=options["port"], user=options["user"],
            password=options["password"], database=schema), initialize=False)
        files = helpers.MysqlDocumentFileRepository(backend)
        jobs = helpers.MysqlDocumentJobRepository(backend)
        with backend.connect() as connection:
            for index in range(1928):
                file = helpers.word(f"word-{index:04d}", f"job-{index:04d}", metadata={"synthetic": "x" * 3500})
                files._write_file(connection, file, create=True)
        for index in range(119):
            embedded = helpers.word(f"word-{index:04d}", f"job-{index:04d}", metadata={"synthetic": "x" * 35000})
            jobs.create_document_job(helpers.bound_job(embedded, receipt=True))
        # 同一权威 payload 重建旧布局；只改变派生事实，不改变结果输入。
        with backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT VERSION() AS version, @@server_uuid AS server_uuid")
            report["engine"] = cursor.fetchone()
            for table, identity, column, builder in (
                ("document_jobs", "job_id", "list_query_json", document_job_list_projection_from_raw),
                ("document_files", "file_id", "review_query_json", document_file_review_projection_from_raw),
            ):
                cursor.execute(f"SELECT {identity}, payload FROM {table}")
                for row in cursor.fetchall():
                    cursor.execute(f"UPDATE {table} SET {column} = %s WHERE {identity} = %s",
                                   (json.dumps(builder(row["payload"]), ensure_ascii=False), row[identity]))
        base = helpers.DocumentJobListQuery("T", "C", as_of=helpers.NOW, page_size=20)
        queries = {"default_page": base, "no_match": replace(base, q="absent-search-token")}
        references = {}
        with backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            # 旧/ready 三轮计时已有冻结证据；本轮各一次仅确认当前夹具与完整结果。
            for name, query in queries.items():
                report["requests"][name] = {"reference_samples": {}}
                for label, module in modules.items():
                    result, timing = helpers.measure(module, connection, query)
                    if name in references:
                        assert result == references[name], "冻结旧实现与 ready 结果不等价"
                    references[name] = result
                    report["requests"][name]["reference_samples"][label] = timing
                    print(json.dumps({"request": name, "implementation": label,
                                      "seconds": timing["total_seconds"]}), flush=True)
        settings = Settings.model_construct(jobs_repository_backend="mysql", jobs_mysql_host=options["host"],
            jobs_mysql_port=options["port"], jobs_mysql_user=options["user"], jobs_mysql_password=options["password"],
            jobs_mysql_database=schema, jobs_mysql_charset="utf8mb4", jobs_mysql_connect_timeout_seconds=5)
        for mode in ("apply", "verify"):
            migration = migrate_document_job_list_query(settings, mode=mode, batch_size=3000,
                                                       mysql_connect_factory=lambda: helpers.pymysql.connect(
                                                           **options, database=schema, autocommit=False))
            assert migration["exit_code"] == 0, "合成库迁移失败"
            if mode == "verify":
                assert migration["all_ready"], "合成库全量校验未就绪"
        with backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            report["projection_bytes"] = {}
            for table, column in (("document_jobs", "list_query_json"), ("document_files", "review_query_json")):
                cursor.execute(f"SELECT COUNT(*) AS n, AVG(OCTET_LENGTH({column})) AS mean_bytes, "
                               f"MAX(OCTET_LENGTH({column})) AS max_bytes FROM {table}")
                facts = cursor.fetchone()
                facts["mean_bytes"] = float(facts["mean_bytes"])
                report["projection_bytes"][table] = facts
            for name, query in queries.items():
                samples = []
                for _ in range(4):
                    result, timing = helpers.measure(helpers.candidate, connection, query)
                    assert result == references[name], "组合候选与冻结旧实现完整结果不等价"
                    samples.append(timing)
                report["requests"][name].update(full_result_equal=True, first=samples[0], warmed=samples[1:],
                    median_seconds=median(row["total_seconds"] for row in samples[1:]))
    with helpers.pymysql.connect(**options, autocommit=True) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s", (schema,))
        report["schema_removed"] = cursor.fetchone()["n"] == 0
    assert report["schema_removed"], "本次临时库未清理"
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"schema_removed": True, "medians": {
        name: result["median_seconds"] for name, result in report["requests"].items()}}))


if __name__ == "__main__":
    main()
