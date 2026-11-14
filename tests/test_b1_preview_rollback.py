"""通过独立构建验证 B1 停写、产物互读与历史恢复。"""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
from xml.etree import ElementTree
from zipfile import ZipFile

from docx import Document

from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.preview_evidence import read_current_preview_evidence
from app.domains.files.models import DocumentFileRecord
from app.services.document_ir.models import DocumentIR
from app.services.preview.models import sha256
from app.services.preview.page_quality import (
    PageObservation, PageObservationBatch, PageQualityPolicy, RasterObservation, RulePolicy, policy_sha256,
)
from app.services.renderer import image_evidence
from app.services.renderer.block_anchors import ANCHOR_NAME_RE
from app.services.renderer.docx_quality import verify_docx_formula_report
from app.services.renderer.render_evidence import validate_persisted_renderer_content
from tests.document_job_list_query_v2_publication_fixtures import V2PublicationFixture, natural_package
from tests.test_image_group_rendering import neutral_png


PROJECT = Path(__file__).resolve().parents[1]
TASK = PROJECT / ".trellis/tasks/11-14-b1-preview-rollback-validation"
ARCHIVED_IMAGES = Path(".trellis/tasks/archive/2026-10/10-23-rnd-503-image-group-caption-rendering/artifact-hashes.json")
BACKENDS = ("file", "sqlite")
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_package():
    """用同一小样本覆盖正文、表格、公式和图片的认证。"""
    buffer = io.BytesIO()
    with ZipFile(io.BytesIO(natural_package(formula=True, table=True))) as source, ZipFile(buffer, "w") as output:
        blocks = json.loads(source.read("content_list_v2.json"))
        blocks.append({"type": "image", "img_path": "images/b1.png", "page_idx": 0, "bbox": [55, 430, 170, 500]})
        output.writestr("content_list_v2.json", json.dumps(blocks))
        output.writestr("middle.json", source.read("middle.json"))
        output.writestr("images/b1.png", neutral_png())
    return buffer.getvalue()


def observe_fixture(pdf, *, pages, page_count, policy, **_):
    """模拟外部页面观察，保留报告计算、持久化与认证。"""
    return PageObservationBatch(
        status="ok", input_sha256=sha256(pdf), profile_id=policy.profile_id,
        profile_sha256=policy.profile_sha256, policy_sha256=policy_sha256(policy), page_count=page_count,
        pages=tuple(
            PageObservation(
                preview_page_index=page.page_index, width_pt=72.0, height_pt=72.0,
                crop_box=(0.0, 0.0, 72.0, 72.0), rotation=0, geometry_supported=True,
                raster=RasterObservation(
                    png_sha256=sha256(page.content), width=page.width, height=page.height,
                    dpi_x=float(page.width), dpi_y=float(page.height), ink_pixels=0,
                    total_pixels=page.width * page.height, edge_ink_pixels=0, edge_pixels=1,
                ),
            )
            for page in pages
        ),
    )


def docx_anchors(content):
    with ZipFile(io.BytesIO(content)) as package:
        return {
            node.get(W_NS + "name", "")
            for path in package.namelist() if path.startswith("word/") and path.endswith(".xml")
            for node in ElementTree.fromstring(package.read(path)).iter(W_NS + "bookmarkStart")
        }


def snapshot(runtime, job, directory):
    directory.mkdir(parents=True)
    records = [
        record for record in runtime.document_file_repository.list_document_files()
        if record.status == "uploaded" and (record.job_id == job.id or record.id == job.source_file_id)
    ]
    files = []
    for index, record in enumerate(sorted(records, key=lambda item: item.file_type)):
        content = runtime.file_upload_service.read_file_content(record)
        if record.checksum_sha256 is not None and sha256(content) != record.checksum_sha256:
            raise AssertionError(f"产物与文件描述符哈希不符: {record.file_type}")
        filename = f"object-{index}"
        (directory / filename).write_bytes(content)
        files.append({"record": record.model_dump(mode="json"), "bytes": filename, "sha256": sha256(content)})
    write_json(directory / "bundle.json", {"job": job.model_dump(mode="json"), "files": files})
    return {
        "job_id": job.id,
        "files": [{"id": entry["record"]["id"], "type": entry["record"]["file_type"], "sha256": entry["sha256"]}
                  for entry in files],
    }


