"""MinerU 包 I/O、资源限额和包内路径判断的唯一所有者。"""
from __future__ import annotations

import hashlib
import json
import lzma
import zlib
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any


@dataclass(frozen=True, slots=True)
class MinerUValidationPolicy:
    """有界的本地输入策略；变更限额时同时升级版本。"""

    version: str = "mineru-input-policy/v2"
    max_entries: int = 10_000
    max_file_bytes: int = 128 * 1024 * 1024
    max_total_bytes: int = 1024 * 1024 * 1024
    max_json_bytes: int = 64 * 1024 * 1024
    max_issue_details: int = 1000
    max_report_bytes: int = 512 * 1024

    def __post_init__(self) -> None:
        for field in ("max_entries", "max_file_bytes", "max_total_bytes", "max_json_bytes",
                      "max_issue_details", "max_report_bytes"):
            value = getattr(self, field)
            if type(value) is not int or value <= 0:
                raise ValueError(f"MinerU 输入限额 {field} 必须为正整数。")
        # 固定报告字段和失败计数也需要空间；过低的测试预算不能生成合法失败摘要。
        if self.max_report_bytes < 4096:
            raise ValueError("MinerU 报告字节上限至少为 4096，以容纳有界失败摘要。")


DEFAULT_POLICY = MinerUValidationPolicy()


class MinerUPackageError(ValueError):
    """包边界失败，仅携带有限事实，不暴露临时路径或正文。"""

    def __init__(self, code: str, reason: str) -> None:
        self.code = code
        self.facts = {"reason": reason}
        super().__init__(f"MinerU 输入校验失败：{code}（{reason}）。")


def package_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_relative_path(raw_path: str, *, allow_leading_dot: bool = False) -> PurePosixPath:
    """先检查原文，禁止通过标准化抹除穿越或 Windows 路径。"""

    if not raw_path or "\x00" in raw_path or "\\" in raw_path or ":" in raw_path:
        raise MinerUPackageError("mineru_path_invalid", "invalid_path_syntax")
    if allow_leading_dot and raw_path.startswith("./"):
        raw_path = raw_path[2:]
    path = PurePosixPath(raw_path)
    parts = (raw_path[:-1] if raw_path.endswith("/") else raw_path).split("/")
    if path.is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise MinerUPackageError("mineru_path_invalid", "absolute_or_traversal")
    return path


def _contained_path(root: Path, relative: PurePosixPath) -> Path:
    candidate = root.joinpath(*relative.parts)
    if any(part.is_symlink() for part in [candidate, *candidate.parents] if part.is_relative_to(root)):
        raise MinerUPackageError("mineru_path_invalid", "symlink")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise MinerUPackageError("mineru_path_invalid", "outside_package_root")
    return resolved


def resolve_asset_path(raw_path: str, package_root: Path, content_list_dir: Path | None = None) -> tuple[Path | None, str]:
    """只允许根目录及选中 JSON 目录的精确相对寻址，拒绝多义命中。"""

    relative = validate_relative_path(raw_path, allow_leading_dot=True)
    root = package_root.resolve()
    bases = [root]
    if content_list_dir is not None:
        base = content_list_dir.resolve()
        if not base.is_relative_to(root):
            raise MinerUPackageError("mineru_path_invalid", "outside_package_root")
        bases.append(base)
    if raw_path.endswith("/"):
        return None, "not_regular_file"
    candidates = {_contained_path(root, PurePosixPath((base / str(relative)).relative_to(root).as_posix())) for base in bases}
    existing = sorted(path for path in candidates if path.exists())
    if len(existing) > 1:
        raise MinerUPackageError("mineru_path_invalid", "ambiguous_asset_reference")
    if not existing:
        return None, "missing"
    candidate = existing[0]
    if not stat.S_ISREG(candidate.stat().st_mode):
        return None, "not_regular_file"
    return candidate, "package_root" if candidate == root / str(relative) else "content_list_directory"


def _preflight_destination_identity(root: Path, members: list[zipfile.ZipInfo]) -> None:
    """在同文件系统的临时命名空间探测真实碰撞，不展开成员内容或猜测大小写规则。"""
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".mineru-preflight-", dir=root) as directory:
        probe_root = Path(directory)
        seen: set[tuple[int, int]] = set()
        for member in members:
            destination = probe_root.joinpath(*PurePosixPath(member.orig_filename).parts)
            try:
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists():
                        reason = "file_directory_conflict" if destination.is_dir() else "duplicate_normalized_path"
                        raise MinerUPackageError("mineru_path_invalid", reason)
                    destination.touch(exist_ok=False)
            except (FileExistsError, NotADirectoryError) as exc:
                raise MinerUPackageError("mineru_path_invalid", "file_directory_conflict") from exc
            identity = destination.stat()
            key = (identity.st_dev, identity.st_ino)
            if key in seen:
                raise MinerUPackageError("mineru_path_invalid", "duplicate_normalized_path")
            seen.add(key)


