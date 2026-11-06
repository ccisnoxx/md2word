"""B10 四条真实只读路径的合成 SQLite 测量；不访问正文或外部服务。"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
import csv
import gc
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import resource
import sqlite3
import statistics
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

TASK = Path(__file__).resolve().parent
ROOT = TASK.parents[2]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings
from app.domains.audit.models import AuditEvent
from app.domains.document_jobs.incidents import DocumentJobIncidentService
from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobEventRecord
from app.domains.document_jobs.publication import PublicationRecord, observed_publication_source
from app.domains.document_jobs.review import ReviewBinding, ReviewSubmission
from app.domains.document_jobs.service import DocumentJobService
from app.domains.files.models import DocumentFileRecord
from app.domains.files.result_registration import review_source_descriptor
from app.domains.files.retention import DocumentFileRetentionPlanner
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.infrastructure.persistence.sqlite.document_jobs import SqliteDocumentJobRepository, SqliteDocumentJobEventRepository
from app.infrastructure.persistence.sqlite.files import SqliteDocumentFileRepository
from app.services.auth.models import AuthenticatedUser

NOW = datetime(2026, 11, 6, 0, tzinfo=timezone.utc)
CHECKSUM = 'sha256:' + '1' * 64
USER = AuthenticatedUser(id='owner', username='operator', role='admin', tenant_id='T', company_id='C')
TABLES = ('document_jobs', 'document_files', 'document_job_publications', 'job_events', 'document_job_review_records')


class BodySentinel:
    """正文入口一旦触达就失败；零计数来自实际运行而非预设值。"""
    def __init__(self):
        self.calls = 0

    def read_file_content(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError('测量路径不得读取对象正文')


def seed(backend, jobs, files, size):
    """真实仓储维护任务/文件投影；发布与事件是受控元数据夹具。"""
    publications, event_rows = [], []
    for index in range(size):
        job_id = f'job-{index:05d}'
        slot = index % 10
        created = NOW - timedelta(days=1, seconds=size-index)
        kinds = ['source_pdf'] + (['document_ir', 'generated_word'] if slot < 4 else [])
        records = []
        for kind in kinds:
            file_id = f'{job_id}-{kind}'
            filename, mime = {'source_pdf': ('source.pdf', 'application/pdf'),
                'document_ir': ('ir.json', 'application/json'),
                'generated_word': ('result.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}[kind]
            record = DocumentFileRecord(id=file_id, tenant_id='T', company_id='C', job_id=job_id,
                file_type=kind, storage_provider='local_file', bucket='local',
                object_key=f'document-jobs/T/{job_id}/{kind}/{file_id}/{filename}',
                original_filename=filename, mime_type=mime, size_bytes=1024,
                checksum_sha256=CHECKSUM, status='uploaded', created_by='owner',
                created_at=created, updated_at=created,
                expires_at=NOW + timedelta(days=-1 if slot in (4, 5) else 3))
            records.append(files.create_document_file(record))
        state, stage = ('succeeded', 'completed') if slot < 4 else ('failed', 'failed') if slot < 6 else ('running', 'translating') if slot < 8 else ('queued', 'uploaded')
        job = jobs.create_document_job(DocumentJobRecord(id=job_id, tenant_id='T', company_id='C',
            created_by='owner', source_file_id=records[0].id, template_version_id='template@1',
            mode='en2zh_pdf_to_word', status=state, stage=stage,
            result_file_id=records[-1].id if slot < 4 else None,
            document_ir_file_id=records[1].id if slot < 4 else None,
            quality_status='passed' if slot < 4 else 'pending',
            failed_stage='translating' if state == 'failed' else None,
            error_code='translation_failed' if state == 'failed' else None,
            error_message='合成翻译失败' if state == 'failed' else None,
            created_at=created, updated_at=created))
        if slot < 4:
            result = records[-1]
            job = jobs.update_document_job_review_if_current(job.id, submission=ReviewSubmission(
                record_id=job.id+'-review', status='needs_fix' if slot == 3 else 'approved',
                reviewed_by='owner', reviewer_role='admin', reviewed_at=NOW,
                binding=ReviewBinding(generation=0, result_file_id=result.id, binding_state='verified',
                    result_sha256=CHECKSUM, file_review_source_revision=result.review_source_revision,
                    descriptor=review_source_descriptor(result), receipt_sha256=None)))
            assert job is not None
            if slot < 2:
                publication_id = job.id+'-publication'
                publication = PublicationRecord(id=publication_id, job_id=job.id, tenant_id='T', company_id='C',
                    generation=0, request_id=job.id+'-request', submission_sha256=CHECKSUM,
                    published_by='owner', published_at=NOW, note='合成测量发布记录', trace_id='b10',
                    source_file_id=records[0].id, source_sha256=CHECKSUM, result_file_id=result.id,
                    result_sha256=CHECKSUM, expected_source=observed_publication_source(job, result),
                    review_record_id=job.current_review_record_id, review_sequence=job.review_sequence,
                    files=tuple(records), quality={'status': 'passed'}, preview={}, configuration={},
                    protected_file_ids=tuple(record.id for record in records),
                    audit=AuditEvent(audit_id=publication_id+'-audit', actor_id='owner', actor_role='admin',
                        action='document_job.publish', target_type='document_job', target_id=job.id,
                        trace_id='b10', created_at=NOW))
                publications.append(publication)
                with backend.connect() as connection:
                    jobs._write_job(connection, DocumentJobRecord.model_validate({**job.model_dump(),
                        'current_publication_id': publication_id, 'delivery_status': 'published'}))
        for event_index in range(21):
            event = DocumentJobEventRecord(id=f'{job_id}-event-{event_index}', tenant_id='T', company_id='C',
                job_id=job_id, created_by='owner', stage=stage, event_type='stage_started',
                message='合成阶段事件', payload={'sequence': event_index}, created_at=created)
            event_rows.append((job_id, backend.dump_payload(event), created.isoformat()))
        if len(event_rows) >= 2100:
            with backend.connect() as connection:
                connection.executemany('INSERT INTO job_events (job_id, payload, created_at) VALUES (?, ?, ?)', event_rows)
            event_rows.clear()
    with backend.connect() as connection:
        connection.executemany('INSERT INTO job_events (job_id, payload, created_at) VALUES (?, ?, ?)', event_rows)
        for publication in publications:
            jobs._insert_publication(connection, publication)
        counts = {table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in TABLES}
        protected = [json.loads(row[0]) for row in connection.execute(
            'SELECT protected_file_ids FROM document_job_publications').fetchall()]
        file_ids = {row[0] for row in connection.execute('SELECT file_id FROM document_files').fetchall()}
        assert len(protected) == size*2//10 and all(len(ids) == 3 for ids in protected)
        protected_ids = {file_id for ids in protected for file_id in ids}
        assert len(protected_ids) == size*6//10 and protected_ids <= file_ids
    assert counts == dict(zip(TABLES, (size, size*18//10, size*2//10, size*21, size*4//10)))
    assert files.is_document_file_protected('job-00000-source_pdf') is True
    assert files.is_document_file_protected('job-00004-source_pdf') is False
    return counts


def readonly(action, arg1, arg2, database, source):
    if action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
                  sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE}:
        raise AssertionError('测量请求不得写入数据库')
    return sqlite3.SQLITE_OK


class CursorCounter:
    """只记录交给调用方的行，不以返回行代替扫描量。"""
    def __init__(self, cursor, entry):
        self.cursor, self.entry = cursor, entry

    def fetchall(self):
        rows = self.cursor.fetchall()
        self.entry['returned_rows'] += len(rows)
        return rows

    def fetchone(self):
        row = self.cursor.fetchone()
        self.entry['returned_rows'] += int(row is not None)
        return row


class ConnectionCounter:
    def __init__(self, connection, counts):
        self.connection, self.counts = connection, counts

    def execute(self, sql, params=()):
        normalized = ' '.join(sql.split())
        entry = self.counts['sql'].get(normalized)
        if entry is None:
            plan = [dict(row) for row in self.connection.execute('EXPLAIN QUERY PLAN '+sql, params).fetchall()]
            entry = self.counts['sql'][normalized] = {'sql': normalized, 'sample_parameters': list(params),
                'calls': 0, 'returned_rows': 0, 'plan': plan}
        entry['calls'] += 1
        return CursorCounter(self.connection.execute(sql, params), entry)


@contextmanager
def instrument(backend, repositories, cardinalities):
    """独立计数阶段使用轻量闭包，避免 Mock 保存百万条调用历史。"""
    counts = {'sql': {}, 'repository_calls': Counter(), 'model_decodes': Counter(),
              'protected_id_json_decodes': 0, 'sqlite_progress_steps': 0, 'connections': 0}
    original_connect = backend.connect
    def progress():
        counts['sqlite_progress_steps'] += 1
        return 0
    @contextmanager
    def connect():
        counts['connections'] += 1
        with original_connect() as connection:
            connection.execute('PRAGMA query_only = ON')
            connection.set_authorizer(readonly)
            # EXPLAIN 的 VM 指令也可能触发回调，因此仅在真实语句执行时启用。
            yield ConnectionCounter(connection, counts)
    original_execute = ConnectionCounter.execute
    def execute(counter, sql, params=()):
        counter.connection.set_progress_handler(None, 0)
        normalized = ' '.join(sql.split())
        if normalized not in counts['sql']:
            plan = [dict(row) for row in counter.connection.execute('EXPLAIN QUERY PLAN '+sql, params).fetchall()]
            counts['sql'][normalized] = {'sql': normalized, 'sample_parameters': list(params),
                'calls': 0, 'returned_rows': 0, 'plan': plan}
        counter.connection.set_progress_handler(progress, 1000)
        return original_execute(counter, sql, params)
    def counted(original, counter, key):
        def call(*args, **kwargs):
            counter[key] += 1
            return original(*args, **kwargs)
        return call
    import app.infrastructure.persistence.sqlite.files as file_module
    real_loads = json.loads
    def protected_loads(value):
        counts['protected_id_json_decodes'] += 1
        return real_loads(value)
    with ExitStack() as stack:
        stack.enter_context(patch.object(backend, 'connect', connect))
        stack.enter_context(patch.object(ConnectionCounter, 'execute', execute))
        stack.enter_context(patch.object(file_module, 'json', SimpleNamespace(loads=protected_loads)))
        for repository in repositories:
            for name in vars(type(repository)):
                method = getattr(repository, name)
                if not name.startswith('_') and callable(method):
                    key = type(repository).__name__+'.'+name
                    stack.enter_context(patch.object(repository, name, counted(method, counts['repository_calls'], key)))
        for model in (DocumentJobRecord, DocumentFileRecord, DocumentJobEventRecord, PublicationRecord):
            for method in ('model_validate_json', 'model_validate'):
                stack.enter_context(patch.object(model, method,
                    counted(getattr(model, method), counts['model_decodes'], model.__name__+'.'+method)))
        yield counts
    entries = list(counts['sql'].values())
    aliases = {'j': 'document_jobs', 'f': 'document_files', **{name: name for name in TABLES}}
    for entry in entries:
        scans = []
        for row in entry['plan']:
            match = re.match(r'SCAN (\w+)', row['detail'])
            if match and match[1] in aliases:
                table = aliases[match[1]]
                scans.append({'table': table, 'rows_per_execution': cardinalities[table],
                              'visits': cardinalities[table]*entry['calls']})
        entry['inferred_full_scan_visits'] = scans
    counts['sql'] = entries
    counts['sql_calls'] = sum(entry['calls'] for entry in entries)
    counts['select_calls'] = sum(entry['calls'] for entry in entries if entry['sql'].startswith('SELECT'))
    counts['sql_returned_rows'] = sum(entry['returned_rows'] for entry in entries)
    counts['inferred_full_scan_visits'] = sum(scan['visits'] for entry in entries for scan in entry['inferred_full_scan_visits'])
    counts['sqlite_vm_ops_lower_bound'] = counts['sqlite_progress_steps']*1000
    counts['scan_method'] = 'EXPLAIN 中物理表 SCAN × 固定表基数 × 调用次数；非 rows_examined；不计索引 SEARCH、临时 B 树或 clock 常量扫描。当前数据前置 LIMIT 1 拒绝查询均返回0，分页使用排序后取页，完整扫描推导适用。'


def signature(value):
    """跨采样核对业务输出稳定性，摘要计算不计入延迟或内存。"""
    if isinstance(value, bool):
        return {'protected': value}
    if hasattr(value, 'candidates'):
        return {'totals': value.totals, 'candidate_ids_sha256': hashlib.sha256('\n'.join(x.file_id for x in value.candidates).encode()).hexdigest()}
    items = value.items
    ids = [x[0].id if isinstance(x, tuple) else x.job.id for x in items]
    summary = value.summary
    return {'total': value.total, 'page_ids': ids,
        'summary': summary.model_dump(mode='json') if hasattr(summary, 'model_dump') else summary}


def measure(path, call, backend, repositories, cardinalities, body, repeats):
    expected = signature(call())
    samples = []
    for repeat in range(repeats):
        gc.collect()
        started = time.perf_counter_ns()
        result = call()
        samples.append((time.perf_counter_ns()-started)/1e6)
        assert signature(result) == expected
        del result
        print(f'{path} 计时 {repeat+1}/{repeats}: {samples[-1]:.2f}ms', flush=True)
    gc.collect()
    with instrument(backend, repositories, cardinalities) as counts:
        result = call()
    assert signature(result) == expected
    del result
    print(f'{path} 独立计数完成', flush=True)
    import tracemalloc
    gc.collect()
    tracemalloc.start()
    result = call()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert signature(result) == expected
    del result
    assert body.calls == 0
    return {'path': path, 'latency_ms_samples': samples, 'latency_ms_median': statistics.median(samples),
        'latency_ms_min': min(samples), 'latency_ms_max': max(samples),
        'latency_ms_p95_nearest_rank': sorted(samples)[math.ceil(.95*len(samples))-1],
        'latency_ms_stdev': statistics.stdev(samples), 'python_peak_bytes': peak,
        'python_current_bytes_at_return': current, 'process_cumulative_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
        'body_read_calls': body.calls, 'result_signature': expected, 'counts': counts}


def run_size(size, repeats):
    database = TASK / 'measurement.sqlite'
    # 只清理由本次独占创建的数据库；既存文件说明前次异常，拒绝覆盖。
    database.touch(exist_ok=False)
    try:
        backend = SqlitePersistenceBackend(database)
        jobs, files, events = SqliteDocumentJobRepository(backend), SqliteDocumentFileRepository(backend), SqliteDocumentJobEventRepository(backend)
        with ExitStack() as clocks:
            for module in ('app.domains.document_jobs.service', 'app.domains.document_jobs.incidents',
                           'app.infrastructure.persistence.sqlite.document_jobs'):
                clocks.enter_context(patch(module+'.utc_now', lambda: NOW))
            cardinalities = seed(backend, jobs, files, size)
            print(f'{size} 档播种完成: {cardinalities}', flush=True)
            before_sha256 = hashlib.sha256(database.read_bytes()).hexdigest()
            body = BodySentinel()
            service = DocumentJobService(Settings.model_construct(document_publication_enabled=True), jobs, events, files, file_upload_service=body)
            incidents = DocumentJobIncidentService(service)
            planner = DocumentFileRetentionPlanner(files, retention_days=3)
            calls = {
                'list_jobs': lambda: service.list_jobs(user=USER, page=1, page_size=20, status_filter=None),
                'list_incidents': lambda: incidents.list_incidents(user=USER, page=1, page_size=20,
                    status_filter=None, stage_filter=None, failure_type=None, retryable=None,
                    retry_count=None, stalled_minutes=None, q=None, sort='updated_at_desc'),
                'is_document_file_protected': lambda: files.is_document_file_protected('job-00004-source_pdf'),
                'build_plan': lambda: planner.build_plan(now=NOW),
            }
            results = [measure(name, call, backend, (jobs, files, events), cardinalities, body, repeats) for name, call in calls.items()]
            after_sha256 = hashlib.sha256(database.read_bytes()).hexdigest()
            assert before_sha256 == after_sha256
            return {'jobs': size, 'cardinalities': cardinalities, 'database_bytes': database.stat().st_size,
                'database_sha256_before': before_sha256, 'database_sha256_after': after_sha256,
                'protection_checks': {'published_source_protected': True, 'failed_source_protected': False,
                    'protected_ids_per_publication': 3, 'distinct_protected_file_ids': size*6//10},
                'measurements': results}
    finally:
        database.unlink()
        for suffix in ('-journal', '-wal', '-shm'):
            database.with_name(database.name+suffix).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description='B10 本地 SQLite 四路径定向测量')
    parser.add_argument('--sizes', type=int, nargs='+', default=[120, 1000, 10000])
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--output', default='results')
    args = parser.parse_args()
    if args.repeats < 5 or any(size not in (120, 1000, 10000) for size in args.sizes):
        parser.error('仅允许120/1000/10000档，至少5次计时')
    if Path(args.output).name != args.output:
        parser.error('输出必须是本目录内的文件前缀')
    payload = {'environment': {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
        'machine': platform.machine(), 'sqlite': sqlite3.sqlite_version, 'fixed_now': NOW.isoformat(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        'method': {'warmups': 1, 'timing_repeats': args.repeats, 'counter_runs': 1, 'memory_runs': 1,
            'timing_connections': '真实backend.connect，无query_only或authorizer额外调用；防写仅在独立计数阶段，所有阶段前后DB哈希必须一致',
            'page': 1, 'page_size': 20, 'role': USER.role, 'sqlite_progress_interval_ops': 1000,
            'fixture': '每10任务: 成功4(已发布2/批准1/需修复1)、失败2、运行2、排队2；源文件10+成功IR4+成功DOCX4；事件210；发布2各保护3文件；失败source到期，其他文件未来到期。无正文对象、无预览资源配置。',
            'limitations': '合成元数据；发布绕过完整发布流程播种；真实仓储读行为不替换。只测service，不测HTTP序列化；SQLite C分配不在tracemalloc内；RSS为进程累计峰值。'}, 'datasets': []}
    for size in args.sizes:
        payload['datasets'].append(run_size(size, args.repeats))
        (TASK/(args.output+'.json')).write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n')
        with (TASK/(args.output+'.csv')).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['jobs', 'path', 'median_ms', 'min_ms', 'max_ms', 'p95_ms', 'stdev_ms', 'python_peak_bytes', 'cumulative_rss_bytes', 'sql_calls', 'returned_rows', 'full_scan_visits', 'repository_calls', 'job_decodes', 'file_decodes', 'protection_json_decodes', 'body_reads'])
            writer.writeheader()
            for dataset in payload['datasets']:
                for item in dataset['measurements']:
                    counts = item['counts']
                    writer.writerow(dict(jobs=dataset['jobs'], path=item['path'], median_ms=item['latency_ms_median'], min_ms=item['latency_ms_min'], max_ms=item['latency_ms_max'], p95_ms=item['latency_ms_p95_nearest_rank'], stdev_ms=item['latency_ms_stdev'], python_peak_bytes=item['python_peak_bytes'], cumulative_rss_bytes=item['process_cumulative_peak_rss_bytes'], sql_calls=counts['sql_calls'], returned_rows=counts['sql_returned_rows'], full_scan_visits=counts['inferred_full_scan_visits'], repository_calls=sum(counts['repository_calls'].values()), job_decodes=sum(value for key,value in counts['model_decodes'].items() if key.startswith('DocumentJobRecord.')), file_decodes=sum(value for key,value in counts['model_decodes'].items() if key.startswith('DocumentFileRecord.')), protection_json_decodes=counts['protected_id_json_decodes'], body_reads=item['body_read_calls']))
    print(f'测量完成: {args.output}.json / {args.output}.csv；SQLite临时文件已清理。', flush=True)


if __name__ == '__main__':
    main()
