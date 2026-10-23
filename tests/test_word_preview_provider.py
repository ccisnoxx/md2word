"""端口预算与生产 adapter 的正式 tests-only 子进程协议符合性。"""

from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
import zipfile
import zlib

from pydantic import ValidationError

from app.core.config import Settings
from app.services.document_ir.models import DocumentIR, DocumentIRBlock, DocumentIRMetadata
from app.services.renderer import DocumentIRWordRenderer
from app.services.preview.models import (
    PreviewFailure, PreviewPage, PreviewPolicy, PreviewResult, png_dimensions, sha256, validate_docx, validate_result,
)
from app.services.preview.sandbox_adapter import SandboxWordPreviewProvider


def formal_docx():
    document = DocumentIR(metadata=DocumentIRMetadata(job_id="test", source_file_id="source", document_language="en"),
                          blocks=[DocumentIRBlock(id="text", type="paragraph", order=0, text="Word preview")])
    return DocumentIRWordRenderer().render_to_bytes(document, template_path=None, config_path=None, image_loader=lambda _: None)


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


# 固定脚本实现正式 argv/JSON，不作为 Settings backend，也不代表实际 DOCX 排版或沙箱。
EXECUTOR = r'''
import hashlib, json, os, pathlib, subprocess, sys, time
root = pathlib.Path.cwd()
args = sys.argv[1:]
assert args[0] in {"describe", "render"} and args[1:3] == ["--protocol", "word-preview-exec/v1"]
assert "RND504_SECRET" not in os.environ
profile_raw = pathlib.Path(__file__).with_suffix(".json").read_bytes()
profile = json.loads(profile_raw)
mode = profile["test_mode"]
result_path = pathlib.Path(args[args.index("--result") + 1])
base = {"protocol_version": "word-preview-exec/v1", "profile_id": profile["profile_id"],
        "profile_sha256": "sha256:" + hashlib.sha256(profile_raw).hexdigest(),
        "provider_id": "test-executor", "provider_version": "1.0"}
if args[0] == "describe":
    if mode == "describe_fifo":
        os.mkfifo(result_path); sys.exit(0)
    base.update(engine_version="test-only", validator_version="test-only", pdf_full_decode=mode != "no_decoder", png_decode=True)
    if mode == "describe_profile": base["profile_sha256"] = "sha256:" + "1" * 64
    result_path.write_text(json.dumps(base)); sys.exit(0)
request = json.loads(pathlib.Path(args[args.index("--request") + 1]).read_text())
assert set(request) == {"protocol_version", "input", "profile_id", "profile_sha256", "render_pages", "budget_ms", "limits"}
assert request["input"]["path"] == "source.docx" and request["budget_ms"] > 0
assert request["input"]["sha256"] == "sha256:" + hashlib.sha256((root / "source.docx").read_bytes()).hexdigest()
assert request["profile_sha256"] == base["profile_sha256"]
base.update(input_sha256=request["input"]["sha256"])
if mode == "unknown_exit": sys.exit(71)
if mode == "timeout":
    subprocess.Popen([sys.executable, "-c", "import pathlib,time; time.sleep(.6); pathlib.Path(" + repr(profile["sentinel"]) + ").write_text('alive')"])
    time.sleep(30)
if mode.startswith("exit_"):
    exit_code = int(mode.split("_")[1])
    code = {20:"preview_input_invalid", 21:"preview_resource_exceeded", 22:"preview_sandbox_unavailable",
            23:"preview_output_invalid", 24:"preview_engine_failed", 25:"preview_engine_failed"}[exit_code]
    base.update(status="error", error_code=code)
    result_path.write_text(json.dumps(base)); sys.exit(exit_code)
if mode == "result_fifo": os.mkfifo(result_path); sys.exit(0)
if mode == "bad_json": result_path.write_text("{}"); sys.exit(0)
pdf = bytes.fromhex(profile["test_pdf"])
pdf_path = root / "out/preview.pdf"
pdf_path.write_bytes(pdf)
def descriptor(path, mime):
    data = path.read_bytes()
    return {"path": str(path.relative_to(root)), "mime_type": mime, "sha256":"sha256:"+hashlib.sha256(data).hexdigest(), "size_bytes":len(data)}
base.update(status="ok", page_count=1, pdf=descriptor(pdf_path,"application/pdf"), pages=[])
if request["render_pages"]:
    page = root / "out/page-000000.png"
    page.write_bytes(bytes.fromhex(profile["test_png"]))
    base["pages"] = [dict(descriptor(page, "image/png"), page_index=0, width=1, height=1)]
if mode == "bad_hash": base["pdf"]["sha256"] = "sha256:" + "1"*64
if mode == "bad_source": base["input_sha256"] = "sha256:" + "1"*64
if mode == "bad_profile": base["profile_sha256"] = "sha256:" + "1"*64
if mode == "bad_provider": base["provider_version"] = "2.0"
if mode == "bad_path": base["pdf"]["path"] = "../preview.pdf"
if mode == "absolute_path": base["pdf"]["path"] = str(pdf_path)
if mode == "bad_mime": base["pdf"]["mime_type"] = "text/plain"
if mode == "bad_count": base["page_count"] = 0
if mode == "bad_page_index" and base["pages"]: base["pages"][0]["page_index"] = 1
if mode == "missing_page": base["pages"] = []
if mode == "bad_dimensions" and base["pages"]: base["pages"][0]["width"] = 2
if mode == "pdf_fifo": pdf_path.unlink(); os.mkfifo(pdf_path)
if mode == "symlink": pdf_path.unlink(); pdf_path.symlink_to(root / "source.docx")
if mode == "hardlink": pdf_path.rename(root / "shared.pdf"); os.link(root / "shared.pdf", pdf_path)
if mode == "source_changed": (root / "source.docx").chmod(0o600); (root / "source.docx").write_bytes(b"changed")
if mode == "temp_limit": (root / "oversize").write_bytes(b"x" * request["limits"]["max_temp_bytes"])
result_path.write_text(json.dumps(base))
'''