def extract_zip(zip_path: Path, target_dir: Path, *, policy: MinerUValidationPolicy = DEFAULT_POLICY) -> None:
    """先预检所有条目，再有界流式展开；不信任 ZIP 声明的大小。"""

    root = target_dir.resolve()
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
            if len(members) > policy.max_entries:
                raise MinerUPackageError("mineru_package_limit_exceeded", "entry_count")
            paths: set[str] = set()
            declared_total = 0
            destinations: list[tuple[zipfile.ZipInfo, Path]] = []
            for member in members:
                relative = validate_relative_path(member.orig_filename)
                canonical = str(relative)
                if canonical in paths:
                    raise MinerUPackageError("mineru_path_invalid", "duplicate_normalized_path")
                paths.add(canonical)
                mode = stat.S_IFMT(member.external_attr >> 16)
                expected_mode = stat.S_IFDIR if member.is_dir() else stat.S_IFREG
                if mode not in {0, expected_mode}:
                    raise MinerUPackageError("mineru_path_invalid", "special_zip_entry")
                if member.flag_bits & 1:
                    raise MinerUPackageError("mineru_package_invalid", "encrypted_entry")
                if member.file_size > policy.max_file_bytes:
                    raise MinerUPackageError("mineru_package_limit_exceeded", "single_file_bytes")
                declared_total += member.file_size
                if declared_total > policy.max_total_bytes:
                    raise MinerUPackageError("mineru_package_limit_exceeded", "total_bytes")
                destinations.append((member, _contained_path(root, relative)))
            file_paths = {PurePosixPath(member.orig_filename) for member, _destination in destinations if not member.is_dir()}
            for member, _destination in destinations:
                if any(parent in file_paths for parent in PurePosixPath(member.orig_filename).parents):
                    raise MinerUPackageError("mineru_path_invalid", "file_directory_conflict")
            _preflight_destination_identity(root, members)
            actual_total = 0
            for member, destination in destinations:
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                actual_file = 0
                with archive.open(member) as source, destination.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        actual_file += len(chunk)
                        actual_total += len(chunk)
                        if actual_file > policy.max_file_bytes or actual_total > policy.max_total_bytes:
                            raise MinerUPackageError("mineru_package_limit_exceeded", "actual_expanded_bytes")
                        output.write(chunk)
    except MinerUPackageError:
        raise
    except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError, EOFError, zlib.error, lzma.LZMAError) as exc:
        raise MinerUPackageError("mineru_package_invalid", "unreadable_archive") from exc


def find_content_list(package_root: Path) -> Path:
    """v2 优先，只有不存在 v2 时才选择 legacy；坏 v2 不回退。"""

    candidates = [path for path in package_root.rglob("*.json") if path.is_file() and
                  (path.name in {"content_list_v2.json", "content_list.json"} or
                   path.name.endswith(("_content_list_v2.json", "_content_list.json")))]
    if not candidates:
        raise MinerUPackageError("mineru_content_list_missing", "missing_content_list")
    return sorted(candidates, key=lambda item: (0 if item.name.endswith("content_list_v2.json") else 1,
                                               len(item.parts), item.as_posix()))[0]


def read_json_payload(path: Path, *, policy: MinerUValidationPolicy = DEFAULT_POLICY) -> tuple[Any, str]:
    """限制实际读取量并保留原始字节 hash；不重写输入 JSON。"""

    with path.open("rb") as stream:
        data = stream.read(policy.max_json_bytes + 1)
    if len(data) > policy.max_json_bytes:
        raise MinerUPackageError("mineru_package_limit_exceeded", "json_bytes")
    try:
        return json.loads(data.decode("utf-8")), hashlib.sha256(data).hexdigest()
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise MinerUPackageError("mineru_json_invalid", "unreadable_json") from exc


def load_content_blocks(content_list_path: Path) -> list[dict[str, Any]]:
    """兼容旧内部调用；非法节点必须显式失败，正式入口先做结构化验证。"""

    payload, _ = read_json_payload(content_list_path)
    blocks = payload.get("content_list") if isinstance(payload, dict) else payload
    if not isinstance(blocks, list):
        raise MinerUPackageError("mineru_json_invalid", "unsupported_top_level")
    return _flatten_content_blocks(blocks)


def _flatten_content_blocks(blocks: list[Any]) -> list[dict[str, Any]]:
    nested = any(isinstance(item, list) for item in blocks)
    flattened: list[dict[str, Any]] = []
    for page_index, item in enumerate(blocks):
        if nested and not isinstance(item, list):
            raise MinerUPackageError("mineru_page_invalid", "invalid_page")
        for block in item if nested else [item]:
            if not isinstance(block, dict):
                raise MinerUPackageError("mineru_block_invalid", "invalid_block")
            copied = dict(block)
            if nested:
                copied.setdefault("page_idx", page_index)
            flattened.append(copied)
    return flattened
