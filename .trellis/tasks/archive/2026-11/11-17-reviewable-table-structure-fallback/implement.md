# 实施与定向验证

1. 连接普通转换的结构预检、原生保留、可信图像占位和原页回退。采用现有来源定位、资源注册、页依赖、失败日志和下载路径。
2. 只对已认证的新回退调整活动质量分级，在现有质量报告提供 warning 与人工复核；保留旧证据格式和独立硬门禁。
3. 通过普通 Worker 和真实 HTTP 路由核对三种成功响应，下载实际 Word 并核对内容；验证无可靠回退、摘要错误和实物表缺失三个负例。
4. 核对差异和工作区。补记实际命令、结果和未验证范围。授权范围仅含以上定向用例。

## 实际执行与结果

验收基线为本地 `main@96e7aca2`，使用临时目录、正式直转 Worker 和 TestClient。测试模块为 `tests/test_reviewable_table_structure_fallback.py`。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest -v tests.test_reviewable_table_structure_fallback
```

首轮运行 6 项，耗时 1.553 秒。无可靠回退、参考图摘要不一致和 Word 漏表三个负例通过。三个成功场景的整体质量断言失败。核对发现成功夹具缺少实际 PDF 页尺寸的 `middle.json`，并且预览禁用仍独立贡献 `pending`。为成功用例补齐与 PDF 一致的页尺寸和现有本地预览替身，负例沿用原夹具。保留独立质量提示和预览的原分级。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest -v \
  tests.test_reviewable_table_structure_fallback.ReviewableTableStructureFallbackTests.test_bad_html_preserves_the_native_cells_and_downloads \
  tests.test_reviewable_table_structure_fallback.ReviewableTableStructureFallbackTests.test_illegal_merge_preserves_the_verified_reference_and_downloads \
  tests.test_reviewable_table_structure_fallback.ReviewableTableStructureFallbackTests.test_empty_table_without_crop_preserves_the_single_pdf_page_and_downloads
```

复验只运行首次未通过的三项，退出码 0，3 项通过，0 项跳过，耗时 1.194 秒。每项为 `succeeded/completed`、质量 `warning`。质量 API 返回原页、来源指针、保留方式及 `manual_review_required=true`。三项内部签发和真实 HTTP 下载均返回 200，下载字节与登记主件匹配。Word 分别保留 Alpha/Beta 原生单元格、已验证参考图，以及真实 Poppler 生成的单页原图。图像场景带不可编辑提示。

