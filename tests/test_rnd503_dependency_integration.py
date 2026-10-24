"""保护已接受输入/题注依赖接入后的历史公式产物恢复。"""

import json
from unittest import TestCase
from unittest.mock import patch

from app.services.document_ir.models import DocumentIR
from app.services.renderer.evidence import build_renderer_evidence
from tests import test_document_job_result_persistence as base


class Rnd503DependencyIntegrationTests(TestCase):
    def test_original_validation_shapes_keep_all_three_recovery_entries(self):
        helper = base.DocumentJobResultPersistenceTests()
        for shape in ("absent", "none", "nonempty_ignored", "nonempty_saved"):
            for entry in ("legacy", "explicit", "receipt"):
                with self.subTest(shape=shape, entry=entry), helper._runtime() as (
                    _root, runtime, execution, job, _client, _headers,
                ):
                    job, ir = helper._install_formula_ir(runtime, execution, job, source="$x^2+3$")
                    payload = json.loads(ir.model_dump_json())
                    if shape in {"absent", "none"}:
                        # IR-205 账本依赖 IR-201 checksum；真实旧 IR 同时没有这组新字段。
                        for key in ("logical_table_groups_version", "logical_table_groups", "logical_table_group_counts"):
                            payload["metadata"].pop(key, None)
                        for block in payload["blocks"]:
                            for key in ("logical_group_id", "table_fragment_id", "source_spans"):
                                block["metadata"].pop(key, None)
                        for key in ("mineru_validation", "mineru_validation_input"):
                            if shape == "absent":
                                payload["metadata"].pop(key, None)
                            else:
                                payload["metadata"][key] = None
                    original = execution._get_document_ir_file(job)
                    ir_file = runtime.file_upload_service.register_generated_content(
                        tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id,
                        created_by=job.created_by, file_type="document_ir", filename="history.document-ir.json",
                        mime_type="application/json", content=json.dumps(payload).encode(),
                        metadata=original.metadata,
                    )
                    job = runtime.document_job_repository.update_document_job(job.id, document_ir_file_id=ir_file.id)
                    ir = DocumentIR.model_validate(payload)
                    template = execution.template_read_service.resolve_template_version(job.template_version_id)
                    rendered = execution.word_renderer.render_to_result(
                        ir, template_path=template.template_path, config_path=template.layout_config_path,
                        image_loader=execution._build_image_loader(job),
                    )
                    content = base.legacy_image_docx(rendered.content)
                    evidence = build_renderer_evidence(ir, content, formula_report=rendered.formula_report)
                    if shape != "nonempty_saved":
                        for key in ("mineru_validation", "mineru_validation_input", "caption_reconciliation"):
                            evidence.pop(key, None)
                    word = runtime.file_upload_service.register_generated_content(
                        tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id,
                        created_by=job.created_by, file_type="generated_word", filename="history.docx",
                        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        content=content, metadata={"retry_count": job.retry_count,
                            "document_ir_file_id": ir_file.id, **evidence},
                    )
                    job = runtime.document_job_repository.update_document_job(job.id, stage="uploading")
                    if entry == "explicit":
                        helper._install_formula_ir(runtime, execution, job, source="$y^3$")
                        job = runtime.document_job_repository.update_document_job(
                            job.id, retry_count=1, result_file_id=word.id,
                        )
                    elif entry == "receipt":
                        job = runtime.document_job_repository.prepare_document_job_result(
                            job.id, expected_retry_count=job.retry_count,
                            expected_document_ir_file_id=job.document_ir_file_id, candidate=word,
                        )
                    with patch.object(execution.word_renderer, "render_to_result") as render:
                        result = execution.execute_job(job.id)
                    render.assert_not_called()
                    self.assertEqual((result.status, result.result_file_id), ("succeeded", word.id), result.error_message)