@contextmanager
def executor(mode="ok", *, render_pages=False, policy_patch=None, profile_patch=None):
    with TemporaryDirectory(prefix="rnd504-protocol-") as directory:
        root = Path(directory)
        launcher = root / "executor.py"
        launcher.write_text("#!" + sys.executable + "\n" + EXECUTOR)
        launcher.chmod(0o700)
        policy = PreviewPolicy(backend="sandboxed", profile_id="test-only", render_pages=render_pages,
                               **(policy_patch or {}))
        profile = {"protocol_version": "word-preview-exec/v1", "profile_id": policy.profile_id,
                   "launcher_sha256": sha256(launcher.read_bytes()), "approval_reference": "tests-only",
                   "sandbox": {name: True for name in ("no_network", "no_macros", "private_mount", "unprivileged", "resource_limits", "terminate_domain")},
                   "limits": {name: getattr(policy, name) for name in ("max_temp_bytes", "max_cpu_seconds", "max_memory_bytes", "max_processes")},
                   "test_mode": mode, "test_pdf": pdf_bytes().hex(), "test_png": png_bytes().hex(),
                   "sentinel": str(root / "late-child"), **(profile_patch or {})}
        path = launcher.with_suffix(".json")
        path.write_text(json.dumps(profile))
        policy = policy.model_copy(update={"profile_sha256": sha256(path.read_bytes())})
        attempts = root / "attempts"
        attempts.mkdir()
        adapter = SandboxWordPreviewProvider(backend="sandboxed", launcher=str(launcher), profile_path=str(path),
            profile_id=policy.profile_id, profile_sha256=policy.profile_sha256, temp_root=str(attempts))
        yield adapter, policy, root
        assert not list(attempts.iterdir()), "预览临时目录未清理"


class WordPreviewProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docx = formal_docx()

    def test_defaults_are_disabled_and_snapshot_has_no_paths(self):
        settings = Settings(_env_file=None, word_preview_launcher="/private/launcher", word_preview_profile_path="/private/profile")
        self.assertEqual(settings.word_preview_backend, "disabled")
        self.assertNotIn("/private", settings.word_preview_policy().model_dump_json())
        with self.assertRaises(PreviewFailure) as error:
            SandboxWordPreviewProvider().render(self.docx, policy=settings.word_preview_policy())
        self.assertEqual(error.exception.code, "preview_disabled")

    def test_input_zip_crc_xml_active_content_and_budgets(self):
        validate_docx(self.docx, PreviewPolicy())
        for data, code in ((b"", "preview_input_invalid"), (b"bad", "preview_input_invalid"),
                           (self.docx, "preview_resource_exceeded")):
            with self.subTest(code=code, size=len(data)), self.assertRaises(PreviewFailure) as error:
                validate_docx(data, PreviewPolicy(max_input_bytes=10))
            self.assertEqual(error.exception.code, code)
        for name, data in (("word/vbaProject.bin", b"bad"), ("word/embeddings/ole.bin", b"bad"),
                           ("word/document.xml", b"<!DOCTYPE x><x/>"), ("word/document.xml", b"bad")):
            stream = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(self.docx)) as old, zipfile.ZipFile(stream, "w") as package:
                for item in old.infolist():
                    if item.filename != name:
                        package.writestr(item.filename, old.read(item))
                package.writestr(name, data)
            with self.subTest(name=name, data=data), self.assertRaises(PreviewFailure):
                validate_docx(stream.getvalue(), PreviewPolicy())

    def test_input_zip_crc_expansion_ratio_and_missing_required_part(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as package:
            package.writestr("[Content_Types].xml", "<Types/>")
            package.writestr("word/document.xml", "<document/>")
            package.writestr("_rels/.rels", "<Relationships/>")
        valid = buffer.getvalue()
        validate_docx(valid, PreviewPolicy())
        corrupt = bytearray(valid)
        corrupt[corrupt.index(b"<document/>")] = ord("X")
        with self.assertRaises(PreviewFailure) as error: validate_docx(bytes(corrupt), PreviewPolicy())
        self.assertEqual(error.exception.code, "preview_input_invalid")
        compressed = io.BytesIO()
        with zipfile.ZipFile(compressed, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr("huge.bin", b"0" * 200000)
        with self.assertRaises(PreviewFailure) as error: validate_docx(compressed.getvalue(), PreviewPolicy())
        self.assertEqual(error.exception.code, "preview_resource_exceeded")
        missing = io.BytesIO()
        with zipfile.ZipFile(missing, "w") as package: package.writestr("word/document.xml", "<document/>")
        with self.assertRaises(PreviewFailure) as error: validate_docx(missing.getvalue(), PreviewPolicy())
        self.assertEqual(error.exception.code, "preview_input_invalid")

    def test_input_rejects_utf16_macro_content_types_and_renamed_active_parts(self):
        contents = """<?xml version="1.0" encoding="UTF-16"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Override PartName="/word/document.xml" ContentType="application/vnd.ms-word.document.macroEnabled.main+xml"/>
<Override PartName="/word/custom.bin" ContentType="application/vnd.ms-office.vbaProject"/>
</Types>"""
        relationships = """<?xml version="1.0" encoding="UTF-16"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="active" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="custom.bin"/>
</Relationships>"""
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.docx)) as original, zipfile.ZipFile(output, "w") as package:
            for item in original.infolist():
                if item.filename not in {"[Content_Types].xml", "word/_rels/document.xml.rels"}:
                    package.writestr(item.filename, original.read(item))
            package.writestr("[Content_Types].xml", contents.encode("utf-16"))
            package.writestr("word/_rels/document.xml.rels", relationships.encode("utf-16"))
            package.writestr("word/custom.bin", b"test-only-active-content")
        with self.assertRaises(PreviewFailure) as error:
            validate_docx(output.getvalue(), PreviewPolicy())
        self.assertEqual(error.exception.code, "preview_input_invalid")

    def test_input_xml_semantics_rejects_each_active_declaration_and_keeps_hyperlinks(self):
        def replace_parts(replacements):
            output = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(self.docx)) as original, zipfile.ZipFile(output, "w") as package:
                for item in original.infolist():
                    if item.filename not in replacements: package.writestr(item.filename, original.read(item))
                for name, content in replacements.items(): package.writestr(name, content)
            return output.getvalue()

        for content_type in ("application/vnd.ms-word.document.macroEnabled.main+xml", "application/vnd.ms-office.vbaProject", "application/vnd.ms-office.activeX+xml", "application/vnd.openxmlformats-officedocument.oleObject"):
            types = ('<?xml version="1.0" encoding="UTF-16"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Override PartName="/word/custom.bin" ContentType="' + content_type + '"/></Types>')
            with self.subTest(content_type=content_type), self.assertRaises(PreviewFailure) as error:
                validate_docx(replace_parts({"[Content_Types].xml": types.encode("utf-16"), "word/custom.bin": b"test-only"}), PreviewPolicy())
            self.assertEqual(error.exception.code, "preview_input_invalid")
        for kind in ("vbaProject", "vbaProjectSignature", "oleObject", "activeX", "control", "package"):
            relationship = ('<?xml version="1.0" encoding="UTF-16"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                            '<Relationship Id="custom" Type="http://schemas.microsoft.com/office/2006/relationships/' + kind + '" Target="custom.bin"/></Relationships>')
            with self.subTest(relationship=kind), self.assertRaises(PreviewFailure) as error:
                validate_docx(replace_parts({"word/_rels/document.xml.rels": relationship.encode("utf-16"), "word/custom.bin": b"test-only"}), PreviewPolicy())
            self.assertEqual(error.exception.code, "preview_input_invalid")
        normal_link = ('<?xml version="1.0" encoding="UTF-16"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="link" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.invalid/vbaProject" TargetMode="External"/></Relationships>')
        validate_docx(replace_parts({"word/_rels/document.xml.rels": normal_link.encode("utf-16")}), PreviewPolicy())
        dtd = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE document [<!ENTITY x "test">]><document>&x;</document>'
        with self.assertRaises(PreviewFailure) as error:
            validate_docx(replace_parts({"word/document.xml": dtd.encode("utf-16")}), PreviewPolicy())
        self.assertEqual(error.exception.code, "preview_input_invalid")

    def test_result_pages_and_resource_contract(self):
        for pages in (False, True):
            policy = PreviewPolicy(render_pages=pages)
            validate_result(preview_result(policy), policy)
        with self.assertRaises(ValidationError):
            PreviewResult(pdf=pdf_bytes(), page_count=0, provider_id="test", provider_version="1", profile_sha256=PreviewPolicy().profile_sha256)
        for result, policy, expected in (
            (preview_result(PreviewPolicy()).model_copy(update={"page_count": 0}), PreviewPolicy(), "preview_output_invalid"),
            (preview_result(PreviewPolicy()).model_copy(update={"pdf": b""}), PreviewPolicy(), "preview_output_invalid"),
            (preview_result(PreviewPolicy()), PreviewPolicy(max_output_bytes=1), "preview_resource_exceeded"),
            (preview_result(PreviewPolicy()), PreviewPolicy(render_pages=True), "preview_output_invalid"),
            (preview_result(PreviewPolicy(render_pages=True)), PreviewPolicy(), "preview_output_invalid"),
        ):
            with self.subTest(expected=expected), self.assertRaises(PreviewFailure) as error:
                validate_result(result, policy)
            self.assertEqual(error.exception.code, expected)
        png = png_bytes(2, 2)
        self.assertEqual(png_dimensions(png, max_pixels=4), (2, 2))
        with self.assertRaises(PreviewFailure): png_dimensions(png, max_pixels=3)
        with self.assertRaises(PreviewFailure): png_dimensions(png[:-1], max_pixels=4)

    def test_formal_subprocess_success_with_and_without_pages(self):
        for pages in (False, True):
            with self.subTest(pages=pages), executor(render_pages=pages) as (adapter, policy, root), patch.dict(os.environ, {"RND504_SECRET": "not-inherited"}):
                output = adapter.render(self.docx, policy=policy)
                self.assertEqual(output.pdf, pdf_bytes())
                self.assertEqual(output.page_count, 1)
                self.assertEqual(len(output.pages), int(pages))
                self.assertFalse(list((root / "attempts").iterdir()))

    def test_formal_subprocess_exit_error_mapping(self):
        for exit_code, code in ((20,"preview_input_invalid"), (21,"preview_resource_exceeded"), (22,"preview_sandbox_unavailable"),
                                (23,"preview_output_invalid"), (24,"preview_engine_failed"), (25,"preview_engine_failed"),
                                (71,"preview_unexpected_error")):
            mode = f"exit_{exit_code}" if exit_code != 71 else "unknown_exit"
            with self.subTest(exit_code=exit_code), executor(mode) as (adapter, policy, root), self.assertRaises(PreviewFailure) as error:
                adapter.render(self.docx, policy=policy)
            self.assertEqual(error.exception.code, code)
            self.assertEqual(error.exception.retryable, exit_code == 25)

    def test_formal_subprocess_rejects_schema_identity_path_fifo_and_invalid_pages(self):
        for mode in ("bad_json", "bad_hash", "bad_source", "bad_profile", "bad_provider", "bad_path", "absolute_path",
                     "bad_mime", "bad_count", "bad_page_index", "missing_page", "bad_dimensions", "pdf_fifo", "result_fifo", "symlink", "hardlink", "source_changed", "describe_fifo"):
            with self.subTest(mode=mode), executor(mode, render_pages=True) as (adapter, policy, root), self.assertRaises(PreviewFailure):
                adapter.render(self.docx, policy=policy)

    def test_formal_subprocess_timeout_terminates_group_and_cleans(self):
        with executor("timeout", policy_patch={"timeout_seconds": 0.15}) as (adapter, policy, root):
            started = time.monotonic()
            with self.assertRaises(PreviewFailure) as error: adapter.render(self.docx, policy=policy)
            self.assertEqual(error.exception.code, "preview_timeout")
            self.assertTrue(error.exception.retryable)
            self.assertLess(time.monotonic() - started, 2)
            time.sleep(0.7)
            self.assertFalse((root / "late-child").exists())
            self.assertFalse(list((root / "attempts").iterdir()))

    def test_formal_subprocess_requires_approval_decoder_profile_and_temp_budget(self):
        for mode, patch_profile, patch_policy, expected in (
            ("ok", {"approval_reference": ""}, {}, "preview_sandbox_unavailable"),
            ("no_decoder", {}, {}, "preview_sandbox_unavailable"),
            ("describe_profile", {}, {}, "preview_profile_unavailable"),
            ("temp_limit", {}, {"max_temp_bytes": 100000}, "preview_resource_exceeded"),
        ):
            with self.subTest(mode=mode), executor(mode, policy_patch=patch_policy, profile_patch=patch_profile) as (adapter, policy, root), self.assertRaises(PreviewFailure) as error:
                adapter.render(self.docx, policy=policy)
            self.assertEqual(error.exception.code, expected)
