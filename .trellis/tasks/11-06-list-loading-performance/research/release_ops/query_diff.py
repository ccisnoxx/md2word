"""隔离恢复库上的完整真实 router 对照；只输出响应摘要，不替代 HTTP 鉴权验收。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import json
import io
import os
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
from unittest.mock import patch

from common import OpsError, connection_factory, mysql_environment, safe_main, target_arguments
from snapshot import digest


def aware_time(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise OpsError("aware_as_of_required")
    return result.astimezone(timezone.utc)


@contextmanager
def frozen_clock(as_of):
    """只固定真实 owner 的时钟；不替换仓储、动作或发布证据依赖。"""
    from contextlib import ExitStack
    from app.domains.resources import models
    original = models.utc_now
    with ExitStack() as stack:
        for name, module in tuple(sys.modules.items()):
            if name.startswith("app.") and module is not None:
                for key, value in tuple(vars(module).items()):
                    if value is original:
                        stack.enter_context(patch.object(module, key, lambda: as_of))
        yield


def build_read_runtime(settings, backend):
    """按 main 的真实构造参数接线；不导入 main，不启动队列或调用任何 bootstrap。"""
    from app.domains.audit.service import AuditService
    from app.domains.document_jobs.execution import CeleryDocumentJobTaskQueue
    from app.domains.document_jobs.incidents import DocumentJobIncidentService
    from app.domains.document_jobs.preview import DocumentJobPreviewService
    from app.domains.document_jobs.service import DocumentJobService
    from app.domains.files import FileRetentionPolicyService, FileUploadService
    from app.domains.jobs.resource_snapshots import JobResourceSnapshotService
    from app.domains.resources.service import ResourceVersionService
    from app.domains.templates.read_service import TemplateReadService
    from app.domains.translation.term_version_service import TermVersionService
    from app.infrastructure.persistence.mysql.audit import MysqlAuditEventRepository
    from app.infrastructure.persistence.mysql.document_jobs import (
        MysqlDocumentJobRepository, MysqlDocumentJobEventRepository,
        MysqlDocumentJobTranslationBatchRepository,
    )
    from app.infrastructure.persistence.mysql.files import MysqlDocumentFileRepository
    from app.infrastructure.persistence.mysql.resources import MysqlResourceVersionRepository
    from app.infrastructure.persistence.mysql.retention_policies import MysqlRetentionPolicyRepository
    from app.infrastructure.persistence.mysql.term_assets import MysqlTranslationTermRepository
    from app.services.preview.sandbox_adapter import SandboxWordPreviewProvider

    if settings.document_jobs_worker_backend != "celery":
        raise OpsError("reviewed_celery_configuration_required")
    jobs = MysqlDocumentJobRepository(backend)
    files = MysqlDocumentFileRepository(backend)
    events = MysqlDocumentJobEventRepository(backend)
    audit = AuditService(MysqlAuditEventRepository(backend))
    retention = FileRetentionPolicyService(settings, MysqlRetentionPolicyRepository(backend), files)
    uploads = FileUploadService(settings, files, retention_days_resolver=retention.resolve_retention_days)
    resources = ResourceVersionService(MysqlResourceVersionRepository(backend))
    terms = MysqlTranslationTermRepository(backend)
    snapshots = JobResourceSnapshotService(settings, resources, terms)
    templates = TemplateReadService(settings, resources, audit, document_job_repository=jobs)
    term_service = TermVersionService(settings.translation_terms_file,
        default_term_version_id=settings.default_translation_term_version_id, repository=terms)
    provider = SandboxWordPreviewProvider(
        backend=settings.word_preview_backend, launcher=settings.word_preview_launcher,
        profile_path=settings.word_preview_profile_path, profile_id=settings.word_preview_profile_id,
        profile_sha256=settings.word_preview_profile_sha256)
    previews = DocumentJobPreviewService(settings, jobs, events, files, uploads,
        provider=provider, observer=provider, audit_service=audit)
    service = DocumentJobService(settings, jobs, events, files,
        CeleryDocumentJobTaskQueue(settings), templates, term_service, snapshots,
        document_job_translation_batch_repository=MysqlDocumentJobTranslationBatchRepository(backend),
        file_upload_service=uploads, word_preview_service=previews, audit_service=audit)
    return SimpleNamespace(document_job_service=service,
        document_job_incident_service=DocumentJobIncidentService(service))


def install_io_guard(host, port):
    """额外阻断意外外联、写文件和子进程；只读挂载/数据库只读账号仍为运行前提。"""
    addresses = {entry[4][0] for entry in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    addresses.add(host)
    denied = []

    def guard(event, args):
        blocked = False
        if event == "socket.connect":
            address = args[1]
            blocked = not (isinstance(address, tuple) and address[0] in addresses and address[1] == port)
        elif event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"}:
            blocked = args[0] not in addresses
        elif event == "open":
            _, mode, flags = args
            blocked = (mode is not None and any(letter in mode for letter in "wax+")) or bool(
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        elif event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.remove",
                       "os.rename", "os.mkdir", "os.rmdir", "os.link", "os.symlink", "os.truncate"}:
            blocked = True
        if blocked:
            denied.append(event)
            raise OpsError("readonly_runtime_io_denied")
    sys.addaudithook(guard)
    return denied


def run_cases(runtime, users, cases, as_of):
    from app.domains.document_jobs.router import list_document_jobs
    from app.domains.document_jobs.incidents_router import list_document_job_incidents
    from app.services.auth.models import AuthenticatedUser
    from app.services.auth.permissions import permissions_for_role
    defaults = {
        "jobs": dict(page=1, page_size=20, status_filter=None, status_group=None,
            translation_qa_status=None, q=None, sort="created_at_desc", include_archived=False,
            created_from=None, created_to=None),
        "incidents": dict(page=1, page_size=20, status_filter=None, stage=None, failure_type=None,
            retryable=None, retry_count=None, stalled_minutes=None, q=None, sort="priority"),
    }
    reports = []
    seen_roles = set()
    if not isinstance(cases, list) or not cases:
        raise OpsError("nonempty_case_matrix_required")
    with frozen_clock(as_of):
        for number, case in enumerate(cases):
            endpoint = case["endpoint"]
            if endpoint not in defaults or set(case["params"]) - defaults[endpoint].keys():
                raise OpsError("unknown_router_parameter")
            record = users.get_internal_user(case["user_id"])
            if (record is None or record.id != case["user_id"] or record.status != "active"
                    or record.role != case["expected_role"]):
                raise OpsError("actual_active_user_required")
            # 与 AuthService 的真实转换字段一致；不构造或签发 JWT，也不声称执行了鉴权。
            user = AuthenticatedUser(**{key: getattr(record, key) for key in (
                "id", "username", "role", "tenant_id", "company_id", "department_id",
                "display_name", "token_version")}, token_scopes=permissions_for_role(record.role))
            params = {**defaults[endpoint], **case["params"]}
            if (type(params["page"]) is not int or params["page"] < 1
                    or type(params["page_size"]) is not int or not 1 <= params["page_size"] <= 100):
                raise OpsError("invalid_pagination")
            for key in ("created_from", "created_to"):
                if params.get(key) is not None:
                    params[key] = aware_time(params[key])
            route = list_document_jobs if endpoint == "jobs" else list_document_job_incidents
            response = route(runtime=runtime, user=user, **params).model_dump(mode="json")
            reports.append({"case": number, "endpoint": endpoint, "role": user.role,
                "scope_sha256": digest([user.id, user.tenant_id, user.company_id, user.department_id]),
                "total": response["total"], "items": len(response["items"]),
                "response_sha256": digest(response)})
            seen_roles.add(user.role)
    if not {"admin", "operator"}.issubset(seen_roles):
        raise OpsError("actual_admin_and_operator_cases_required")
    return {"exit_code": 0, "format": "md2word-router-diff-v1", "as_of": as_of.isoformat(),
            "matrix_sha256": digest(cases), "cases": reports}


def compare(before, after):
    if (before.get("exit_code") != 0 or after.get("exit_code") != 0
            or before.get("format") != "md2word-router-diff-v1"
            or after.get("format") != before["format"]
            or not before.get("cases") or not after.get("cases")):
        raise OpsError("both_successful_complete_responses_required")
    equal = before == after
    return {"exit_code": int(not equal), "equal": equal, "cases": len(before["cases"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture")
    target_arguments(capture)
    capture.add_argument("--deny-server-uuid", required=True, help="生产实例 UUID；必须与恢复实例不同")
    capture.add_argument("--as-of", required=True)
    capture.add_argument("--cases", required=True, type=Path)
    check = commands.add_parser("compare")
    check.add_argument("before", type=Path)
    check.add_argument("after", type=Path)
    args = parser.parse_args()
    if args.command == "compare":
        report = compare(json.loads(args.before.read_text()), json.loads(args.after.read_text()))
    else:
        if args.expect_server_uuid == args.deny_server_uuid:
            raise OpsError("production_instance_forbidden")
        as_of = aware_time(args.as_of)
        cases = json.loads(args.cases.read_text())
        values = mysql_environment()
        from app.core.config import Settings
        from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
        from app.infrastructure.persistence.mysql.internal_users import MysqlInternalUserRepository
        sys.dont_write_bytecode = True
        settings = Settings(_env_file=None, jobs_repository_backend="mysql",
                            **{"jobs_mysql_" + key: value for key, value in values.items()})
        connect = connection_factory(values, args.expect_database, args.expect_server_uuid, readonly=True)
        backend = MysqlPersistenceBackend(MysqlPersistenceConfig(**values), initialize=False, connect_factory=connect)
        runtime = build_read_runtime(settings, backend)
        # 路由及其依赖先导入，再装审计保护，避免导入缓存写入被误记为业务写。
        from app.domains.document_jobs import router, incidents_router  # noqa: F401
        denied = install_io_guard(values["host"], values["port"])
        # 下游日志若含原始对象路径/业务错误，只留内存后丢弃；成功输出只有完整响应摘要。
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            report = run_cases(runtime, MysqlInternalUserRepository(backend), cases, as_of)
        if denied:
            raise OpsError("caught_runtime_io_denial_invalidates_response")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(safe_main(main))
