"""从同源 qa607 工作树复用的发布夹具；仅外部 MinerU/预览 provider 使用替身。"""
from contextlib import contextmanager
from datetime import timedelta
import io
import json
from pathlib import Path
import struct
import tempfile
import zipfile
import zlib
from unittest.mock import patch
from uuid import uuid4
from app.domains.resources.models import ResourceVersionRecord, ResourceVersionStatus, utc_now
from app.domains.resources.service import ResourceVersionService
from app.domains.jobs.models import JobResourceSnapshot
from app.domains.jobs.resource_snapshots import JobResourceSnapshotService
from app.domains.term_rules.models import TermRulesStore
from app.domains.term_rules.yaml_codec import TermRuleYamlCodec
from app.domains.document_jobs.review import digest
from app.domains.document_jobs.publication import observed_publication_source
from app.services.auth.models import AuthenticatedUser
from app.services.preview.models import PreviewPolicy, PreviewResult, PreviewPage
from tests import test_fastapi_jobs_backend as fixtures
from tests import test_resource_versioning as resource_fixtures
from tests import test_document_job_execution_stages as stage_fixtures
from tests import test_document_job_result_persistence as result_fixtures


def pdf_bytes():
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] /Resources << >> /Contents 4 0 R >>",
               b"<< /Length 0 >>\nstream\n\nendstream"]
    data, positions = b"%PDF-1.4\n", [0]
    for index, body in enumerate(objects, 1):
        positions.append(len(data))
        data += str(index).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 5\n0000000000 65535 f \n" + b"".join(f"{pos:010d} 00000 n \n".encode() for pos in positions[1:])
    return data + b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"

def png_bytes(width=1, height=1):
    def chunk(kind, content):
        return struct.pack(">I", len(content)) + kind + content + struct.pack(">I", zlib.crc32(kind + content) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\0" + b"\0" * width * 4) * height)) + chunk(b"IEND", b""))

def preview_result(policy, *, pages=None):
    return PreviewResult(pdf=pdf_bytes(), page_count=1, provider_id="test-executor", provider_version="1.0",
                         profile_sha256=policy.profile_sha256, pages=tuple(pages if pages is not None else (
                             [PreviewPage(page_index=0, content=png_bytes(), width=1, height=1)] if policy.render_pages else [])))

def natural_package(*, formula=False, table=False):
    blocks = [{"type": "text", "text": "The document describes a stable design with clear behavior under normal use.", "page_idx": 0, "bbox": [40, 50 + index * 80, 550, 100 + index * 80]}
              for index in range(3)]
    if formula:
        blocks.append({"type": "equation", "latex": r"\unknown{VOUT}", "page_idx": 0, "bbox": [40, 350, 550, 400]})
    if table:
        blocks.append({"type": "table", "html": "<table><tr><th>Symbol</th><th>Value</th></tr><tr><td>X</td><td>12</td></tr></table>",
                       "page_idx": 0, "bbox": [40, 350, 250, 400]})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(zipfile.ZipInfo("content_list_v2.json", date_time=(2026, 1, 1, 0, 0, 0)), json.dumps(blocks))
        archive.writestr(zipfile.ZipInfo("middle.json", date_time=(2026, 1, 1, 0, 0, 0)),
            json.dumps({"pdf_info": [{"page_idx": 0, "page_size": [600, 800]}]}))
    return buffer.getvalue()

class RecordingPreviewProvider:
    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)
        self.inputs = []
        self.before_return = None

    def render(self, docx, *, policy):
        self.inputs.append(docx)
        if self.before_return: self.before_return()
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if isinstance(outcome, Exception): raise outcome
        return outcome or preview_result(policy)

