from __future__ import annotations

# app/services/jobs/artifact_storage.py: 定义 jobs artifact 存储 adapter 和下载结果合同边界。

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from app.core.job_models import JobFile
from app.core.job_paths import JobPaths, resolve_artifact_path
from app.services.jobs.artifact_integrity import attach_artifact_fingerprint, validate_artifact_fingerprint
from app.services.jobs.artifacts import ArtifactFileType, JobArtifactService


@dataclass(frozen=True, slots=True)
class DownloadArtifact:
    """artifact 下载结果合同；API 层据此选择本地文件、流式响应或重定向。"""

    kind: Literal["local_path", "stream", "redirect"]
    path: Path | None = None
    content: Iterable[bytes] | None = None
    redirect_url: str | None = None

    @classmethod
    def local_path(cls, path: Path) -> "DownloadArtifact":
        return cls(kind="local_path", path=path)

    @classmethod
    def stream(cls, content: Iterable[bytes]) -> "DownloadArtifact":
        return cls(kind="stream", content=content)

    @classmethod
    def redirect(cls, url: str) -> "DownloadArtifact":
        return cls(kind="redirect", redirect_url=url)


class ArtifactStorageProtocol(Protocol):
    """Artifact 存储 adapter 的最小合同，下载结果不再绑定到本地 Path。"""

    def build_registered_file(self, file_type: ArtifactFileType, paths: JobPaths) -> JobFile: ...
    def resolve_download(self, paths: JobPaths, file: JobFile) -> DownloadArtifact: ...


class LocalArtifactStorageAdapter:
    """基于 JobPaths 的本地 artifact storage adapter，保持现有逻辑路径合同不变。"""

    def __init__(self, artifact_contract: JobArtifactService) -> None:
        self.artifact_contract = artifact_contract

    def build_registered_file(self, file_type: ArtifactFileType, paths: JobPaths) -> JobFile:
        """按本地 JobPaths 生成持久化的 JobFile 记录。"""

        file = JobFile(file_type=file_type, path=self.logical_path_for_file_type(file_type, paths))
        return attach_artifact_fingerprint(file, self.resolve_download_path(paths, file, validate_integrity=False))

    def logical_path_for_file_type(self, file_type: ArtifactFileType, paths: JobPaths) -> str:
        """把 artifact 合同中的 path_attr 解析成 job 内逻辑路径。"""

        spec = self.artifact_contract.spec_for_file_type(file_type)
        absolute_path = getattr(paths, spec.path_attr)
        return str(absolute_path.relative_to(paths.root))

    def resolve_download_path(self, paths: JobPaths, file: JobFile, *, validate_integrity: bool = True) -> Path:
        """校验 JobFile 逻辑路径后解析为本地绝对下载路径。"""

        expected_logical_path = self.logical_path_for_file_type(file.file_type, paths)
        if file.path != expected_logical_path:
            raise ValueError(
                f"产物逻辑路径不匹配: expected={expected_logical_path} actual={file.path}"
            )
        artifact_path = resolve_artifact_path(paths, file.path)
        if validate_integrity:
            validate_artifact_fingerprint(file, artifact_path)
        return artifact_path

    def resolve_download(self, paths: JobPaths, file: JobFile) -> DownloadArtifact:
        """返回本地文件下载结果，保持现有 local adapter 行为不变。"""

        return DownloadArtifact.local_path(self.resolve_download_path(paths, file))
