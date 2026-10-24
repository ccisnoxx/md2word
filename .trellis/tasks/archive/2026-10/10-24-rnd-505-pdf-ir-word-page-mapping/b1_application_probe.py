"""在B1独立进程核查停止新写入，仍完成原DOCX/预览并可读取旧manifest。"""
import hashlib
import json
from pathlib import Path
import sys

from app.domains.document_jobs import execution as execution_module
from app.domains.document_jobs import preview as preview_module
from app.services.renderer import block_anchors
from tests.test_document_job_word_preview import DocumentJobWordPreviewTests


def run():
    root = Path(sys.argv[1]).resolve()
    for module in (execution_module, preview_module, block_anchors):
        assert Path(module.__file__).resolve().is_relative_to(root), module.__file__
    case = DocumentJobWordPreviewTests()
    results = []
    for kind in ("file", "sqlite"):
        with case.runtime(kind=kind) as (runtime, execution, provider, job, user, client, headers):
            result = execution.execute_job(job.id)
            assert result.status == "succeeded", result.error_message
            assert result.word_preview_state.current_run.status == "succeeded"
            main = runtime.document_file_repository.get_document_file(result.result_file_id)
            assert main.metadata.get("block_anchor_evidence") is None
            manifest = runtime.document_file_repository.get_document_file(result.word_preview_state.current_run.manifest_file_id)
            body = json.loads(runtime.file_upload_service.read_file_content(manifest))
            assert "page_mapping" not in body
            mapping = preview_module.current_page_mapping(result, runtime.document_file_repository, runtime.file_upload_service)
            assert mapping["status"] == "unavailable" and mapping["reason_code"] == "legacy_evidence_missing"
            results.append({"backend": kind, "main": result.status, "preview": result.word_preview_state.current_run.status,
                "new_marker_proof": False, "new_mapping": False, "legacy_manifest_reader": "passed"})
    report = {"source_root": str(root), "modules": {module.__name__: {"path": module.__file__,
        "sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()}
        for module in (execution_module, preview_module, block_anchors)}, "results": results}
    Path(sys.argv[2]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": len(results), "source_root": str(root)}))


if __name__ == "__main__":
    run()