def load_bundle(runtime, directory):
    bundle = read_json(directory / "bundle.json")
    job = DocumentJobRecord.model_validate(bundle["job"])
    for entry in bundle["files"]:
        record = DocumentFileRecord.model_validate(entry["record"])
        content = (directory / entry["bytes"]).read_bytes()
        if sha256(content) != entry["sha256"]:
            raise AssertionError(f"冻结样本字节变化: {record.file_type}")
        path = runtime.file_upload_service.resolve_file_object_path(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        runtime.document_file_repository.create_document_file(record)
    runtime.document_job_repository.create_document_job(job)
    return job


def restored_state(runtime, job):
    return (
        runtime.document_job_repository.get_document_job(job.id),
        [(record, sha256(runtime.file_upload_service.read_file_content(record)))
         for record in runtime.document_file_repository.list_document_files()],
    )


def mutate_manifest(runtime, run, variant):
    files = runtime.document_file_repository
    manifest = files.get_document_file(run.manifest_file_id)
    path = runtime.file_upload_service.resolve_file_object_path(manifest)
    if variant == "outer_damage":
        path.write_bytes(path.read_bytes() + b" ")
        return
    body = read_json(path)
    if variant == "legacy_shape":
        body.pop("page_mapping")
        body.pop("page_quality_run")
    else:
        body["page_mapping"]["mapping_sha256"] = "0" * 64
    write_json(path, body)
    content = path.read_bytes()
    files.update_document_file(manifest.id, size_bytes=len(content), checksum_sha256=sha256(content))


def inspect_docx(case, runtime, job, producer):
    repository = runtime.document_file_repository
    service = runtime.file_upload_service
    result = repository.get_document_file(job.result_file_id)
    document = service.read_file_content(result)
    ir_record = repository.get_document_file(result.metadata["document_ir_file_id"])
    ir = DocumentIR.model_validate_json(service.read_file_content(ir_record))
    validate_persisted_renderer_content(ir, document, result.metadata,
                                        expected_template_version_id=job.template_version_id)
    names = docx_anchors(document)
    case.assertEqual(any(ANCHOR_NAME_RE.fullmatch(name) for name in names), producer == "normal")
    case.assertEqual("block_anchor_evidence" in result.metadata, producer == "normal")
    if producer == "b1":
        case.assertEqual(result.metadata["block_anchor_summary"]["generation_disabled"], 1)
    case.assertTrue(result.metadata["formula_report"]["entries"])
    case.assertTrue(any(name.startswith("md2w_formula_") for name in names))
    case.assertTrue(Document(io.BytesIO(document)).inline_shapes)
    case.assertTrue(result.metadata["image_layout_report"])


class Probe(V2PublicationFixture, TestCase):
    def produce(self, producer, kind, destination):
        with self.runtime(kind=kind, pages=True, source_package=source_package()) as (
            runtime, execution, provider, job, _, _, _,
        ):
            job = self.install_publication_resources(runtime, execution, job)
            policy = PageQualityPolicy(enabled=True)
            rules = {**policy.rules, "blank": RulePolicy(enabled=True, thresholds={
                "max_ink_ratio": 0.01, "max_foreground_count": 0,
            })}
            policy = PageQualityPolicy(enabled=True, rules=rules)
            job = runtime.document_job_repository.update_document_job(job.id, request_snapshot={
                **job.request_snapshot, "page_quality": policy.model_dump(mode="json"),
            })
            preview_service = execution.rendering.results.word_preview_service
            with patch.object(preview_service, "observer", Mock(observe=observe_fixture)):
                result = execution.execute_job(job.id)
            self.assertEqual(result.status, "succeeded", result.error_message)
            self.assertEqual(result.word_preview_state.current_run.status, "succeeded")
            self.assertEqual(len(provider.inputs), 1)
            inspect_docx(self, runtime, result, producer)
            evidence = read_current_preview_evidence(result, runtime.document_file_repository,
                                                    runtime.file_upload_service, include_mapping=True,
                                                    include_page_quality=True)
            self.assertTrue(evidence.observation.available)
            self.assertEqual("page_mapping" in evidence.manifest, producer == "normal")
            self.assertEqual(evidence.page_mapping["status"], "available" if producer == "normal" else "unavailable")
            report = evidence.page_quality_run
            self.assertIsNotNone(report)
            self.assertEqual(report, evidence.manifest["page_quality_run"])
            self.assertIsNotNone(report["binding"]["actual_context_sha256"])
            self.assertEqual(report["binding"]["mapping_sha256"],
                             evidence.manifest.get("page_mapping", {}).get("mapping_sha256"))
            self.assertEqual((report["counts"]["observed_pages"], report["evaluation_state"], report["quality_status"]),
                             (1, "incomplete", "pending"))
            self.assertEqual(report["pages"][0]["rules"]["blank"]["reason_code"], "uncalibrated")
            return {"producer": producer, "backend": kind, "page_quality": report["evaluation_state"],
                    **snapshot(runtime, result, destination)}

    def consume(self, reader, producer, kind, samples, root, variant):
        runtime = self._build_runtime(root, kind)
        job = load_bundle(runtime, samples / producer / kind)
        if variant != "unchanged":
            mutate_manifest(runtime, job.word_preview_state.current_run, variant)
        before = restored_state(runtime, job)
        inspect_docx(self, runtime, job, producer)
        if variant == "outer_damage":
            with self.assertRaisesRegex(ValueError, "预览Artifact字节与描述符不一致"):
                read_current_preview_evidence(job, runtime.document_file_repository, runtime.file_upload_service,
                                              include_mapping=True, include_page_quality=True)
            mapping, quality = "outer_rejected", "not_read"
        else:
            evidence = read_current_preview_evidence(job, runtime.document_file_repository, runtime.file_upload_service,
                                                    include_mapping=True, include_page_quality=True)
            self.assertTrue(evidence.observation.available)
            if variant == "legacy_shape" or producer == "b1":
                self.assertEqual(evidence.page_mapping["reason_code"], "legacy_evidence_missing")
            elif variant == "inner_damage":
                self.assertEqual(evidence.page_mapping["reason_code"], "invalid_mapping")
            else:
                self.assertEqual(evidence.page_mapping, evidence.manifest["page_mapping"])
                self.assertEqual(evidence.page_mapping["status"], "available")
            mapping = evidence.page_mapping["reason_code"] or "available"
            if variant != "unchanged" or (reader, producer) == ("normal", "b1"):
                self.assertIsNone(evidence.page_quality_run)
                quality = "unavailable"
            else:
                self.assertIsNotNone(evidence.page_quality_run)
                self.assertEqual(evidence.page_quality_run, evidence.manifest["page_quality_run"])
                quality = "authenticated"
        self.assertEqual(restored_state(runtime, job), before)
        return {"reader": reader, "producer": producer, "backend": kind, "variant": variant,
                "preview": variant != "outer_damage", "mapping": mapping, "page_quality": quality}


def check_archived_word(directory):
    paths = [directory / filename for filename in (
        "b1-generated.docx", "b1-generated.ir.json", "b1-generated.reports.json",
    )]
    if not all(path.is_file() for path in paths):
        return {"status": "unavailable", "reason": "本机历史样本不完整"}
    manifest = read_json(PROJECT / ARCHIVED_IMAGES)
    expected = {
        name.rsplit("/", 1)[-1]: digest
        for entry in manifest for name, digest in entry["files"].items()
        if "/tests/tmp/rnd503/b1/" in name
    }
    observed = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    if observed != {name: expected[name] for name in observed}:
        raise AssertionError("历史 DOCX、IR 或报告字节与归档指纹不符")
    word, ir_path, reports_path = paths
    content, reports = word.read_bytes(), read_json(reports_path)
    ir = DocumentIR.model_validate_json(ir_path.read_bytes())
    verify_docx_formula_report(content, reports["formula_report"])
    image_report = reports["image_layout_report"]
    from app.services.renderer.render_plan import document_ir_hash

    raw_ir_hash = image_evidence.canonical_sha256(read_json(ir_path))
    if raw_ir_hash != image_report["source_ir_sha256"]:
        raise AssertionError("归档图片报告与冻结的原始 IR 不匹配")
    try:
        image_evidence.verify_image_report(ir, content, image_report, _legacy_ir_identity=True)
    except ValueError as error:
        # 补充历史样本与本任务的新产物矩阵分别报告。
        if str(error) != "图片布局证据无效：原始 IR 绑定":
            raise
        image_status = "ir_binding_rejected"
    else:
        image_status = "authenticated"
    return {"sample": "RND-503 原始离线 DOCX／IR／报告", "sha256": observed,
            "formula": "authenticated", "image": image_status, "preview_manifest": "unavailable",
            "archived_ir_sha256": raw_ir_hash, "reader_legacy_ir_sha256": document_ir_hash(ir, legacy=True)}


def run_probe(source_root, expected, mode, phase, root, archived_word):
    case = Probe()
    samples = root / "samples"
    if phase == "produce":
        result = [case.produce(mode, kind, samples / mode / kind) for kind in BACKENDS]
    else:
        rows = []
        for kind in BACKENDS:
            cases = (("normal", "unchanged"), ("normal", "legacy_shape"), ("normal", "inner_damage"),
                     ("normal", "outer_damage")) if mode == "b1" else (("b1", "unchanged"),)
            for producer, variant in cases:
                rows.append(case.consume(mode, producer, kind, samples,
                                         root / "read" / mode / kind / variant, variant))
        result = {"interop": rows, "archived_word": check_archived_word(archived_word)}
        if mode == "b1":
            from tests.b1_preview_recovery import check_recovery

            result["recovery"] = check_recovery(case, root / "recovery", samples)
    loaded = {}
    for name, module in tuple(sys.modules.items()):
        if name != "app" and not name.startswith("app."):
            continue
        path = getattr(module, "__file__", None)
        if path is None:
            continue
        relative = Path(path).resolve().relative_to(source_root).as_posix()
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if expected.get(relative) != digest:
            raise AssertionError(f"实际加载的模块不在构建清单或指纹不符: {relative}")
        loaded[relative] = digest
    required = {
        "app/services/renderer/block_anchors.py", "app/services/renderer/render_evidence.py",
        "app/domains/document_jobs/preview.py", "app/domains/document_jobs/preview_evidence.py",
    }
    if not required <= loaded.keys():
        raise AssertionError("未观察到所有关键模块的加载")
    write_json(root / f"{mode}-{phase}.json", {"loaded_app_sha256": loaded, "result": result})


PROBE_ENTRY = """
import json
import sys
from pathlib import Path
source, project, mode, phase, root = sys.argv[1:]
source, project, root = (Path(value).resolve() for value in (source, project, root))
sys.path.insert(0, str(source))
import tests
tests.__path__.insert(0, str(project / 'tests'))
from tests.test_b1_preview_rollback import run_probe
fingerprints = json.loads((source.parent / 'fingerprints.json').read_text())
key = 'normal_app_sha256' if mode == 'normal' else 'candidate_app_sha256'
run_probe(source, fingerprints[key], mode, phase, root, project / 'tests/tmp/rnd503/b1')
"""


class B1PreviewRollbackTests(TestCase):
    def test_b1_candidate_build_and_offline_matrix(self):
        with TemporaryDirectory(prefix="md2word-b1-") as temporary:
            root = Path(temporary)
            builds = []
            for name in ("build", "rebuilt"):
                output = root / name
                subprocess.run([sys.executable, str(TASK / "build_candidate.py"), "--output", str(output)],
                               check=True, cwd=PROJECT, timeout=120)
                builds.append(read_json(output / "fingerprints.json"))
            self.assertEqual(builds[0], builds[1])
            fingerprints = builds[0]
            results = {}
            for mode, phase in (("normal", "produce"), ("b1", "produce"), ("b1", "consume"), ("normal", "consume")):
                source = root / "build" / mode
                invocation = subprocess.run([sys.executable, "-I", "-B", "-c", PROBE_ENTRY,
                                             str(source), str(PROJECT), mode, phase, str(root)],
                                            cwd=source, capture_output=True, text=True, timeout=180)
                self.assertEqual(invocation.returncode, 0, invocation.stdout + invocation.stderr)
                results[f"{mode}-{phase}"] = read_json(root / f"{mode}-{phase}.json")
            self.assertEqual(len(results["b1-consume"]["result"]["recovery"]), 30)
            results["test_inputs_sha256"] = {
                name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()
                for name in ("tests/test_b1_preview_rollback.py", "tests/b1_preview_recovery.py")
            }
            report = os.environ.get("B1_PREVIEW_ROLLBACK_EVIDENCE")
            if report:
                destination = Path(report)
                destination.mkdir(parents=True, exist_ok=True)
                write_json(destination / "fingerprints.json", fingerprints)
                write_json(destination / "offline-results.json", results)