三个负例分别核对带页定位的 `table_structure_recovery_unavailable`、`table_placeholder_integrity_failed` 和 Word 实物不符的 `render_failed`，均无可下载结果。复用首轮通过记录。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/ops/export_openapi.py
git diff --check -- app tests docs/api/openapi.json .trellis/spec/backend/word-generation-rules.md
```

同步质量 API 维护快照，导出 180 条路径、399 个 schema。差异空白检查通过。使用 Python `ast.parse` 静态核对 19 个变动 Python 文件，并读取快照确认人工复核条目和 `warning` 严重度。


## 局部裁图和跨页回退补验

### 题注提示对账

两份同一续表的题注分别包含复合表号 `4-1` 和续表标记。续表规则能识别关联，题注整理器仍会产生 `caption_binding_uncertain`。原页回退替换了题注所在块，但原先只移除附块 ID 的提示，全局题注提示继续计入未知风险，整体质量停在 `pending`。

本次修复限定在 `app/services/document_ir/table_structure_recovery.py` 的坏表整页回退。替换前收集题注不确定块、关联成员及绑定或候选的来源与目标块。仅当来源可完整定位，且本代已核验的原页图像覆盖全部关联块时，清除活动 `caption_binding_uncertain`。关联块仍留在正文、缺少定位，或先前整页回退已使来源不完整时，保留活动提示。图像输出仍使用现有的来源校验和 Word 实物校验。

### 实际回放结果

两次执行均使用 `babe9757` 的临时导出、正式本地直转 Worker、TestClient、留存夹具组装的 MinerU 回包和本地预览替身。图像由真实 Poppler 26.06.0 处理。首次预检发现并行工作区已有代码和夹具变化，提前退出，未创建任务。后续回放均在临时目录运行，修复后回放只叠加上述 Python 文件。

| 回放 | 任务与质量 | 下载及实物核对 |
| --- | --- | --- |
| 修复前。第 1 页局部裁图 | `succeeded/completed`、整体 `warning`。唯一复核项为第 1 页 `/1`，`invalid_table_merge`、`pdf_crop`、`manual_review_required=true`。 | 签发和下载均为 HTTP 200，下载字节与登记主件一致。主件 SHA-256 为 `b7b170cc4d30a754773f1b9c1121c8238aa9d5b39e3e28cc24097719aad79fbc`。Word 中的 `880 × 630` PNG 与登记裁图字节一致，与源 PDF 第 1 页 `[200, 140, 640, 455]` pt 矩形逐像素一致。无整页回退。 |
| 修复前。三页跨页续表 | `succeeded/completed`、整体 `pending`。实际人工复核项为第 2 页 `/1/0`，`invalid_table_merge`、`pdf_page`、`manual_review_required=true`。布局提示仍有 `caption_binding_uncertain`。 | 签发和下载均为 HTTP 200，下载字节与登记主件一致。主件 SHA-256 为 `e224d8b687eaa4fec61190c20bf94bd20dc38cbc2a27a421ceeb71c5dbf9c236`。质量断言先失败，因此这次未核对第 1、2 页图片、页序及第 3 页正文。 |
| 修复后。仅复验三页跨页续表 | `succeeded/completed`、整体 `warning`。仅第 2 页 `/1/0` 需人工复核，`invalid_table_merge`、`pdf_page`、`manual_review_required=true`。第 1 页是闭包内的续表依赖页。题注来源在第 1、2 页，活动提示已按回退实物对账。 | 签发和下载均为 HTTP 200。下载字节、登记主件、质量接口所绑定摘要一致。主件 SHA-256 为 `93ade09c6da2147550d8d63aa5a0818a7497353fd4fcf7c2bf6ce6fee975ee30`。第 1、2 页各有一张 `2000 × 2000` PNG，分别与带题注的原页逐像素一致，Word 内嵌顺序为第 1 页后第 2 页。第 3 页正文在两张图之后，仍是可编辑的 Word 文本段落。 |

首次同时回放局部裁图和跨页回退，各创建一个任务。局部裁图通过，跨页停在质量断言，命令退出码为 1。修复后只创建一个三页跨页任务，未重复局部裁图，命令退出码为 0。为核对题注随原页保留，修复后的回放还将原有两条题注写入临时源 PDF，并分别核对质量、下载及 Word 实物。原六项定向验收继续复用已通过结果。

### 实际执行命令

从仓库根目录执行。命令用标准输入传入 Python 代码，输入和产物均在临时目录。以下保留两次实际运行的命令。

<details>
<summary>修复前回放命令（局部裁图和跨页回退）</summary>

```sh
PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 .venv/bin/python - <<'PY'
from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
from shutil import which
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

repo = Path.cwd()
base = "babe9757b9f4b12ddb78950474874f38930a3c3d"
third_text = "Third page remains editable."

def git(*args):
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()

def check(ok, message):
    if not ok:
        raise AssertionError(message)

def digest(data):
    return "sha256:" + sha256(data).hexdigest()

def snapshot():
    return (git("rev-parse", "HEAD"), git("status", "--porcelain=v1", "--untracked-files=all"))

def package(blocks, sizes, v2=False):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("content_list_v2.json" if v2 else "content_list.json", json.dumps(blocks))
        archive.writestr("middle.json", json.dumps({
            "pdf_info": [{"page_idx": i, "page_size": size} for i, size in enumerate(sizes)],
        }))
    return stream.getvalue()

@contextmanager
def direct(root, source, returned, *, crop):
    runtime = fixtures.build_test_runtime(
        root / "runtime", auth_jwt_secret_key="test-jwt-secret",
        auth_internal_users_json=fixtures.build_auth_users_json(),
        document_jobs_worker_backend="eager",
    )
    worker = runtime.document_job_execution_service
    worker.fake_mineru_client.result_zip_bytes = returned
    worker.document_ir_service.pdf_crop_provider = crop
    worker.document_ir_service.page_rasterizer = PopplerPdfPageRasterizer()
    worker.settings.word_preview_backend = "sandboxed"
    worker.rendering.results.word_preview_service.provider = RecordingPreviewProvider()
    with TestClient(create_app(runtime)) as client:
        owner = fixtures.build_auth_header(client)
        file = fixtures.FastAPIJobsBackendTests._upload_source_pdf(
            None, client, owner, filename="source.pdf", pdf_content=source,
        )
        check(file["checksum_sha256"] == digest(source), "上传源摘要不符")
        created = client.post("/api/v1/document-jobs", headers=owner, json={
            "source_file_id": file["id"], "translation_mode": "direct", "document_language": "en",
        })
        check(created.status_code == 201, f"创建直转任务返回 {created.status_code}")
        url = f"/api/v1/document-jobs/{created.json()['job_id']}"
        detail = client.get(url, headers=owner)
        check(detail.status_code == 200, f"查询任务返回 {detail.status_code}")
        yield runtime, client, owner, url, detail.json()

