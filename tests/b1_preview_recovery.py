"""在候选进程中用主干冻结对象重放三条历史恢复入口。"""

from itertools import product
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.preview_evidence import read_current_preview_evidence
from app.domains.files.models import DocumentFileRecord
from app.main import create_app
from app.services.preview.models import sha256
from tests.test_fastapi_jobs_backend import build_auth_header


_ADAPTERS = ("file", "sqlite")
_ENTRIES = ("legacy_discovery", "explicit_pointer", "prepared_receipt")
_VARIANTS = {
    "valid": None,
    "optional_missing": None,
    "optional_invalid": None,
    "docx_corrupt": ("uploading", "oss_failed"),
    "mandatory_missing": ("quality_checking", "render_failed"),
}
_PRIVATE_PROBE = "B1_PRIVATE_PROOF_PROBE"
_PRIVATE_VALUES = (
    '"block_anchor_evidence"',
    '"block_render_evidence"',
    '"render_plan"',
    '"page_mapping"',
    '"formula_source_coverage"',
    _PRIVATE_PROBE,
)


def _import_objects(case, runtime, sample: Path, bundle: dict, original, entry: str, variant: str):
    records = {}
    hashes = {}
    for exported in bundle["files"]:
        record = DocumentFileRecord.model_validate(exported["record"])
        content = (sample / exported["bytes"]).read_bytes()
        case.assertEqual(len(content), record.size_bytes)
        if record.checksum_sha256 is not None:
            case.assertEqual(sha256(content), record.checksum_sha256)
        if record.id == original.result_file_id:
            metadata = record.metadata.copy()
            case.assertEqual(metadata["renderer_content_contract_version"], "renderer-content/v2")
            case.assertIn("block_anchor_evidence", metadata)
            case.assertIn("formula_source_coverage", metadata)
            if entry == "legacy_discovery":
                # 旧发现入口只接受尚无结果协议标记的登记，冻结主件和预览的实物字节照常复用。
                del metadata["document_job_result_protocol"]
            if variant == "optional_missing":
                del metadata["block_anchor_evidence"]
            elif variant == "optional_invalid":
                metadata["block_anchor_evidence"] = {
                    **metadata["block_anchor_evidence"],
                    "evidence_sha256": "0" * 64,
                    "private_probe": _PRIVATE_PROBE,
                }
            elif variant == "docx_corrupt":
                content += b"B1_DOCX_CORRUPTION"
            elif variant == "mandatory_missing":
                del metadata["formula_source_coverage"]
            record = record.model_copy(update={"metadata": metadata})
        path = runtime.file_upload_service.resolve_file_object_path(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        records[record.id] = runtime.document_file_repository.create_document_file(record)
        hashes[record.id] = sha256(content)
    return records, hashes


def _check_public_projection(case, runtime, result):
    client = TestClient(create_app(runtime))
    try:
        headers = build_auth_header(client)
        for suffix in ("", "/files", "/events"):
            response = client.get(f"/api/v1/document-jobs/{result.id}{suffix}", headers=headers)
            case.assertEqual(response.status_code, 200, suffix)
            for private_value in _PRIVATE_VALUES:
                case.assertNotIn(private_value, response.text, suffix)
    finally:
        client.close()
    for private_value in _PRIVATE_VALUES:
        case.assertNotIn(private_value.strip('"'), result.error_message or "")


def _check_entry(case, root, sample, adapter, entry, variant):
    bundle = json.loads((sample / "bundle.json").read_text(encoding="utf-8"))
    original = DocumentJobRecord.model_validate(bundle["job"])
    runtime = case._build_runtime(root, adapter)
    files = runtime.document_file_repository
    file_service = runtime.file_upload_service
    jobs = runtime.document_job_repository
    execution = runtime.document_job_execution_service
    records, before = _import_objects(case, runtime, sample, bundle, original, entry, variant)
    word = records[original.result_file_id]
    manifest_id = original.word_preview_state.current_run.manifest_file_id
    frozen_manifest = json.loads(file_service.read_file_content(records[manifest_id]))
    case.assertIn(frozen_manifest["page_mapping"]["status"], {"available", "degraded"})
    receipt = None
    if entry == "prepared_receipt":
        receipt = original.prepared_result
        if word.metadata != receipt.file.metadata:
            # 负例同步修改选定描述的证据字段，保留历史凭据的其余字段。
            receipt = receipt.model_copy(update={"file": receipt.file.model_copy(update={"metadata": word.metadata})})
    replay = DocumentJobRecord.model_validate({
        **original.model_dump(),
        "status": "running",
        "stage": "uploading",
        "completed_at": None,
        "timeout_at": None,
        "result_file_id": word.id if entry == "explicit_pointer" else None,
        "prepared_result": receipt,
    })
    jobs.create_document_job(replay)
    case.assertEqual(jobs.get_document_job(replay.id), replay)
    files_before = {item.id: item for item in files.list_document_files()}
    with (
        patch.object(execution.rendering, "_resolve_render_resources",
                     side_effect=AssertionError("恢复重新解析了渲染资源")) as resolve,
        patch.object(execution.rendering.word_renderer, "render_to_result",
                     side_effect=AssertionError("恢复重新渲染了 Word")) as render,
        patch.object(execution.rendering.results.word_preview_service.provider, "render",
                     side_effect=AssertionError("恢复重新生成了预览")) as preview,
    ):
        result = execution.execute_job(replay.id)
    resolve.assert_not_called()
    render.assert_not_called()
    preview.assert_not_called()
    label = f"{adapter}/{entry}/{variant}"
    case.assertIsNotNone(result, label)
    case.assertEqual(result, jobs.get_document_job(replay.id), label)
    case.assertEqual(result.word_preview_state, original.word_preview_state, label)
    case.assertEqual(result.document_ir_file_id, original.document_ir_file_id, label)
    case.assertEqual(result.retry_count, original.retry_count, label)

    expected_error = _VARIANTS[variant]
    mapping = None
    if expected_error:
        case.assertEqual(result.status, "failed", label)
        case.assertEqual((result.failed_stage, result.error_code), expected_error, label)
        case.assertEqual(result.result_file_id, replay.result_file_id, label)
        case.assertEqual(result.prepared_result, receipt, label)
    else:
        case.assertEqual((result.status, result.stage), ("succeeded", "completed"),
                         f"{label} · {result.error_message}")
        case.assertEqual(result.result_file_id, word.id, label)
        if entry == "explicit_pointer":
            # 显式指针入口沿用历史状态，不创建预览授权所需的 receipt。
            case.assertIsNone(result.prepared_result, label)
        else:
            expected_receipt = receipt if receipt is not None else original.prepared_result.model_copy(update={"file": word})
            case.assertEqual(result.prepared_result, expected_receipt, label)
            current = read_current_preview_evidence(result, files, file_service, include_mapping=True)
            case.assertTrue(current.observation.available, label)
            case.assertEqual(current.manifest, frozen_manifest, label)
            mapping = current.page_mapping
            if variant == "valid":
                case.assertEqual(mapping, frozen_manifest["page_mapping"], label)
            else:
                case.assertEqual((mapping["status"], mapping["reason_code"]), ("unavailable", "invalid_mapping"), label)

    _check_public_projection(case, runtime, result)
    case.assertEqual({item.id: item for item in files.list_document_files()}, files_before, label)
    after = {file_id: sha256(file_service.read_file_content(record)) for file_id, record in records.items()}
    case.assertEqual(after, before, label)
    return {
        "adapter": adapter,
        "entry": entry,
        "variant": variant,
        "status": result.status,
        "failed_stage": result.failed_stage,
        "error_code": result.error_code,
        "result_file_id": result.result_file_id,
        "receipt_file_id": result.prepared_result.file.id if result.prepared_result else None,
        "preview": "available" if mapping is not None else "preserved",
        "mapping_status": mapping["status"] if mapping is not None else None,
        "mapping_reason": mapping["reason_code"] if mapping is not None else None,
        "artifacts": {
            role: {
                "id": file_id,
                "record_sha256": records[file_id].checksum_sha256,
                "before_sha256": before[file_id],
                "after_sha256": after[file_id],
            }
            for role, file_id in (
                ("docx", word.id), ("ir", original.document_ir_file_id), ("manifest", manifest_id)
            )
        },
    }


def check_recovery(case, root: Path, samples: Path) -> list[dict]:
    """用同一候选核验文件和 SQLite 上各入口的保留、降级与拒绝行为。"""

    return [
        _check_entry(case, root / adapter / entry / variant, samples / "normal" / adapter, adapter, entry, variant)
        for adapter, entry, variant in product(_ADAPTERS, _ENTRIES, _VARIANTS)
    ]
