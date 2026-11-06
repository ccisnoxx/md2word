"""只读测量当前安装版本；不加载应用启动、不迁移、不输出业务字段或凭据。"""
import json
import time
from datetime import datetime, timezone
import pymysql
from app.core.config import Settings
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.document_jobs import MysqlDocumentJobRepository
from app.infrastructure.persistence.mysql.files import MysqlDocumentFileRepository
from app.infrastructure.persistence import document_job_list_query as sql_owner
from app.domains.document_jobs.list_query import DocumentJobListQuery
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.service import DocumentJobService

settings = Settings(_env_file=None)
config = MysqlPersistenceConfig(settings.jobs_mysql_host, settings.jobs_mysql_port, settings.jobs_mysql_user,
    settings.jobs_mysql_password, settings.jobs_mysql_database, settings.jobs_mysql_charset)

metrics = {}
active_kind = 'setup'
def append_metric(kind, key, elapsed):
    bucket=metrics.setdefault(kind,{})
    bucket[key]=bucket.get(key,0)+elapsed

class MeasuredCursor(pymysql.cursors.DictCursor):
    """只记阶段总耗时，不记录语句参数或业务数据。"""
    def execute(self, query, args=None):
        started=time.perf_counter()
        try:
            return super().execute(query,args)
        finally:
            if not query.startswith('SET SESSION'):
                append_metric(active_kind,'execute_seconds',time.perf_counter()-started)

def connect():
    started=time.perf_counter()
    connection = pymysql.connect(host=config.host, port=config.port, user=config.user, password=config.password,
        database=config.database, charset=config.charset, cursorclass=MeasuredCursor,
        autocommit=False, connect_timeout=10, read_timeout=20, write_timeout=10)
    append_metric(active_kind,'connect_seconds',time.perf_counter()-started)
    started=time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute('SET SESSION TRANSACTION READ ONLY')
        cursor.execute('SET SESSION MAX_EXECUTION_TIME=15000')
        cursor.execute('SET SESSION innodb_lock_wait_timeout=5')
    append_metric(active_kind,'diagnostic_setup_seconds',time.perf_counter()-started)
    return connection

def emit(stage, **values):
    print(json.dumps({'stage':stage, **values}, ensure_ascii=False, default=float), flush=True)

backend = MysqlPersistenceBackend(config, initialize=False, connect_factory=connect)
with backend.connect() as connection:
    with connection.cursor() as cursor:
        cursor.execute('SELECT @@transaction_read_only AS read_only, @@version AS version')
        emit('database', **cursor.fetchone())
        for table, projection in [('document_jobs', 'list_query_json'), ('document_files', 'review_query_json')]:
            cursor.execute(f'SELECT COUNT(*) AS rows_count, SUM(OCTET_LENGTH(payload)) AS payload_bytes, AVG(OCTET_LENGTH({projection})) AS projection_avg_bytes, MAX(OCTET_LENGTH({projection})) AS projection_max_bytes FROM {table}')
            record = cursor.fetchone()
            emit('size', table=table, **record)
            if table == 'document_jobs' and record['payload_bytes'] > 128*1024*1024:
                raise RuntimeError('诊断读取超过预设内存预算')
        cursor.execute("SELECT JSON_UNQUOTE(JSON_EXTRACT(payload,'$.tenant_id')) AS tenant_id, JSON_UNQUOTE(JSON_EXTRACT(payload,'$.company_id')) AS company_id, COUNT(*) AS n FROM document_jobs GROUP BY tenant_id,company_id ORDER BY n DESC")
        scopes=cursor.fetchall()
        emit('scope_counts', counts=[r['n'] for r in scopes])
        # 纯仓储诊断选择最大数据域；没有构造用户身份或调用认证接口。
        scope=scopes[0]
with backend.connect() as connection:
    start=time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute('SELECT payload FROM document_jobs ORDER BY created_at, job_id')
        rows=cursor.fetchall()
    emit('incident_load_payloads', seconds=round(time.perf_counter()-start,6), rows=len(rows))
start=time.perf_counter()
jobs=[DocumentJobRecord.model_validate_json(row['payload']) for row in rows]
emit('incident_decode', seconds=round(time.perf_counter()-start,6), jobs=len(jobs))
visible=[job for job in jobs if job.tenant_id==scope['tenant_id'] and job.company_id==scope['company_id'] and job.deleted_at is None and job.archived_at is None]
files=MysqlDocumentFileRepository(backend)
service=DocumentJobService(settings, MysqlDocumentJobRepository(backend), None, files)
file_calls=[]
original_get=files.get_document_file
def timed_get(file_id):
    global active_kind
    active_kind='file_get'
    start=time.perf_counter()
    record=original_get(file_id)
    file_calls.append(time.perf_counter()-start)
    return record
files.get_document_file=timed_get
protection_calls=[]
original_protected=files.is_document_file_protected
def timed_protected(file_id):
    global active_kind
    active_kind='protection'
    started=time.perf_counter()
    result=original_protected(file_id)
    protection_calls.append(time.perf_counter()-started)
    return result
files.is_document_file_protected=timed_protected
start=time.perf_counter()
views=[service._effective_job(job) for job in visible]
emit('incident_initial_review', seconds=round(time.perf_counter()-start,6), rows=len(views), file_calls=len(file_calls), file_seconds=round(sum(file_calls),6))
file_calls.clear()
protection_calls.clear()
metrics.clear()
start=time.perf_counter()
for job in views:
    service.build_incident_classification_view(job)
emit('incident_classification_view', seconds=round(time.perf_counter()-start,6), rows=len(views), file_calls=len(file_calls), file_seconds=round(sum(file_calls),6))

emit("incident_read_details", protection_calls=len(protection_calls), protection_seconds=round(sum(protection_calls),6), metrics={kind:{key:round(value,6) for key,value in values.items()} for kind,values in metrics.items()})