def download_review(runtime, client, owner, url, job, *, page, pointer, method):
    state = (job["status"], job["stage"], job["quality_status"])
    print(f"  直转结果 {state}", flush=True)
    check(state[:2] == ("succeeded", "completed"),
          f"转换失败 {job['error_code']} / {job['error_message']} / {job.get('failure_diagnostic')}")
    quality = client.get(f"{url}/quality", headers=owner)
    check(quality.status_code == 200, f"质量接口返回 {quality.status_code}")
    quality = quality.json()
    base_result, = [part for part in quality["producers"]["items"] if part["producer"] == "document_base"]
    reviews = base_result.get("table_structure_reviews", [])
    issued = client.get(f"{url}/download-url", headers=owner)
    check(issued.status_code == 200, f"签发返回 {issued.status_code}")
    grant = issued.json()
    check(grant["classification"] == "internal_only", "不是内部 DOCX 下载")
    downloaded = client.get(grant["download_url"])
    check(downloaded.status_code == 200, f"下载返回 {downloaded.status_code}")
    word_record = runtime.document_file_repository.get_document_file(job["result_file_id"])
    read = runtime.file_upload_service.read_file_content
    check(downloaded.content == read(word_record)
          and digest(downloaded.content) == word_record.checksum_sha256 == quality["source"]["result_sha256"]
          and quality["source"]["result_file_id"] == word_record.id, "下载、质量报告和登记主件未绑定同一实物")
    print(f"  签发 200、下载 200、字节与主件相同，主件 {word_record.checksum_sha256}", flush=True)
    print(f"  复核项 {reviews}", flush=True)
    check(state[2] == quality["states"]["quality_status"] == "warning",
          f"质量不为 warning，布局提示 {word_record.metadata.get('layout_quality_flags')}")
    check(reviews == [{"page_number": page, "source_pointer": pointer, "reason": "invalid_table_merge",
                       "preserved_as": method, "severity": "warning", "manual_review_required": True}],
          "复核定位、严重度或保留方式不符")
    ir = json.loads(read(runtime.document_file_repository.get_document_file(job["document_ir_file_id"])))
    files = [entry for entry in runtime.document_file_repository.list_document_files() if entry.job_id == job["id"]]
    return Document(BytesIO(downloaded.content)), ir, files

def page_pixels(pdf, page, root):
    prefix = root / f"expected-page-{page}"
    subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-singlefile", "-r", "144",
                    "-png", str(pdf), str(prefix)], capture_output=True, timeout=30, check=True)
    with Image.open(prefix.with_suffix(".png")) as image:
        return image.convert("RGB")

def pixels_match(content, expected, label):
    with Image.open(BytesIO(content)) as image:
        check(image.format == "PNG" and image.size == expected.size, f"{label}尺寸或格式不符")
        check(ImageChops.difference(image.convert("RGB"), expected).getbbox() is None, f"{label}像素不符")

def pictures(word):
    return [word.part.related_parts[ref.get(qn("r:embed"))].blob
            for ref in word.element.body.xpath(".//a:blip")]

def crop_case(root):
    source = make_crop_pdf(media="0 0 842 596").content
    pdf = root / "source.pdf"
    pdf.write_bytes(source)
    bbox = [200, 140, 640, 455]
    full = page_pixels(pdf, 1, root)
    expected = full.crop(tuple(value * 2 for value in bbox))
    red, green, blue = expected.getpixel((440, 315))
    check(full.size == (1684, 1192) and expected.size == (880, 630)
          and expected.getpixel((0, 0)) == (255, 255, 255) and blue > green > red, "参考裁图未覆盖预期色块范围")
    blocks = [
        {"type": "text", "text": "Body before table.", "page_idx": 0, "bbox": [50, 70, 760, 120], "column_hint": "wide"},
        {"type": "table", "html": ILLEGAL_MERGE, "page_idx": 0, "bbox": bbox, "column_hint": "wide"},
    ]
    with direct(root, source, package(blocks, [[842, 596]]), crop=PopplerPdfTableCropProvider()) as args:
        word, ir, files = download_review(*args, page=1, pointer="/1", method="pdf_crop")
        binding, = ir["metadata"]["table_placeholders"]
        check(binding["source_kind"] == "source_pdf_crop" and binding["page_index"] == 0
              and binding["bbox"] == bbox and binding["frame"] == [842, 596]
              and binding["source_pdf_sha256"] == digest(source), "裁图绑定的页码、坐标或源摘要不符")
        check(not ir["metadata"]["degraded_pages"], "局部裁图任务发生整页回退")
        asset, = [entry for entry in files if entry.metadata.get("asset_role") == "table_placeholder"]
        embedded, = pictures(word)
        check(embedded == args[0].file_upload_service.read_file_content(asset)
              and digest(embedded) == asset.checksum_sha256 == binding["asset_sha256"], "Word 图像与登记裁图不同")
        pixels_match(embedded, expected, "局部裁图")
        check(any("不可编辑" in part.text for part in word.paragraphs), "图像未标记为不可编辑")
        print("  裁图范围 [200, 140, 640, 455] pt，PNG 880×630，逐像素匹配原页对应矩形。未发生整页回退。", flush=True)

