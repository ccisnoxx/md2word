#!/usr/bin/env python3
"""sr-4 渲染等价性工具：用正式转换路径生成 DOCX，记录每个 part 的 sha256 并与基线对比。

用法（在仓库根目录运行）：
  python verify_render_equivalence.py --output parts.json [--extra-input DIR ...]
  python verify_render_equivalence.py --output parts.json --compare baseline-parts.json [...]

默认输入为 tests/fixtures/component_pdf_samples 下提交的 MinerU 包；``--extra-input`` 可追加本地包目录。
除 DOCX part 外，还记录渲染证据（renderer_metadata）的规范化 JSON 摘要，用于发现证据拆分导致的语义变化。
需配合固定的 PYTHONHASHSEED 运行（见 validation/equiv.sh），否则 metadata 中由 set 产生的列表顺序可能随进程变化。
转换失败时记录异常类型与消息，失败本身也纳入对比。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
import types
import zipfile
from pathlib import Path

REPO_ROOT = Path.cwd()
sys.path.insert(0, str(REPO_ROOT))

from scripts.dev.formal_mineru_conversion import run_conversion  # noqa: E402

SAMPLE_ROOT = REPO_ROOT / "tests/fixtures/component_pdf_samples/samples"
# 连续两次运行确认后需要排除的不稳定 part；为空表示全部 part 均参与对比。
UNSTABLE_PARTS: frozenset[str] = frozenset()
# zipfile.writestr 以当前时间（秒级）写入条目时间戳，使整包 docx_sha256 及其派生摘要随运行时刻变化；
# 只替换 zipfile 模块看到的 time 对象，固定 localtime，part 内容不受影响。
zipfile.time = types.SimpleNamespace(time=time.time, localtime=lambda *_: time.struct_time((2026, 1, 1, 0, 0, 0, 3, 1, 0)))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _collect_inputs(extra_inputs: list[str]) -> dict[str, Path]:
    inputs = {
        str(path.relative_to(SAMPLE_ROOT)): path
        for path in sorted(SAMPLE_ROOT.glob("**/mineru"))
        if path.is_dir()
    }
    for raw in extra_inputs:
        path = Path(raw).expanduser().resolve()
        inputs[f"extra/{path.name}"] = path
    return inputs


def _render_sample(input_path: Path, work_dir: Path) -> dict[str, object]:
    output_path = work_dir / "out.docx"
    try:
        result = run_conversion(
            input_path=str(input_path),
            output_path=str(output_path),
            template_path=None,
            subscript_config=None,
            no_template=False,
            use_mineru_header_footer=False,
        )
    except Exception as exc:  # 失败类型与消息也是等价性的一部分
        return {"error": f"{type(exc).__name__}: {exc}"}
    with zipfile.ZipFile(result.output_docx_path) as archive:
        parts = {
            name: _sha256(archive.read(name))
            for name in sorted(archive.namelist())
            if name not in UNSTABLE_PARTS
        }
    metadata = json.dumps(result.renderer_metadata, sort_keys=True, ensure_ascii=False, default=str)
    return {"parts": parts, "renderer_metadata_sha256": _sha256(metadata.encode("utf-8"))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", required=True)
    parser.add_argument("--compare")
    parser.add_argument("--extra-input", action="append", default=[])
    args = parser.parse_args()

    manifest: dict[str, object] = {"excluded_parts": sorted(UNSTABLE_PARTS), "samples": {}}
    for name, input_path in _collect_inputs(args.extra_input).items():
        with tempfile.TemporaryDirectory(prefix="sr4_equiv_") as temp_dir:
            manifest["samples"][name] = _render_sample(input_path, Path(temp_dir))
    Path(args.output).write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                                 encoding="utf-8")
    samples = manifest["samples"]
    print(f"已生成 {len(samples)} 个样本的清单：{args.output}")
    for name, entry in samples.items():
        summary = entry.get("error") or f"{len(entry['parts'])} 个 part"
        print(f"  {name}: {summary}")

    if not args.compare:
        return 0
    baseline = json.loads(Path(args.compare).read_text(encoding="utf-8"))
    if baseline == manifest:
        print("与基线完全一致。")
        return 0
    print("与基线存在差异：")
    for name in sorted(set(baseline["samples"]) | set(samples)):
        before, after = baseline["samples"].get(name), samples.get(name)
        if before == after:
            continue
        if not before or not after or "parts" not in before or "parts" not in after:
            print(f"  {name}: {before!r} -> {after!r}")
            continue
        for part in sorted(set(before["parts"]) | set(after["parts"])):
            if before["parts"].get(part) != after["parts"].get(part):
                print(f"  {name}: part {part} 不一致")
        if before["renderer_metadata_sha256"] != after["renderer_metadata_sha256"]:
            print(f"  {name}: renderer_metadata 不一致")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
