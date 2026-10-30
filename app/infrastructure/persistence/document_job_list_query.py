"""列表两表事实查询与表格证据窄读；仅分页 SELECT 返回完整任务 payload。"""
from __future__ import annotations

import sqlite3
from typing import Any, get_args

from app.domains.document_jobs.list_query import (
    DOCUMENT_JOB_LIST_SORTS, TRANSLATION_LIST_MODES, DocumentJobListProjectionUnavailable,
    DocumentJobListQuery, DocumentJobListResult, datetime_query_key, raise_projection_rule_error,
)
from app.domains.document_jobs.list_query_facts import table_evidence_snapshot_key
from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobTranslationQaStatus
from app.domains.files.models import DocumentFileRecord

_JOB_TEXT = ("id", "tenant_id", "company_id", "created_by", "status", "mode", "review_status", "stage",
    "delivery_status", "result_id", "quality_error", "binding_error", "review_path", "binding_revision",
    "binding_checksum", "descriptor_key", "receipt_key", "effective_quality", "receipt_expiry_kind",
    "created_kind", "updated_kind", "table_snapshot_key")
_JOB_FLAGS = ("deleted", "archived", "result_present", "descriptor_key_comparable", "receipt_present",
    "receipt_expiry_present", "receipt_key_comparable", "table_snapshot_key_comparable")
_FILE_TEXT = ("id", "tenant_id", "company_id", "file_type", "job_id")
_WORD_TEXT = ("status", "revision", "checksum", "expiry_kind", "descriptor_error", "descriptor_key", "receipt_key")
_WORD_FLAGS = ("deletion_claim", "checksum_present", "expiry_present", "descriptor_key_comparable", "receipt_key_comparable")


class _ListSql:
    """同一两表合同的两个方言；不承担连接或事务所有权。"""
    def __init__(self, connection, mysql: bool):
        self.connection, self.mysql = connection, mysql
        self.marker = "%s" if mysql else "?"

    def read(self, statement: str, params: tuple = ()):
        try:
            if self.mysql:
                with self.connection.cursor() as cursor:
                    cursor.execute(statement, params)
                    return cursor.fetchall()
            return self.connection.execute(statement, params).fetchall()
        except Exception as error:
            # 旧结构缺少新增列属于明确不可用；其他 SQL/连接错误继续原样传播。
            missing = (self.mysql and error.args and error.args[0] == 1054) or (
                isinstance(error, sqlite3.OperationalError) and "no such column:" in str(error))
            if missing and any(column in str(error) for column in ("list_query_json", "review_query_json")):
                raise DocumentJobListProjectionUnavailable("列表查询事实列未就绪。") from error
            raise

    def extracted(self, source: str, name: str):
        return f"JSON_EXTRACT({source}, '$.{name}')"

    def text(self, source: str, name: str, *, binary: bool = True):
        value = self.extracted(source, name)
        if self.mysql:
            value = f"JSON_UNQUOTE({value})"
            return f"CAST({value} AS BINARY)" if binary else value
        return f"({value} COLLATE BINARY)" if binary else value

    def number(self, source: str, name: str):
        value = self.extracted(source, name)
        if self.mysql:
            value = f"JSON_UNQUOTE({value})"
        return f"CAST({value} AS {'SIGNED' if self.mysql else 'INTEGER'})"

    def kind(self, source: str, name: str):
        return (f"JSON_TYPE({self.extracted(source, name)})" if self.mysql
                else f"JSON_TYPE({source}, '$.{name}')")

    def shape(self, source: str, *, job: bool):
        string, integer, array = ("STRING", "INTEGER", "ARRAY") if self.mysql else ("text", "integer", "array")
        texts = _JOB_TEXT if job else _FILE_TEXT
        flags = _JOB_FLAGS if job else ("job_present",)
        numbers = ("created_us", "updated_us", "receipt_expiry_us") if job else ()
        def is_integer(name):
            # MySQL 8.4 会将微秒时间报告为 UNSIGNED INTEGER，值仍须使用有符号范围比较。
            kinds = "('INTEGER', 'UNSIGNED INTEGER')" if self.mysql else "('integer')"
            return f"{self.kind(source, name)} IN {kinds}"
        checks = [is_integer("version"), f"{self.number(source, 'version')} = {2 if job else 1}"]
        checks += [f"{self.kind(source, name)} = '{string}'" for name in texts]
        checks += [f"({is_integer(name)} AND {self.number(source, name)} IN (0, 1))" for name in flags]
        checks += [is_integer(name) for name in numbers]
        if job:
            checks.append(f"{self.kind(source, 'search')} = '{array}'")
            length = f"JSON_LENGTH({source}, '$.search')" if self.mysql else f"JSON_ARRAY_LENGTH({source}, '$.search')"
            checks.append(f"{length} <= 5")
            for index in range(5):
                checks.append(f"({length} <= {index} OR {self.kind(source, f'search[{index}]')} = '{string}')")
        else:
            word = [f"{self.kind(source, name)} = '{string}'" for name in _WORD_TEXT]
            word += [f"({is_integer(name)} AND {self.number(source, name)} IN (0, 1))" for name in _WORD_FLAGS]
            word.append(is_integer("expiry_us"))
            checks.append(f"({self.text(source, 'file_type')} <> 'generated_word' OR ({' AND '.join(word)}))")
        # CASE 保证坏 JSON 不进入 JSON_EXTRACT；缺键产生的 NULL 不能被当作有效。
        return f"CASE WHEN JSON_VALID({source}) THEN COALESCE(({' AND '.join(checks)}), 0) ELSE 0 END"

    def assert_ready(self, table: str, column: str, *, job: bool):
        rows = self.read(f"SELECT COUNT(*) AS n FROM {table} WHERE ({self.shape(column, job=job)}) = 0")
        if rows[0]["n"]:
            raise DocumentJobListProjectionUnavailable("列表查询事实缺失、损坏或版本不支持。")