def cross_case(root):
    drawings = [
        b"0.1 0.2 0.8 rg 40 40 900 260 re f 0 0 0 rg BT /F1 18 Tf 50 328 Td (Source page one) Tj ET",
        b"0.8 0.2 0.1 rg 40 680 900 260 re f 0 0 0 rg BT /F1 18 Tf 50 660 Td (Source page two) Tj ET",
        b"BT /F1 18 Tf 60 860 Td (Third page remains editable.) Tj ET",
    ]
    pieces = []
    for number, drawing in enumerate(drawings, 1):
        file = root / f"piece-{number}.pdf"
        file.write_bytes(make_pdf(drawing, width=1000, height=1000))
        pieces.append(str(file))
    pdf = root / "source.pdf"
    subprocess.run(["pdfunite", *pieces, str(pdf)], capture_output=True, timeout=10, check=True)
    source = pdf.read_bytes()
    expected = [page_pixels(pdf, number, root) for number in (1, 2)]
    check(expected[0].size == expected[1].size == (2000, 2000)
          and ImageChops.difference(*expected).getbbox() is not None, "参考原页应为两张可区分的整页图")
    blocks = []
    for index, (caption, bbox) in enumerate([
        ("Table 4-1. Pin Functions", [20, 650, 980, 980]),
        ("Table 4-1. Pin Functions (continued)", [20, 20, 980, 350]),
    ]):
        tag = "<td>" if index == 0 else '<td rowspan="invalid">'
        blocks.append([{"type": "table", "bbox": bbox, "content": {
            "table_caption": [{"type": "text", "content": caption}],
            "html": f"<table><tr><th>Pin</th><th>Value</th></tr><tr>{tag}{index+1}</td><td>A</td></tr></table>",
        }}])
    blocks.append([{"type": "text", "text": third_text, "bbox": [55, 120, 940, 165], "column_hint": "wide"}])
    closure = recovery.degradation_closure
    calls = []
    def record_closure(groups, pending):
        closed = closure(groups, pending)
        calls.append((set(pending), closed, [
            (tuple(fragment.source_span.json_pointer for fragment in group.fragments),
             tuple(relation.kind for relation in group.continuation_relations))
            for group in groups
        ]))
        return closed

    with patch.object(recovery, "degradation_closure", side_effect=record_closure):
        with direct(root, source, package(blocks, [[1000, 1000]] * 3, v2=True), crop=None) as args:
            word, ir, files = download_review(*args, page=2, pointer="/1/0", method="pdf_page")
            check(calls == [({1}, {0, 1}, [(("/0/0", "/1/0"), ("verified_continuation",))])],
                  f"跨页闭包没有按预期触发 {calls}")
            rows = ir["metadata"]["degraded_pages"]
            check([(entry["page_index"], entry["issue_pointers"], entry["reason_codes"]) for entry in rows]
                  == [(0, [], []), (1, ["/1/0"], ["invalid_table_merge"])], "降级证据未区分依赖页和实际异常页")
            check(all(entry["source_pdf_sha256"] == digest(source) for entry in rows), "降级证据未绑定源 PDF")
            counts = args[-1]["quality_summary"]["checks_v1"]["document_base"]["page_counts"]
            check(tuple(counts[k] for k in ("source_page_count", "degraded_page_count", "converted_page_count")) == (3, 2, 1),
                  f"源页与回退数量不同 {counts}")
            print("  第 2 页唯一触发异常，关联的续表闭包覆盖第 1、2 页。", flush=True)
            assets = {entry.metadata["page_raster"]["page_index"]: entry for entry in files
                      if entry.metadata.get("origin") == "pdf_page_raster"}
            images = pictures(word)
            check(set(assets) == {0, 1} and len(images) == 2, "登记资产或 Word 图片的页范围不符")
            for index, content in enumerate(images):
                asset = assets[index]
                check(asset.metadata["page_raster"]["source_pdf_sha256"] == digest(source)
                      and content == args[0].file_upload_service.read_file_content(asset)
                      and digest(content) == asset.checksum_sha256, f"第 {index+1} 张内嵌图未绑定到同页登记资产")
                pixels_match(content, expected[index], f"源 PDF 第 {index+1} 页整页图")
            positions = [i for i, part in enumerate(word.paragraphs) if part._p.xpath(".//a:blip")]
            editable = [i for i, part in enumerate(word.paragraphs) if part.text == third_text
                        and part._p.xpath("./w:r/w:t") and not part._p.xpath(".//a:blip")]
            check(len(positions) == 2 and len(editable) == 1 and positions[-1] < editable[0],
                  "第 3 页正文未在两张回退图片之后按正常段落保留")
            print("  两张 2000×2000 原页 PNG 逐像素匹配源 PDF 第 1、2 页，Word 内嵌顺序相同；第 3 页仍为可编辑段落。", flush=True)

