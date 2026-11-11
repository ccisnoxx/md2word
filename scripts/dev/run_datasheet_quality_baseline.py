#!/usr/bin/env python3
"""离线回放锁定的 Datasheet 样本，采集指标原始观测。"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import platform
from pathlib import Path
import re
import shutil
import subprocess
import sys
from time import perf_counter
from xml.etree import ElementTree

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from docx.table import Table

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.document_ir.artifact_validator import MinerUArtifactValidationError
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.table_placeholder import PdfCropSource, TablePlaceholderError
from app.services.renderer.table_renderer import TableRenderError
from scripts.dev.formal_mineru_conversion import LOCAL_SOURCE_FILE_ID, run_conversion
from scripts.ops.datasheet_quality_metrics import OBSERVATION_VERSION, build_report

MANIFEST = ROOT / "tests/fixtures/datasheet_quality/local_baseline_manifest.json"
RESOURCES = {
    "template_path": ROOT / "resources/templates/default/datasheet_template.docx",
    "layout_config_path": ROOT / "resources/template_configs/datasheet_template_v2.yaml",
    "subscript_config": ROOT / "resources/term_rules/subscripts_dictionary.yaml",
}


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def plan_row(sample: dict) -> dict:
    row = {key: sample[key] for key in ("sample_id", "cohort")}
    row.update(mode="direct", evidence_level="local_replay", expected_outcome="normal")
    if "expected_blocker" in sample:
        row.update(expected_outcome="blocked", expected_blocker=sample["expected_blocker"])
    if "tables" in sample:
        row["expected_tables"] = len(sample["tables"])
        row["expected_tokens"] = dict(Counter(
            item[2] for table in sample["tables"] for item in table["tokens"]
        ))
    if "visual" in sample:
        row["expected_visual_pages"] = len({region["source_page"] for region in sample["visual"]})
        row["expected_visual_regions"] = len(sample["visual"])
    return row


def expected_cell_shapes(table: dict) -> list[list[tuple[int, str | None]]]:
    """将独立标注的合并矩形投影到 OOXML 行形状。"""
    starts = {}
    for row, column, height, width in table["merges"]:
        for offset in range(height):
            merge = ("restart" if offset == 0 else "continue") if height > 1 else None
            starts[row + offset, column] = width, merge
    result = []
    for row in range(table["rows"]):
        cells = []
        column = 0
        while column < table["columns"]:
            cell = starts.get((row, column), (1, None))
            cells.append(cell)
            column += cell[0]
        result.append(cells)
    return result


def table_and_token_observations(tables: list[dict], doc, result) -> tuple[dict, dict]:
    """以来源片段定位实物表，再分别核对结构和已标注的单元格。"""
    native = result.renderer_metadata["table_rendering"]["tables"]
    observed = {table["table_index"]: table for table in result.docx_quality["table_observations"]}
    source_grids = {table["logical_group_id"]: table for table in result.renderer_metadata["table_evidence"]["tables"]}
    matched = 0
    tokens = Counter()
    assessed_tokens = Counter()
    extras = Counter()
    duplicates = 0
    table_reasons = []
    token_reasons = []
    physical_tables = doc.element.xpath(".//w:tbl")
    for expected in tables:
        pointers = set(expected["source_pointers"])
        candidates = [unit for unit in native if pointers.intersection(
            fragment["source_span"]["json_pointer"] for fragment in unit["fragments"]
        )]
        actual = observed.get(candidates[0]["output_table_index"]) if len(candidates) == 1 else None
        if actual is None:
            duplicates += max(len(candidates) - 1, 0)
            table_reasons.append({"id": expected["id"], "reason": "source_table_missing_or_ambiguous"})
            continue
        headers = [i for i, row in enumerate(actual["rows"]) if row["header"]]
        cells = [[(cell["grid_span"], cell["vertical_merge"]) for cell in row["cells"]]
                 for row in actual["rows"]]
        reasons = []
        actual_pointers = {fragment["source_span"]["json_pointer"] for fragment in candidates[0]["fragments"]}
        if pointers != actual_pointers:
            reasons.append("source_fragments")
        if actual["grid_columns"] != expected["columns"] or cells != expected_cell_shapes(expected):
            reasons.append("grid")
        if headers != expected["header_rows"]:
            reasons.append("header_rows")
        source = source_grids[candidates[0]["logical_group_id"]]
        source_grid = source["source_grid"]
        source_merges = {(cell["row"], cell["column"], cell["rowspan"], cell["colspan"])
                         for cell in source["validation"]["cells"] if cell["rowspan"] > 1 or cell["colspan"] > 1}
        source_matches = (
            source_grid["rows"] == expected["rows"] and source_grid["columns"] == expected["columns"]
            and source_grid["header_rows"] == expected["header_rows"]
            and source_merges == set(map(tuple, expected["merges"]))
        )
        if reasons or not source_matches:
            table_reasons.append({"id": expected["id"], "reason": ",".join(reasons) or "source_grid",
                                  "actual_columns": actual["grid_columns"], "actual_rows": len(cells),
                                  "actual_header_rows": headers, "source_grid_matches": source_matches,
                                  "source_header_rows": source_grid["header_rows"]})
        else:
            matched += 1
        # 网格错位时，实际同坐标的 Token 无法与预期单元格可靠绑定。
        if any(reason in {"grid", "source_fragments"} for reason in reasons):
            token_reasons.append({"id": expected["id"], "reason": "cell_binding_changed"})
            continue
        word_table = Table(physical_tables[actual["table_index"]], doc)
        for (row, column, kind, literal), count in Counter(map(tuple, expected["tokens"])).items():
            cell = word_table.cell(row, column)
            value = "".join(node.text or "" for node in cell._tc.xpath(".//w:t|.//m:t"))
            found = len(re.findall(r"(?<!\w)" + re.escape(literal) + r"(?!\w)", value))
            assessed_tokens[kind] += count
            tokens[kind] += min(found, count)
            extras[kind] += max(found - count, 0)
    return (
        {"matched": matched, "duplicate": duplicates, "reasons": table_reasons},
        {"matched": dict(tokens), "assessed": dict(assessed_tokens),
         "extras": dict(extras), "reasons": token_reasons},
    )


def pdf_anchors(pdf: Path, labels: set[str]) -> dict[str, list[tuple[int, list[float]]]]:
    """从 PDF 文本框读取唯一锚点的归一化边界。"""
    output = subprocess.run(["pdftotext", "-bbox-layout", str(pdf), "-"], check=True,
                            capture_output=True, timeout=60)
    pages = ElementTree.fromstring(output.stdout).findall(".//{*}page")
    hits = {label: [] for label in labels}
    for page_number, page in enumerate(pages, 1):
        width, height = float(page.attrib["width"]), float(page.attrib["height"])
        for line in page.findall(".//{*}line"):
            words = line.findall("{*}word")
            values = [word.text or "" for word in words]
            for label in labels:
                parts = label.split()
                for index in range(len(words) - len(parts) + 1):
                    if values[index:index + len(parts)] != parts:
                        continue
                    span = words[index:index + len(parts)]
                    edges = [(min, "xMin", width), (min, "yMin", height),
                             (max, "xMax", width), (max, "yMax", height)]
                    bbox = [aggregate(float(word.attrib[key]) for word in span) / scale
                            for aggregate, key, scale in edges]
                    hits[label].append((page_number, bbox))
    return hits


def visual_observation(annotations: list[dict], source: Path, docx: Path, output: Path) -> dict:
    if not shutil.which("soffice") or not shutil.which("pdftotext"):
        return {"matched_pages": 0, "regions": [], "reason": "visual_tools_unavailable"}
    pdf_dir = output / "pdf"
    pdf_dir.mkdir(exist_ok=True)
    target = pdf_dir / docx.with_suffix(".pdf").name
    try:
        subprocess.run(["soffice", f"-env:UserInstallation={(output / 'lo-profile').as_uri()}",
                        "--headless", "--convert-to", "pdf", "--outdir", str(pdf_dir), str(docx)],
                       check=True, capture_output=True, timeout=120)
        if not target.is_file():
            return {"matched_pages": 0, "regions": [], "reason": "visual_render_missing"}
        labels = {item["text"] for item in annotations}
        source_hits, result_hits = pdf_anchors(source, labels), pdf_anchors(target, labels)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ElementTree.ParseError):
        return {"matched_pages": 0, "regions": [], "reason": "visual_render_or_extract_failed"}
    pairs = []
    matched_pages = set()
    for item in annotations:
        label, page = item["text"], item["source_page"]
        left = [box for current_page, box in source_hits[label] if current_page == page]
        right = result_hits[label]
        if len(left) == len(right) == 1:
            result_page, box = right[0]
            pairs.append({"id": item["id"], "source_page": page, "result_page": result_page,
                          "source_bbox": left[0], "result_bbox": box})
            matched_pages.add(page)
    return {"matched_pages": len(matched_pages), "regions": pairs,
            "reason": "anchor_missing_or_ambiguous" if len(pairs) != len(annotations) else None}


def observation(sample: dict, package: Path, output: Path) -> dict:
    sample_id = sample["sample_id"]
    row = {"sample_id": sample_id, "mode": "direct",
           "missing": {"cost": "offline_replay_no_provider_invoice", "edits": "no_human_signoff",
                       "review_time": "no_human_signoff"}}
    sources = list(package.glob("*_origin.pdf"))
    layouts = list(package.glob("*_content_list_v2.json"))
    if len(sources) != 1 or len(layouts) != 1:
        return {**row, "conversion": {"status": "missing_input", "reason": "expected_pdf_and_v2_package"}}
    source, content_list = sources[0], layouts[0]
    if sha256(source) != sample["pdf_sha256"] or sha256(content_list) != sample["content_list_v2_sha256"]:
        return {**row, "conversion": {"status": "input_mismatch", "reason": "manifest_fingerprint_mismatch"}}
    docx = output / f"{sample_id}.docx"
    started = perf_counter()
    try:
        result = run_conversion(
            input_path=str(package), output_path=str(docx), **{key: str(value) for key, value in RESOURCES.items()},
            no_template=False, use_mineru_header_footer=False, document_language="en", job_id=sample_id,
            placeholder_source=PdfCropSource(LOCAL_SOURCE_FILE_ID, "sha256:" + sample["pdf_sha256"],
                                             source.read_bytes()),
        )
        doc = Document(docx)
    except (MinerUArtifactValidationError, TablePlaceholderError, TableRenderError,
            DocumentIntegrityError, PackageNotFoundError) as error:
        reason = getattr(error, "code", type(error).__name__)
        if isinstance(error, MinerUArtifactValidationError) and error.report.first_fatal is not None:
            reason = error.report.first_fatal.code
        if isinstance(error, DocumentIntegrityError):
            reason = ",".join(error.evidence["blocking_quality_flags"])
        row["conversion"] = {"status": "failed", "reason": reason}
    else:
        row["conversion"] = {"status": "succeeded", "docx_available": True, "docx_openable": True}
    row["latency"] = {"kind": "local_replay", "seconds": round(perf_counter() - started, 4)}
    if row["conversion"]["status"] != "succeeded":
        return row
    table_evidence = result.renderer_metadata["table_evidence"]
    placeholders = []
    for table in table_evidence["tables"]:
        pointers = {fragment["fragment_id"]: fragment["json_pointer"] for fragment in table["validation"]["fragments"]}
        placeholders.extend({"source_pointer": pointers[item["fragment_id"]], "source_kind": item["source_kind"],
                             "issue_code": item["issue_code"]} for item in table["placeholders"])
    if "expected_blocker" in sample:
        row["missing"]["blocker"] = "delivery_not_observed_in_local_replay"
    row["artifacts"] = {"docx_sha256": sha256(docx), "source_pages": result.pages,
                        "pdf_sha256": sample["pdf_sha256"],
                        "content_list_v2_sha256": sample["content_list_v2_sha256"],
                        "mineru_package_sha256": result.renderer_metadata["mineru_validation"]["package_sha256"],
                        "table_quality_status": table_evidence["status"], "quality_flags": result.quality_flags,
                        "table_placeholders": placeholders}
    if "tables" in sample:
        row["table"], row["tokens"] = table_and_token_observations(sample["tables"], doc, result)
    if "visual" in sample:
        row["visual"] = visual_observation(sample["visual"], source, docx, output)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="新建本地输出目录")
    parser.add_argument("--package", action="append", default=[], metavar="SAMPLE_ID=DIR", help="绑定本地结果包")
    args = parser.parse_args()
    packages = {}
    manifest = json.loads(MANIFEST.read_text())
    ids = {sample["sample_id"] for sample in manifest["samples"]}
    for argument in args.package:
        sample_id, separator, directory = argument.partition("=")
        if not separator or not directory or sample_id not in ids or sample_id in packages:
            parser.error("--package 需要唯一的已登记样本 ID 和目录")
        packages[sample_id] = Path(directory).expanduser().resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    visual_tools = {}
    for tool, version_arg in (("soffice", "--version"), ("pdftotext", "-v")):
        if shutil.which(tool):
            check = subprocess.run([tool, version_arg], capture_output=True, text=True, check=False, timeout=10)
            version_lines = (check.stdout + check.stderr).strip().splitlines()
            if check.returncode == 0 and version_lines:
                visual_tools[tool] = version_lines[0]
    tracked_diff = subprocess.check_output(["git", "diff", "--binary", "HEAD", "--", "app", "scripts"], cwd=ROOT)
    payload = {
        "schema_version": OBSERVATION_VERSION,
        "metadata": {"manifest_sha256": sha256(MANIFEST), "annotation_version": manifest["annotation_version"],
                     "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                     "tracked_code_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
                     "collector_sha256": sha256(Path(__file__)),
                     "resource_sha256": {key: sha256(value) for key, value in RESOURCES.items()},
                     "platform": platform.platform(), "python_version": platform.python_version(),
                     "visual_tools": visual_tools},
        "plan": [plan_row(sample) for sample in manifest["samples"]],
        "observations": [observation(sample, packages[sample["sample_id"]], output)
                         for sample in manifest["samples"] if sample["sample_id"] in packages],
    }
    for name, data in (("observations.json", payload), ("metrics.json", build_report(payload))):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