def is_document_job_table_evidence_snapshot_current_sql(connection, expected: DocumentJobRecord, *, mysql: bool) -> bool:
    """保留每次独立当前读；不返回 payload，不把普通来源变化当作存储错误。"""
    sql = _ListSql(connection, mysql)
    source = "list_query_json"
    ready = sql.shape(source, job=True)
    key, comparable = table_evidence_snapshot_key(expected)
    equal = (f"{sql.number(source, 'deleted')} = 0 AND {sql.number(source, 'table_snapshot_key_comparable')} = 1 "
             f"AND {1 if comparable else 0} = 1 AND {sql.text(source, 'table_snapshot_key')} = {sql.marker}")
    rows = sql.read(f"SELECT {ready} AS ready, CASE WHEN ({ready}) = 1 THEN "
        f"CASE WHEN {equal} THEN 1 ELSE 0 END ELSE 0 END AS is_current "
        f"FROM document_jobs WHERE job_id = {sql.marker}", (key, expected.id))
    if not rows:
        return False
    if not rows[0]["ready"]:
        raise DocumentJobListProjectionUnavailable("表格证据当前任务事实未就绪。")
    return bool(rows[0]["is_current"])


def query_document_jobs_sql(connection: Any, query: DocumentJobListQuery, *, mysql: bool) -> DocumentJobListResult:
    sql = _ListSql(connection, mysql)
    sql.assert_ready("document_jobs", "list_query_json", job=True)
    sql.assert_ready("document_files", "review_query_json", job=False)
    marker = sql.marker
    j = lambda name: sql.text("j.list_query_json", name)
    f = lambda name: sql.text("f.review_query_json", name)
    jn = lambda name: sql.number("j.list_query_json", name)
    fn = lambda name: sql.number("f.review_query_json", name)
    as_of, kind = datetime_query_key(query.as_of)
    if kind != "aware":
        raise ValueError("列表观察时刻必须包含时区。")
    gate = f"({j('status')} = 'succeeded' AND {j('stage')} = 'completed' AND {jn('result_present')} = 1)"
    # 文件寻址沿原 file_id 列 collation；命中后另做 payload ID 的严格比较。
    result_id = sql.text("j.list_query_json", "result_id", binary=False)
    source = (f"document_jobs j CROSS JOIN (SELECT {marker} AS as_of) clock "
              f"LEFT JOIN document_files f ON {gate} AND f.file_id = {result_id}")
    observed = (f"({gate} AND f.file_id IS NOT NULL AND {f('tenant_id')} = {j('tenant_id')} "
        f"AND {f('company_id')} = {j('company_id')} AND {fn('job_present')} = 1 "
        f"AND {f('job_id')} = {j('id')} AND {f('file_type')} = 'generated_word' AND {f('status')} = 'uploaded')")
    visible = [f"{j('tenant_id')} = {marker}", f"{j('company_id')} = {marker}", f"{jn('deleted')} = 0"]
    values: list[Any] = [query.tenant_id, query.company_id]
    if query.created_by is not None:
        visible.append(f"{j('created_by')} = {marker}")
        values.append(query.created_by)
    if not query.include_archived:
        visible.append(f"{jn('archived')} = 0")

    def count(conditions, params):
        return sql.read(f"SELECT COUNT(*) AS n FROM {source} WHERE {' AND '.join(conditions)}", (as_of, *params))[0]["n"]

    if count([*visible, gate, "f.file_id IS NOT NULL", f"{f('id')} <> {j('result_id')}"], values):
        raise ValueError("文件寻址与 payload 的 id 不一致。")
    if count([*visible, observed, f"{fn('deletion_claim')} = 0", f"{fn('expiry_present')} = 1",
              f"{f('expiry_kind')} <> 'aware'"], values):
        raise TypeError("下载到期时间与列表观察时刻的时区类型不兼容。")

    def rule_error(expression: str, prefix: list[str]):
        rows = sql.read(f"SELECT {expression} AS error FROM {source} WHERE "
            + " AND ".join([*visible, *prefix, f"{expression} <> ''"]) + " LIMIT 1", (as_of, *values))
        if rows:
            code = rows[0]["error"]
            raise_projection_rule_error(code.decode() if isinstance(code, bytes) else code)

    rule_error(j("quality_error"), [])
    rule_error(j("binding_error"), [])
    live = (f"({j('review_path')} = 'verified' AND {observed} "
            f"AND ({fn('expiry_present')} = 0 OR {fn('expiry_us')} > clock.as_of))")
    same_revision = f"{f('revision')} = {j('binding_revision')}"
    rule_error(f("descriptor_error"), [live, same_revision])
    descriptor = (f"({fn('descriptor_key_comparable')} = 1 AND {jn('descriptor_key_comparable')} = 1 "
                  f"AND {f('descriptor_key')} = {j('descriptor_key')})")
    checksum = f"({fn('checksum_present')} = 0 OR {f('checksum')} = {j('binding_checksum')})"
    receipt_prefix = [live, same_revision, descriptor, checksum, f"{jn('receipt_present')} = 1"]
    if count([*visible, *receipt_prefix, f"{fn('expiry_present')} = 1", f"{jn('receipt_expiry_present')} = 1",
              f"{f('expiry_kind')} <> {j('receipt_expiry_kind')}"], values):
        raise TypeError("当前文件与结果凭据的到期时间类型不兼容。")
    receipt = (f"({jn('receipt_present')} = 0 OR ({fn('expiry_present')} = 1 "
        f"AND {jn('receipt_expiry_present')} = 1 AND {fn('expiry_us')} <= {jn('receipt_expiry_us')} "
        f"AND {fn('receipt_key_comparable')} = 1 AND {jn('receipt_key_comparable')} = 1 "
        f"AND {f('receipt_key')} = {j('receipt_key')}))")
    valid = (f"CASE WHEN {j('review_path')} = 'unbound' THEN {j('review_status')} <> 'approved' "
        f"WHEN {j('review_path')} = 'invalid' THEN 0 ELSE ({live} AND {same_revision} AND {descriptor} "
        f"AND {checksum} AND {receipt} AND ({j('review_status')} <> 'approved' OR {j('effective_quality')} <> 'blocked')) END")
    effective = f"CASE WHEN {j('delivery_status')} = 'published' OR ({valid}) THEN {j('review_status')} ELSE 'unreviewed' END"

    def group(expression, conditions, params):
        rows = sql.read(f"SELECT {expression} AS value, COUNT(*) AS n FROM {source} WHERE "
            + " AND ".join(conditions) + f" GROUP BY {expression}", (as_of, *params))
        return {(row["value"].decode("utf-8") if isinstance(row["value"], bytes) else row["value"]): int(row["n"])
                for row in rows}

    summary = group(j("status"), visible, values)
    clauses = list(visible)
    if query.statuses is not None:
        clauses.append(f"{j('status')} IN ({', '.join([marker] * len(query.statuses))})")
        values.extend(query.statuses)
    if query.q is not None:
        expressions = []
        for index in range(5):
            value = j(f"search[{index}]")
            expressions.append(f"LOCATE(CAST({marker} AS BINARY), {value}) > 0" if mysql
                               else f"INSTR({value}, {marker}) > 0")
        clauses.append("(" + " OR ".join(expressions) + ")")
        values.extend([query.q] * 5)
    # 日期边界先下界后上界，检查范围在 QA 模式筛选之前。
    for boundary, operator in ((query.created_from, ">="), (query.created_to, "<=")):
        if boundary is None:
            continue
        micros, boundary_kind = datetime_query_key(boundary)
        if count([*clauses, f"{j('created_kind')} <> {marker}"], [*values, boundary_kind]):
            raise TypeError("任务创建时间与查询边界的时区类型不兼容。")
        clauses.append(f"{jn('created_us')} {operator} {marker}")
        values.append(micros)
    translation = f"{j('mode')} IN ({', '.join([marker] * len(TRANSLATION_LIST_MODES))})"
    qa = group(effective, [*clauses, translation], [*values, *TRANSLATION_LIST_MODES])
    if query.translation_qa_status is not None:
        clauses.append(translation)
        values.extend(TRANSLATION_LIST_MODES)
        if query.translation_qa_status != "all":
            clauses.append(f"({effective}) = {marker}")
            values.append(query.translation_qa_status)
    filtered = group(j("status"), clauses, values)
    column, descending = DOCUMENT_JOB_LIST_SORTS[query.sort]
    kinds = sql.read(f"SELECT COUNT(DISTINCT {j(column + '_kind')}) AS n FROM {source} WHERE "
                    + " AND ".join(clauses), (as_of, *values))
    if kinds[0]["n"] > 1:
        raise TypeError("排序时间混合了有时区和无时区值。")
    direction = "DESC" if descending else "ASC"
    rows = sql.read(f"SELECT j.payload AS payload, f.payload AS observed_payload "
        f"FROM {source} WHERE " + " AND ".join(clauses)
        + f" ORDER BY {jn(column + '_us')} {direction}, {j('id')} {direction} LIMIT {marker} OFFSET {marker}",
        (as_of, *values, query.page_size, (query.page - 1) * query.page_size))
    items, observations = [], {}
    for row in rows:
        item = DocumentJobRecord.model_validate_json(row["payload"])
        items.append(item)
        observations[item.id] = (DocumentFileRecord.model_validate_json(row["observed_payload"])
                                 if row["observed_payload"] is not None else None)
    return DocumentJobListResult(items, sum(filtered.values()), summary, filtered,
        {key: qa.get(key, 0) for key in get_args(DocumentJobTranslationQaStatus)}, observations)