class V2PublicationFixture:
    _upload_source_pdf = fixtures.FastAPIJobsBackendTests._upload_source_pdf
    _create = stage_fixtures.DocumentJobExecutionStageTests._create
    _files = stage_fixtures.DocumentJobExecutionStageTests._files
    _pause_after_ir = stage_fixtures.DocumentJobExecutionStageTests._pause_after_ir
    _build_runtime = result_fixtures.DocumentJobResultPersistenceTests._build_runtime


    @contextmanager
    def runtime(self, *, pages=False, outcomes=(), quality="pending", backend="sandboxed", required=True, kind="file", source_package=None):
        with tempfile.TemporaryDirectory(prefix="rnd504-app-") as directory:
            runtime = self._build_runtime(Path(directory), kind)
            execution = runtime.document_job_execution_service
            runtime.document_job_service.audit_service = runtime.audit_service
            # 在 HTTP 创建前给外部 fake 固定真实源；基础贡献由原转换/渲染/receipt 完成。
            execution.fake_mineru_client.result_zip_bytes = natural_package(table=True) if source_package is None else source_package
            provider = RecordingPreviewProvider(outcomes)
            execution.word_preview_service.provider = provider
            execution.word_preview_service.audit_service = runtime.audit_service
            runtime.document_job_service.word_preview_service = execution.word_preview_service
            with fixtures.TestClient(fixtures.create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                job = self._pause_after_ir(runtime, execution, client, headers)
                policy = PreviewPolicy(backend=backend, required=required, render_pages=pages)
                job = runtime.document_job_repository.update_document_job(job.id, quality_status=quality,
                    request_snapshot={**job.request_snapshot, "word_preview": policy.model_dump(mode="json")})
                user = AuthenticatedUser(id=job.created_by, username="operator", role="operator",
                                         tenant_id=job.tenant_id, company_id=job.company_id)
                yield runtime, execution, provider, job, user, client, headers

    @contextmanager
    def publication_runtime(self, *, kind="file", pages=True, complete=True, approved=True, legacy_base=True):
        with self.runtime(kind=kind, pages=pages, quality="passed") as (runtime, execution, provider, job, user, client, headers):
            job = self.install_publication_resources(runtime, execution, job, complete=complete)
            if legacy_base:
                # 合法历史任务不具有 fresh 基础贡献槽；实际表格/预览/发布认证仍完整执行。
                # 现代表格的自由布局风险会保持 pending，不能用本夹具宣称自动通过质量门。
                checks = {key: value for key, value in job.quality_summary.get("checks_v1", {}).items()
                    if key != "document_base"}
                job = job.model_copy(update={"quality_status": "passed",
                    "quality_summary": {**job.quality_summary, "checks_v1": checks}})
                with runtime.document_job_repository._locked_job(job.id) as (connection, _):
                    runtime.document_job_repository._write_job(connection, job)
            result = execution.execute_job(job.id)
            self.assertEqual(result.status, "succeeded", result.error_message)
            self.assertIn(result.quality_status, {"passed", "warning"})
            if approved:
                result = runtime.document_job_service.submit_document_review(result.id, user=user,
                    review_status="approved", note="内部复核已通过")
            runtime.settings.document_publication_enabled = True
            admin = user.model_copy(update={"id": "user_admin", "username": "admin", "role": "admin"})
            yield runtime, result, admin, user, client, headers, provider

    def install_publication_resources(self, runtime, execution, job, *, complete=True):
        repository = resource_fixtures._MemoryResourceVersionRepository()
        resources = ResourceVersionService(repository)
        selection = runtime.template_read_service.resolve_template_version(job.template_version_id)
        rules_store = TermRulesStore()
        rules_path = runtime.settings.data_path / "publication-symbol-rules.yaml"
        rules_path.write_text(TermRuleYamlCodec().dump_legacy_runtime_yaml(rules_store), encoding="utf-8")
        runtime.settings.term_rules_runtime_yaml_path = str(rules_path)
        for resource_type, resource_id, version, payload in (
            ("template", selection.template_id, str(selection.version), {"docx_path": str(selection.template_path),
                "layout_config_path": str(selection.layout_config_path)}),
            ("term_rule_set", "publication-rules", "1", {"store": rules_store.model_dump(mode="json")}),
        ):
            repository.save_resource_version(ResourceVersionRecord(resource_type=resource_type, resource_id=resource_id,
                version=version, status=ResourceVersionStatus.PUBLISHED, snapshot_hash=digest(payload), payload=payload))
        snapshot = JobResourceSnapshot(template=resources.resolve_version("template", selection.template_id, str(selection.version)),
            term_rule_set=resources.resolve_version("term_rule_set", "publication-rules", "1"))
        snapshots = JobResourceSnapshotService(runtime.settings, resources)
        execution.job_resource_snapshot_service = snapshots if complete else None
        runtime.document_job_service.job_resource_snapshot_service = snapshots
        job = runtime.document_job_repository.update_document_job(job.id,
            request_snapshot={**job.request_snapshot, "resources": snapshot.model_dump(mode="json")})
        return job

    def publish(self, runtime, job, admin, *, key=None, note="批准交付", source=None):
        file = runtime.document_file_repository.get_document_file(job.result_file_id)
        return runtime.document_job_service.publish_document(job.id, user=admin, request_id=key or str(uuid4()),
            note=note, expected_source=source or observed_publication_source(job, file), trace_id="publication-test")
