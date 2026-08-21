from __future__ import annotations

# app/services/document_ir/mineru_package.py: 提供 MinerU 结果包解包和 content_list 读取 helper。

import json
import zipfile
from pathlib import Path
from typing import Any


def extract_zip(zip_path: Path, target_dir: Path) -> None:
    """安全解压 MinerU 结果 zip，保持既有非法路径拒绝语义。"""

    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or any(part in {"", ".", ".."} for part in member_path.parts):
                raise ValueError(f"MinerU 结果包包含非法路径: {member.filename}")
            archive.extract(member, target_dir)


def find_content_list(package_root: Path) -> Path:
    """在唯一结果根中查找 content_list，同根优先选择 v2。"""

    candidates = []
    for path in package_root.rglob("*.json"):
        name = path.name
        if name in {"content_list_v2.json", "content_list.json"}:
            candidates.append(path)
        elif name.endswith("_content_list_v2.json") or name.endswith("_content_list.json"):
            candidates.append(path)
    if not candidates:
        raise FileNotFoundError("MinerU 结果包缺少 content_list_v2.json 或 content_list.json。")
    result_roots = {path.parent.resolve() for path in candidates}
    if len(result_roots) != 1:
        raise ValueError(
            "MinerU 结果包包含多个 MinerU 结果根，无法唯一绑定 content list、layout 和资产。"
        )

    preferred = [path for path in candidates if path.name.endswith("content_list_v2.json")]
    selected = preferred or candidates
    if len(selected) != 1:
        raise ValueError("MinerU 结果根包含多个同版本 content list，无法唯一确定输入。")
    return selected[0]


def load_content_blocks(content_list_path: Path) -> list[dict[str, Any]]:
    """读取 MinerU content_list，兼容扁平块数组和 v2 page-list 数组。"""

    payload = json.loads(content_list_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        blocks = payload
    elif isinstance(payload, dict) and isinstance(payload.get("content_list"), list):
        blocks = payload["content_list"]
    else:
        raise ValueError("MinerU content_list 不是数组，也不包含 content_list 数组。")
    return _flatten_content_blocks(blocks)


def _flatten_content_blocks(blocks: list[Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for page_index, item in enumerate(blocks):
        if isinstance(item, dict):
            flattened.append(item)
            continue
        if not isinstance(item, list):
            continue
        for block in item:
            if not isinstance(block, dict):
                continue
            copied = dict(block)
            copied.setdefault("page_idx", page_index)
            flattened.append(copied)
    return flattened