before = snapshot()
check(before[0] == base, "当前 HEAD 与核对的回放基线不一致")
for binary in ("pdfinfo", "pdftoppm", "pdfunite"):
    check(which(binary), f"缺少 {binary}")
failures = 0
with TemporaryDirectory(prefix="md2word-fallback-replay-") as temporary:
    root = Path(temporary)
    tree = root / "snapshot"
    tree.mkdir()
    with subprocess.Popen(["git", "archive", "--format=tar", base], cwd=repo, stdout=subprocess.PIPE) as archive:
        subprocess.run(["tar", "-xf", "-", "-C", str(tree)], stdin=archive.stdout, check=True)
        check(archive.wait() == 0, "提交快照导出失败")
    os.chdir(tree)
    sys.path.insert(0, str(tree))
    from docx import Document
    from docx.oxml.ns import qn
    from fastapi.testclient import TestClient
    from PIL import Image, ImageChops
    import app
    from app.infrastructure.pdf_crop import PopplerPdfPageRasterizer, PopplerPdfTableCropProvider
    from app.main import create_app
    from app.services.document_ir import table_structure_recovery as recovery
    from tests import test_fastapi_jobs_backend as fixtures
    from tests.document_job_list_query_v2_publication_fixtures import RecordingPreviewProvider
    from tests.test_pdf_crop import _source as make_crop_pdf
    from tests.test_pdf_value_column_observer import make_pdf
    from tests.test_reviewable_table_structure_fallback import ILLEGAL_MERGE

    check(Path(app.__file__).is_relative_to(tree) and Path(fixtures.__file__).is_relative_to(tree),
          "加载的 app 或夹具不属于固定提交的临时快照")
    print(f"基线 {base}，运行目录为临时导出。", flush=True)
    for label, run in (("源 PDF 局部裁图", crop_case), ("跨页表格依赖回退", cross_case)):
        print(f"验收 {label}", flush=True)
        case = root / run.__name__
        case.mkdir()
        try:
            run(case)
        except Exception as error:
            failures += 1
            print(f"结果 {label} 失败：{type(error).__name__}: {error}", flush=True)
            import traceback
            traceback.print_exc(limit=5)
        else:
            print(f"结果 {label} 通过", flush=True)
    os.chdir(repo)
after = snapshot()
print("回放前后原仓库 HEAD 和工作区状态一致。" if after == before
      else "回放期间原仓库状态有并行变化，执行产物均位于临时目录。", flush=True)
raise SystemExit(bool(failures))
PY
```

</details>

<details>
<summary>修复后回放命令（仅三页跨页回退）</summary>

```sh
PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 .venv/bin/python - <<'PY'
from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
from shutil import which
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

repo = Path.cwd()
base = "babe9757b9f4b12ddb78950474874f38930a3c3d"
third_text = "Third page remains editable."
validation_issues = []

def git(*args):
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()

def check(ok, message):
    if not ok:
        raise AssertionError(message)

def digest(data):
    return "sha256:" + sha256(data).hexdigest()

def snapshot():
    return (git("rev-parse", "HEAD"), git("status", "--porcelain=v1", "--untracked-files=all"))

def package(blocks, sizes, v2=False):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("content_list_v2.json" if v2 else "content_list.json", json.dumps(blocks))
        archive.writestr("middle.json", json.dumps({
            "pdf_info": [{"page_idx": i, "page_size": size} for i, size in enumerate(sizes)],
        }))
    return stream.getvalue()

