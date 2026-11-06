"""核对 B10 原始证据的覆盖、计数关系与只读性；不连接数据库。"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import statistics


def main():
    task = Path(__file__).resolve().parent
    results = json.loads((task / "results.json").read_text())
    with (task / "results.csv").open(newline="") as stream:
        csv_rows = {(int(row["jobs"]), row["path"]): row for row in csv.DictReader(stream)}
    assert results["environment"]["script_sha256"] == hashlib.sha256((task / "measure.py").read_bytes()).hexdigest()
    assert [dataset["jobs"] for dataset in results["datasets"]] == [120, 1000, 10000]
    assert len(csv_rows) == 12
    paths = {"list_jobs", "list_incidents", "is_document_file_protected", "build_plan"}
    checks = []
    for dataset in results["datasets"]:
        size = dataset["jobs"]
        files, publications = size * 18 // 10, size // 5
        assert dataset["database_sha256_before"] == dataset["database_sha256_after"]
        assert dataset["cardinalities"]["document_files"] == files
        assert dataset["cardinalities"]["document_job_publications"] == publications
        assert dataset["cardinalities"]["job_events"] == size * 21
        assert {item["path"] for item in dataset["measurements"]} == paths
        for item in dataset["measurements"]:
            path, counts = item["path"], item["counts"]
            samples = item["latency_ms_samples"]
            assert len(samples) == 5 and all(value > 0 for value in samples)
            assert statistics.median(samples) == item["latency_ms_median"]
            assert max(samples) == item["latency_ms_p95_nearest_rank"]
            assert item["python_peak_bytes"] > 0 and item["body_read_calls"] == 0
            assert float(csv_rows[(size, path)]["median_ms"]) == item["latency_ms_median"]
            assert int(csv_rows[(size, path)]["returned_rows"]) == counts["sql_returned_rows"]
            assert not any("job_events" in entry["sql"] for entry in counts["sql"])
            # 这些关系来自固定样本和实际读合同，用于发现漏计或假全量测量。
            if path == "list_jobs":
                assert item["result_signature"]["total"] == size
                assert len(item["result_signature"]["page_ids"]) == 20
                assert counts["model_decodes"]["DocumentJobRecord.model_validate_json"] == 20
                assert counts["inferred_full_scan_visits"] == 12 * size + files
            elif path == "list_incidents":
                assert item["result_signature"]["total"] == size * 6 // 10
                assert counts["model_decodes"]["DocumentJobRecord.model_validate_json"] == size
            elif path == "is_document_file_protected":
                assert item["result_signature"] == {"protected": False}
                assert counts["select_calls"] == 1
                assert counts["sql_returned_rows"] == publications
                assert counts["protected_id_json_decodes"] == publications
            else:
                assert counts["select_calls"] == files + 1
                assert counts["sql_returned_rows"] == files + files * publications
                assert counts["inferred_full_scan_visits"] == files + files * publications
                assert item["result_signature"]["totals"]["candidate_files"] == size // 5
            checks.append({"jobs": size, "path": path, "status": "passed"})
    assert not list(task.glob("*.sqlite*"))
    (task / "verification.json").write_text(json.dumps({"status": "passed", "checks": checks,
        "note": "12组证据覆盖完整；CSV中位数和返回行字段一致；脚本摘要、固定样本计数、正文零读取、数据库前后SHA及临时库清理通过。"},
        ensure_ascii=False, indent=2) + "\n")
    print("证据核对通过：3档×4路径；CSV中位数和返回行字段一致，前后数据库不变，无临时数据库。")


if __name__ == "__main__":
    main()
