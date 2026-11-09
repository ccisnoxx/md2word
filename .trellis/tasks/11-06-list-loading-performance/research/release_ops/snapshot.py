"""全库只读 RR 原列保真摘要；不导出业务值，不依赖主键或去重。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from common import OpsError, connection_factory, mysql_environment, safe_main, target_arguments

KEYS = {
    "document_jobs": {"list_descriptor_key", "list_receipt_key", "list_table_snapshot_key"},
    "document_files": {"review_descriptor_key", "review_receipt_key"},
}
PROJECTIONS = {"document_jobs": "list_query_json", "document_files": "review_query_json"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), default=str).encode()).hexdigest()


def identifier(name):
    return "`" + name.replace("`", "``") + "`"


def row_digest(types, values):
    """类型、NULL 标记与字节长度都入摘要；空串和 NULL、列边界不能混淆。"""
    result = hashlib.sha256()
    for kind, value in zip(types, values, strict=True):
        encoded_type = kind.encode()
        result.update(len(encoded_type).to_bytes(8, "big") + encoded_type)
        if value is None:
            result.update(b"N")
        else:
            if not isinstance(value, bytes):
                raise OpsError("binary_column_result_required")
            result.update(b"V" + len(value).to_bytes(8, "big") + value)
    return result.digest()


def multiset_digest(rows):
    ordered = sorted(rows)
    return {"rows": len(ordered), "sha256": hashlib.sha256(b"".join(ordered)).hexdigest()}


def normalized_ddl(ddl, removed):
    # SHOW CREATE 的列定义独占一行；只去掉明确的新列，保留索引、约束及表选项。
    lines = []
    for line in ddl.splitlines():
        if any(line.lstrip().startswith(identifier(name) + " ") for name in removed):
            continue
        lines.append(line.rstrip().removesuffix(","))
    return "\n".join(lines)


def read_rows(connection, statement, params=()):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchall()


def snapshot(connection, *, include_derived=False):
    read_rows(connection, "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
    tables = read_rows(connection, "SELECT TABLE_NAME AS name, TABLE_TYPE AS kind, ENGINE AS engine "
                      "FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME")
    if not set(KEYS).issubset({table["name"] for table in tables}):
        raise OpsError("business_tables_required")
    result = {"format": "md2word-full-db-v1", "scope": "all_columns" if include_derived else "original_columns",
              "tables": {}}
    for table in tables:
        name = table["name"]
        if table["kind"] != "BASE TABLE" or table["engine"] != "InnoDB":
            # 非事务引擎/视图不能冒充同一 InnoDB 一致性快照；当前批准目标全为 InnoDB。
            raise OpsError("unsupported_table_kind_or_engine")
        columns = read_rows(connection, "SELECT COLUMN_NAME AS name, COLUMN_TYPE AS type, "
                            "DATA_TYPE AS data_type, IS_NULLABLE AS nullable, COLUMN_DEFAULT AS default_value, "
                            "EXTRA AS extra, GENERATION_EXPRESSION AS generation, "
                            "CHARACTER_SET_NAME AS charset, COLLATION_NAME AS collation, "
                            "COLUMN_COMMENT AS comment, ORDINAL_POSITION AS position "
                            "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                            "AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION", (name,))
        allowed = KEYS.get(name, set())
        present = {column["name"] for column in columns} & allowed
        projection = next((column for column in columns if column["name"] == PROJECTIONS.get(name)), None)
        for column in columns:
            if column["name"] in allowed and (
                column["type"] != "longtext" or column["nullable"] != "YES"
                or column["default_value"] is not None or column["extra"] or column["generation"] or column["comment"]
                or projection is None or column["charset"] != projection["charset"]
                or column["collation"] != projection["collation"]
            ):
                raise OpsError("unexpected_key_column_definition")
        ddl = read_rows(connection, "SHOW CREATE TABLE " + identifier(name))[0]["Create Table"]
        retained = columns if include_derived else [column for column in columns if column["name"] not in allowed]
        originals = retained if include_derived else [column for column in retained if column["name"] != PROJECTIONS.get(name)]
        # FLOAT 文本转换可能丢失有效位；未核实此类型的无损编码前明确阻断，不给出伪保真。
        if any(column["data_type"] in {"float", "double", "real"} for column in originals):
            raise OpsError("floating_column_requires_lossless_encoder")
        selected = ", ".join("CAST(" + identifier(column["name"]) + " AS BINARY) AS "
                             + identifier(column["name"]) for column in originals)
        if not selected:
            raise OpsError("original_columns_required")
        hashes = []
        import pymysql
        with connection.cursor(pymysql.cursors.SSDictCursor) as cursor:
            cursor.execute("SELECT " + selected + " FROM " + identifier(name))
            while batch := cursor.fetchmany(100):
                for row in batch:
                    hashes.append(row_digest([column["type"] for column in originals],
                                             [row[column["name"]] for column in originals]))
        result["tables"][name] = {
            **multiset_digest(hashes),
            "columns": [column["name"] for column in originals],
            "original_column_schema_sha256": digest(retained),
            "schema_sha256": digest(normalized_ddl(ddl, set() if include_derived else present)),
            "key_columns": {column["name"]: digest(column) for column in columns
                            if column["name"] in present},
        }
    # 不只比较两张业务表：库选项、触发器、事件和存储过程/函数也纳入结构摘要。
    schema = read_rows(connection, "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
                       "FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=DATABASE()")
    objects = {}
    for table, field in (("TRIGGERS", "TRIGGER_SCHEMA"), ("EVENTS", "EVENT_SCHEMA"),
                         ("ROUTINES", "ROUTINE_SCHEMA")):
        rows = read_rows(connection, f"SELECT * FROM INFORMATION_SCHEMA.{table} WHERE {field}=DATABASE()")
        definition = {"TRIGGERS": "ACTION_STATEMENT", "EVENTS": "EVENT_DEFINITION",
                      "ROUTINES": "ROUTINE_DEFINITION"}[table]
        if any(row[definition] is None for row in rows):
            raise OpsError("schema_definition_not_visible")
        objects[table] = sorted(digest(row) for row in rows)
    result["database_structure_sha256"] = digest({"schema": schema, "objects": objects})
    connection.rollback()
    return result


def compare(before, after, *, require_new_keys):
    if before.get("format") != "md2word-full-db-v1" or after.get("format") != before["format"]:
        raise OpsError("snapshot_format_mismatch")
    if before.get("scope") not in {"all_columns", "original_columns"} or after.get("scope") != before["scope"]:
        raise OpsError("snapshot_scope_mismatch")
    changed = []
    if before["database_structure_sha256"] != after["database_structure_sha256"]:
        changed.append("database_structure")
    if before["tables"].keys() != after["tables"].keys():
        changed.append("table_inventory")
    for name in before["tables"].keys() & after["tables"].keys():
        left, right = before["tables"][name], after["tables"][name]
        if any(left[key] != right[key] for key in
               ("rows", "sha256", "columns", "original_column_schema_sha256", "schema_sha256")):
            changed.append(name)
        if any(right["key_columns"].get(key) != value for key, value in left["key_columns"].items()):
            changed.append(name + ":existing_key_schema")
        if require_new_keys and set(right["key_columns"]) != KEYS.get(name, set()):
            changed.append(name + ":missing_keys")
    return {"exit_code": int(bool(changed)), "equal": not changed,
            "changed_structure_or_tables": sorted(set(changed)), "table_count": len(after["tables"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("snapshot")
    target_arguments(capture)
    capture.add_argument("--include-derived", action="store_true", help="同布局备份/恢复验证，全部列包括派生值也必须相同")
    check = commands.add_parser("compare")
    check.add_argument("before", type=Path)
    check.add_argument("after", type=Path)
    check.add_argument("--require-new-keys", action="store_true")
    args = parser.parse_args()
    if args.command == "compare":
        report = compare(json.loads(args.before.read_text()), json.loads(args.after.read_text()),
                         require_new_keys=args.require_new_keys)
    else:
        connect = connection_factory(mysql_environment(), args.expect_database, args.expect_server_uuid, readonly=True)
        connection = connect()
        try:
            report = {"exit_code": 0, **snapshot(connection, include_derived=args.include_derived)}
        finally:
            connection.close()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(safe_main(main))