@contextmanager
def direct(root, source, returned, *, crop):
    runtime = fixtures.build_test_runtime(
        root / "runtime", auth_jwt_secret_key="test-jwt-secret",
        auth_internal_users_json=fixtures.build_auth_users_json(),
        document_jobs_worker_backend="eager",
    )
    worker = runtime.document_job_execution_service
    worker.fake_mineru_client.result_zip_bytes = returned
    worker.document_ir_service.pdf_crop_provider = crop
    worker.document_ir_service.page_rasterizer = PopplerPdfPageRasterizer()
    worker.settings.word_preview_backend = "sandboxed"
    worker.rendering.results.word_preview_service.provider = RecordingPreviewProvider()
    with TestClient(create_app(runtime)) as client:
        owner = fixtures.build_auth_header(client)
        file = fixtures.FastAPIJobsBackendTests._upload_source_pdf(
            None, client, owner, filename="source.pdf", pdf_content=source,
        )
        check(file["checksum_sha256"] == digest(source), "上传源摘要不符")
        created = client.post("/api/v1/document-jobs", headers=owner, json={
            "source_file_id": file["id"], "translation_mode": "direct", "document_language": "en",
        })
        check(created.status_code == 201, f"创建直转任务返回 {created.status_code}")
        url = f"/api/v1/document-jobs/{created.json()['job_id']}"
        detail = client.get(url, headers=owner)
        check(detail.status_code == 200, f"查询任务返回 {detail.status_code}")
        yield runtime, client, owner, url, detail.json()

def download_review(runtime, client, owner, url, job, *, page, pointer, method):
    state = (job["status"], job["stage"], job["quality_status"])
    print(f"  直转结果 {state}", flush=True)
    check(state[:2] == ("succeeded", "completed"),
          f"转换失败 {job['error_code']} / {job['error_message']} / {job.get('failure_diagnostic')}")
    quality = client.get(f"{url}/quality", headers=owner)
    check(quality.status_code == 200, f"质量接口返回 {quality.status_code}")
    quality = quality.json()
    base_result, = [part for part in quality["producers"]["items"] if part["producer"] == "document_base"]
    reviews = base_result.get("table_structure_reviews", [])
    issued = client.get(f"{url}/download-url", headers=owner)
    check(issued.status_code == 200, f"签发返回 {issued.status_code}")
    grant = issued.json()
    check(grant["classification"] == "internal_only", "不是内部 DOCX 下载")
    downloaded = client.get(grant["download_url"])
    check(downloaded.status_code == 200, f"下载返回 {downloaded.status_code}")
    word_record = runtime.document_file_repository.get_document_file(job["result_file_id"])
    read = runtime.file_upload_service.read_file_content
    check(downloaded.content == read(word_record)
          and digest(downloaded.content) == word_record.checksum_sha256 == quality["source"]["result_sha256"]
          and quality["source"]["result_file_id"] == word_record.id, "下载、质量报告和登记主件未绑定同一实物")
    print(f"  签发 200、下载 200、字节与主件相同，主件 {word_record.checksum_sha256}", flush=True)
    print(f"  复核项 {reviews}", flush=True)
    if state[2] != "warning" or quality["states"]["quality_status"] != "warning":
        validation_issues.append(f"质量不为 warning，布局提示 {word_record.metadata.get('layout_quality_flags')}")
    if reviews != [{"page_number": page, "source_pointer": pointer, "reason": "invalid_table_merge",
                    "preserved_as": method, "severity": "warning", "manual_review_required": True}]:
        validation_issues.append("复核定位不是第 2 页唯一异常表，或其严重度、保留方式不符")
    ir = json.loads(read(runtime.document_file_repository.get_document_file(job["document_ir_file_id"])))
    files = [entry for entry in runtime.document_file_repository.list_document_files() if entry.job_id == job["id"]]
    return Document(BytesIO(downloaded.content)), ir, files

def page_pixels(pdf, page, root):
    prefix = root / f"expected-page-{page}"
    subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-singlefile", "-r", "144",
                    "-png", str(pdf), str(prefix)], capture_output=True, timeout=30, check=True)
    with Image.open(prefix.with_suffix(".png")) as image:
        return image.convert("RGB")

def pixels_match(content, expected, label):
    with Image.open(BytesIO(content)) as image:
        check(image.format == "PNG" and image.size == expected.size, f"{label}尺寸或格式不符")
        check(ImageChops.difference(image.convert("RGB"), expected).getbbox() is None, f"{label}像素不符")

def pictures(word):
    return [word.part.related_parts[ref.get(qn("r:embed"))].blob
            for ref in word.element.body.xpath(".//a:blip")]

