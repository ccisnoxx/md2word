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
    """查找 MinerU content_list 文件，优先选择 v2，再按路径确定性排序。"""

    candidates = []
    for path in package_root.rglob("*.json"):
        name = path.name
        if name in {"content_list_v2.json", "content_list.json"}:
            candidates.append(path)
        elif name.endswith("_content_list_v2.json") or name.endswith("_content_list.json"):
            candidates.append(path)
    if not candidates:
        raise FileNotFoundError("MinerU 结果包缺少 content_list_v2.json 或 content_list.json。")
    return sorted(
        candidates,
        key=lambda item: (0 if item.name.endswith("content_list_v2.json") else 1, len(item.parts), item.as_posix()),
    )[0]


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
