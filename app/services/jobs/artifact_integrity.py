from __future__ import annotations

# app/services/jobs/artifact_integrity.py: 计算和校验 jobs artifact 的 size / sha256 指纹。

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.core.job_models import JobFile


@dataclass(frozen=True, slots=True)
class ArtifactFingerprint:
    """artifact 内容指纹，sha256 使用带算法前缀的稳定字符串格式。"""

    size_bytes: int
    sha256: str


class ArtifactFingerprintMismatch(ValueError):
    """已登记 artifact 的大小或 sha256 与当前文件内容不一致。"""


def compute_artifact_fingerprint(path: Path) -> ArtifactFingerprint:
    """读取本地文件并计算 artifact 的大小和 sha256。"""

    if not path.exists():
        raise FileNotFoundError(f"artifact 文件不存在，无法计算 fingerprint: {path}")
    digest = hashlib.sha256()
    size_bytes = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size_bytes += len(chunk)
            digest.update(chunk)
    return ArtifactFingerprint(size_bytes=size_bytes, sha256=f"sha256:{digest.hexdigest()}")


def attach_artifact_fingerprint(file: JobFile, path: Path) -> JobFile:
    """把本地文件当前内容的 fingerprint 写入 JobFile。"""

    fingerprint = compute_artifact_fingerprint(path)
    return file.model_copy(
        update={
            "size_bytes": fingerprint.size_bytes,
            "sha256": fingerprint.sha256,
        }
    )


def validate_artifact_fingerprint(file: JobFile, path: Path) -> None:
    """校验本地 artifact 文件存在且与 JobFile 已登记 fingerprint 一致。"""

    if not path.exists():
        raise FileNotFoundError(f"产物文件不存在: file_type={file.file_type} path={file.path}")
    if file.size_bytes is None and file.sha256 is None:
        return

    fingerprint = compute_artifact_fingerprint(path)
    if file.size_bytes is not None and file.size_bytes != fingerprint.size_bytes:
        raise ArtifactFingerprintMismatch(
            "产物大小不匹配: "
            f"file_type={file.file_type} path={file.path} expected={file.size_bytes} actual={fingerprint.size_bytes}"
        )
    if file.sha256 is not None and file.sha256 != fingerprint.sha256:
        raise ArtifactFingerprintMismatch(
            "产物 sha256 不匹配: "
            f"file_type={file.file_type} path={file.path} expected={file.sha256} actual={fingerprint.sha256}"
        )