def cross_case(root):
    drawings = [
        b"0.1 0.2 0.8 rg 40 40 900 260 re f 0 0 0 rg BT /F1 18 Tf 50 328 Td (Source page one) Tj ET BT /F1 18 Tf 50 350 Td (Table 4-1. Pin Functions) Tj ET",
        b"0.8 0.2 0.1 rg 40 680 900 260 re f 0 0 0 rg BT /F1 18 Tf 50 660 Td (Source page two) Tj ET BT /F1 18 Tf 50 956 Td (Table 4-1. Pin Functions (continued)) Tj ET",
        b"BT /F1 18 Tf 60 860 Td (Third page remains editable.) Tj ET",
    ]
    pieces = []
    for number, drawing in enumerate(drawings, 1):
        file = root / f"piece-{number}.pdf"
        file.write_bytes(make_pdf(drawing, width=1000, height=1000))
        pieces.append(str(file))
    pdf = root / "source.pdf"
    subprocess.run(["pdfunite", *pieces, str(pdf)], capture_output=True, timeout=10, check=True)
    source = pdf.read_bytes()
    captions = ("Table 4-1. Pin Functions", "Table 4-1. Pin Functions (continued)")
    for page, caption in enumerate(captions, 1):
        observed = subprocess.check_output(["pdftotext", "-f", str(page), "-l", str(page), str(pdf), "-"], text=True, timeout=10)
        check(caption in observed, f"第 {page} 页原始 PDF 缺少与回包一致的题注")
    expected = [page_pixels(pdf, number, root) for number in (1, 2)]
    check(expected[0].size == expected[1].size == (2000, 2000)
          and ImageChops.difference(*expected).getbbox() is not None, "参考原页应为两张可区分的整页图")
    blocks = []
    for index, (caption, bbox) in enumerate([
        ("Table 4-1. Pin Functions", [20, 650, 980, 980]),
        ("Table 4-1. Pin Functions (continued)", [20, 20, 980, 350]),
    ]):
        tag = "<td>" if index == 0 else '<td rowspan="invalid">'
        blocks.append([{"type": "table", "bbox": bbox, "content": {
            "table_caption": [{"type": "text", "content": caption}],
            "html": f"<table><tr><th>Pin</th><th>Value</th></tr><tr>{tag}{index+1}</td><td>A</td></tr></table>",
        }}])
    blocks.append([{"type": "text", "text": third_text, "bbox": [55, 120, 940, 165], "column_hint": "wide"}])
    closure = recovery.degradation_closure
    calls = []
    def record_closure(groups, pending):
        closed = closure(groups, pending)
        calls.append((set(pending), closed, [
            (tuple(fragment.source_span.json_pointer for fragment in group.fragments),
             tuple(relation.kind for relation in group.continuation_relations))
            for group in groups
        ]))
        return closed

    original_caption_scope = recovery._uncertain_caption_block_ids
    caption_calls = []
    def record_caption_scope(document):
        ids = original_caption_scope(document)
        caption_calls.append({block.page_index for block in document.blocks if block.id in ids})
        return ids

    with (
        patch.object(recovery, "degradation_closure", side_effect=record_closure),
        patch.object(recovery, "_uncertain_caption_block_ids", side_effect=record_caption_scope),
    ):
        with direct(root, source, package(blocks, [[1000, 1000]] * 3, v2=True), crop=None) as args:
            word, ir, files = download_review(*args, page=2, pointer="/1/0", method="pdf_page")
            check(calls == [({1}, {0, 1}, [(("/0/0", "/1/0"), ("verified_continuation",))])],
                  f"跨页闭包没有按预期触发 {calls}")
            rows = ir["metadata"]["degraded_pages"]
            check([(entry["page_index"], entry["issue_pointers"], entry["reason_codes"]) for entry in rows]
                  == [(0, [], []), (1, ["/1/0"], ["invalid_table_merge"])], "降级证据未区分依赖页和实际异常页")
            check(all(entry["source_pdf_sha256"] == digest(source) for entry in rows), "降级证据未绑定源 PDF")
            counts = args[-1]["quality_summary"]["checks_v1"]["document_base"]["page_counts"]
            check(tuple(counts[k] for k in ("source_page_count", "degraded_page_count", "converted_page_count")) == (3, 2, 1),
                  f"源页与回退数量不同 {counts}")
            print("  第 2 页唯一触发异常，关联的续表闭包覆盖第 1、2 页。", flush=True)
            assets = {entry.metadata["page_raster"]["page_index"]: entry for entry in files
                      if entry.metadata.get("origin") == "pdf_page_raster"}
            images = pictures(word)
            check(set(assets) == {0, 1} and len(images) == 2, "登记资产或 Word 图片的页范围不符")
            for index, content in enumerate(images):
                asset = assets[index]
                check(asset.metadata["page_raster"]["source_pdf_sha256"] == digest(source)
                      and content == args[0].file_upload_service.read_file_content(asset)
                      and digest(content) == asset.checksum_sha256, f"第 {index+1} 张内嵌图未绑定到同页登记资产")
                pixels_match(content, expected[index], f"源 PDF 第 {index+1} 页整页图")
            positions = [i for i, part in enumerate(word.paragraphs) if part._p.xpath(".//a:blip")]
            editable = [i for i, part in enumerate(word.paragraphs) if part.text == third_text
                        and part._p.xpath("./w:r/w:t") and not part._p.xpath(".//a:blip")]
            check(len(positions) == 2 and len(editable) == 1 and positions[-1] < editable[0],
                  "第 3 页正文未在两张回退图片之后按正常段落保留")
            print("  两张 2000×2000 原页 PNG 逐像素匹配源 PDF 第 1、2 页，Word 内嵌顺序相同；第 3 页仍为可编辑段落。", flush=True)
            check(caption_calls == [{0, 1}]
                  and "caption_binding_uncertain" not in ir["quality_flags"],
                  f"题注来源对账或活动标志清理不符 {caption_calls}")
            print("  原题注提示来源覆盖第 1、2 页，同代原页图像覆盖全部相关块，活动提示已清除。", flush=True)

before = snapshot()
check(before[0] == base, "当前 HEAD 与核对的回放基线不一致")
patched_file = Path("app/services/document_ir/table_structure_recovery.py")
patch_content = (repo / patched_file).read_bytes()
check(patch_content != subprocess.check_output(["git", "show", f"{base}:{patched_file}"], cwd=repo),
      "运行前未找到批准的题注修复")
for binary in ("pdfinfo", "pdftoppm", "pdfunite", "pdftotext"):
    check(which(binary), f"缺少 {binary}")
failures = 0
with TemporaryDirectory(prefix="md2word-fallback-replay-") as temporary:
    root = Path(temporary)
    tree = root / "snapshot"
    tree.mkdir()
    with subprocess.Popen(["git", "archive", "--format=tar", base], cwd=repo, stdout=subprocess.PIPE) as archive:
        subprocess.run(["tar", "-xf", "-", "-C", str(tree)], stdin=archive.stdout, check=True)
        check(archive.wait() == 0, "提交快照导出失败")
    (tree / patched_file).write_bytes(patch_content)
    os.chdir(tree)
    sys.path.insert(0, str(tree))
    from docx import Document
    from docx.oxml.ns import qn
    from fastapi.testclient import TestClient
    from PIL import Image, ImageChops
    import app
    from app.infrastructure.pdf_crop import PopplerPdfPageRasterizer
    from app.main import create_app
    from app.services.document_ir import table_structure_recovery as recovery
    from tests import test_fastapi_jobs_backend as fixtures
    from tests.document_job_list_query_v2_publication_fixtures import RecordingPreviewProvider
    from tests.test_pdf_value_column_observer import make_pdf

    check(Path(app.__file__).is_relative_to(tree) and Path(fixtures.__file__).is_relative_to(tree),
          "加载的 app 或夹具不属于固定提交的临时快照")
    print(f"基线 {base}，临时副本只叠加 {patched_file}。", flush=True)
    for label, run in (("跨页表格依赖回退", cross_case),):
        print(f"验收 {label}", flush=True)
        case = root / run.__name__
        case.mkdir()
        try:
            run(case)
        except Exception as error:
            failures += 1
            print(f"结果 {label} 失败：{type(error).__name__}: {error}", flush=True)
            import traceback
            traceback.print_exc(limit=5)
        else:
            print(f"结果 {label} {'存在质量或定位不符' if validation_issues else '通过'}", flush=True)
    os.chdir(repo)
after = snapshot()
print("回放前后原仓库 HEAD 和工作区状态一致。" if after == before
      else "回放期间原仓库状态有并行变化，执行产物均位于临时目录。", flush=True)
check((repo / patched_file).read_bytes() == patch_content, "原工作区的修复在回放期间变化")
for issue in validation_issues:
    print(f"质量核对失败：{issue}", flush=True)
raise SystemExit(bool(failures or validation_issues))
PY
```

</details>

## 未验证范围

- 本次局部裁图已覆盖一个具有明确页尺寸和表框的样本，跨页回退已覆盖一个三页场景。更长的依赖链、其他页面几何及题注关联仍部分分布在未回退页的场景未另外执行。
- v2 图表识别分支、非字符串坏 HTML 的占位证据及旧凭据重读仅做静态复核。复用六项定向验收及局部裁图的已有通过结果。既有 P7、LOW/HIGH 和其他历史用例未重跑。
- 生产部署、生产预览、Word/WPS 客户端视觉效果、正式发布后最终件签发和下载仍未验证。
