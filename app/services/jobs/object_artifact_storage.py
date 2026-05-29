from __future__ import annotations

# app/services/jobs/object_artifact_storage.py: 提供基于 object_key 的本地和 S3-compatible artifact adapter。

import shutil
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from app.core.job_models import JobFile
from app.core.job_paths import JobPaths
from app.services.jobs.artifact_integrity import validate_artifact_fingerprint
from app.services.jobs.artifact_storage import DownloadArtifact, LocalArtifactStorageAdapter
from app.services.jobs.artifacts import ArtifactFileType, JobArtifactService


class ObjectArtifactStorageAdapter:
    """用本地目录模拟对象存储 adapter；生产对象存储可复用同一 object_key 合同。"""

    def __init__(self, artifact_contract: JobArtifactService, object_root: Path) -> None:
        self.artifact_contract = artifact_contract
        self.object_root = object_root
        self.local_fallback = LocalArtifactStorageAdapter(artifact_contract)
        self.object_root.mkdir(parents=True, exist_ok=True)

    def build_registered_file(self, file_type: ArtifactFileType, paths: JobPaths) -> JobFile:
        """把当前本地 artifact shadow upload 到对象目录，并返回 object metadata。"""

        local_file = self.local_fallback.build_registered_file(file_type, paths)
        return self.shadow_upload_registered_file(paths.root.name, paths, local_file)

    def shadow_upload_registered_file(self, job_id: str, paths: JobPaths, file: JobFile) -> JobFile:
        """上传已登记本地 artifact，保持 JobFile.path 不变并回填 object_key。"""

        source_path = self.local_fallback.resolve_download_path(paths, file)
        object_key = self.object_key_for(job_id, file.path)
        self.upload_local_artifact(object_key, source_path)
        return file.model_copy(update={"storage_backend": "object", "object_key": object_key})

    def object_key_for(self, job_id: str, logical_path: str) -> str:
        """按 job_id + logical path 生成稳定 object key。"""

        logical = PurePosixPath(logical_path)
        if logical.is_absolute() or any(part in {"", ".", ".."} for part in logical.parts):
            raise ValueError(f"产物逻辑路径不能生成 object_key: {logical_path}")
        return f"jobs/{job_id}/{logical.as_posix()}"

    def upload_local_artifact(self, object_key: str, source_path: Path) -> Path:
        """把本地 artifact 复制到对象目录；重复执行会覆盖同一 object_key。"""

        if not source_path.exists():
            raise FileNotFoundError(f"本地 artifact 不存在，无法 shadow upload: {source_path}")
        target_path = self.resolve_object_path(object_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_name(f"{target_path.name}.tmp")
        shutil.copy2(source_path, temp_path)
        temp_path.replace(target_path)
        return target_path

    def resolve_object_path(self, object_key: str) -> Path:
        """把 object_key 解析到对象目录内，禁止越界路径。"""

        resolved_root = self.object_root.resolve()
        candidate = (self.object_root / object_key).resolve()
        if candidate != resolved_root and resolved_root not in candidate.parents:
            raise ValueError(f"object_key 越界: {object_key}")
        return candidate

    def resolve_download(self, paths: JobPaths, file: JobFile) -> DownloadArtifact:
        """优先返回对象副本；对象缺失时保留 local fallback 下载能力。"""

        if file.storage_backend == "object" and file.object_key:
            object_path = self.resolve_object_path(file.object_key)
            if object_path.exists():
                validate_artifact_fingerprint(file, object_path)
                return DownloadArtifact.local_path(object_path)

        fallback_path = self.local_fallback.resolve_download_path(paths, file)
        if fallback_path.exists():
            return DownloadArtifact.local_path(fallback_path)

        if file.storage_backend == "object" and file.object_key:
            raise FileNotFoundError(
                f"对象 artifact 不存在且本地 fallback 不存在: object_key={file.object_key} path={file.path}"
            )
        raise FileNotFoundError(f"本地 artifact 不存在: path={file.path}")


class S3ArtifactStorageAdapter:
    """S3-compatible artifact adapter；上传本地 artifact，下载时返回签名重定向或对象流。"""

    def __init__(
        self,
        artifact_contract: JobArtifactService,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        key_prefix: str = "",
        public_base_url: str = "",
        download_mode: Literal["redirect", "stream"] = "redirect",
        presign_expires_seconds: int = 3600,
        client: Any | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("S3 artifact storage 需要配置 bucket。")
        self.artifact_contract = artifact_contract
        self.bucket = bucket
        self.key_prefix = self._normalize_key_prefix(key_prefix)
        self.public_base_url = public_base_url.rstrip("/")
        self.download_mode = download_mode
        self.presign_expires_seconds = presign_expires_seconds
        self.local_fallback = LocalArtifactStorageAdapter(artifact_contract)
        self.client = client or self._build_boto3_client(
            endpoint_url=endpoint_url,
            region_name=region_name,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
        )

    def build_registered_file(self, file_type: ArtifactFileType, paths: JobPaths) -> JobFile:
        """把当前本地 artifact 上传到 S3-compatible bucket，并返回 object metadata。"""

        local_file = self.local_fallback.build_registered_file(file_type, paths)
        return self.shadow_upload_registered_file(paths.root.name, paths, local_file)

    def shadow_upload_registered_file(self, job_id: str, paths: JobPaths, file: JobFile) -> JobFile:
        """上传已登记本地 artifact，保持 JobFile.path 不变并回填 S3 object_key。"""

        source_path = self.local_fallback.resolve_download_path(paths, file)
        object_key = self.object_key_for(job_id, file.path)
        self.upload_local_artifact(
            object_key,
            source_path,
            content_type=self.artifact_contract.media_type_for_file(file),
        )
        return file.model_copy(
            update={
                "storage_backend": "object",
                "object_key": object_key,
                "public_url": self.public_url_for(object_key),
            }
        )

    def object_key_for(self, job_id: str, logical_path: str) -> str:
        """按可选 prefix + job_id + logical path 生成稳定 S3 object key。"""

        if not job_id or "/" in job_id:
            raise ValueError(f"job_id 不能生成 object_key: {job_id}")
        logical = PurePosixPath(logical_path)
        if logical.is_absolute() or any(part in {"", ".", ".."} for part in logical.parts):
            raise ValueError(f"产物逻辑路径不能生成 object_key: {logical_path}")
        object_key = f"jobs/{job_id}/{logical.as_posix()}"
        if self.key_prefix:
            return f"{self.key_prefix}/{object_key}"
        return object_key

    def upload_local_artifact(self, object_key: str, source_path: Path, *, content_type: str) -> None:
        """通过 S3 API 上传本地 artifact；重复执行覆盖同一 object_key。"""

        if not source_path.exists():
            raise FileNotFoundError(f"本地 artifact 不存在，无法上传到 S3: {source_path}")
        self.client.upload_file(
            str(source_path),
            self.bucket,
            object_key,
            ExtraArgs={"ContentType": content_type},
        )

    def public_url_for(self, object_key: str) -> str | None:
        """如果配置了公开基地址，生成只读展示 URL；真正下载仍走 download_url。"""

        if not self.public_base_url:
            return None
        return f"{self.public_base_url}/{object_key}"

    def resolve_download(self, paths: JobPaths, file: JobFile) -> DownloadArtifact:
        """按配置返回 S3 临时重定向或流；旧 local 记录继续走本地 fallback。"""

        if file.storage_backend == "object" and file.object_key:
            if self.download_mode == "redirect":
                return DownloadArtifact.redirect(self.build_presigned_download_url(file.object_key))
            try:
                return DownloadArtifact.stream(self.stream_object(file.object_key))
            except FileNotFoundError:
                pass

        fallback_path = self.local_fallback.resolve_download_path(paths, file)
        if fallback_path.exists():
            return DownloadArtifact.local_path(fallback_path)

        if file.storage_backend == "object" and file.object_key:
            raise FileNotFoundError(
                f"S3 artifact 不存在且本地 fallback 不存在: object_key={file.object_key} path={file.path}"
            )
        raise FileNotFoundError(f"本地 artifact 不存在: path={file.path}")

    def build_presigned_download_url(self, object_key: str) -> str:
        """生成 S3 get_object 临时签名 URL。"""

        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=self.presign_expires_seconds,
        )

    def stream_object(self, object_key: str) -> Iterator[bytes]:
        """从 S3 get_object Body 生成下载流。"""

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=object_key)
        except Exception as exc:
            if self._is_missing_object_error(exc):
                raise FileNotFoundError(f"S3 artifact 不存在: object_key={object_key}") from exc
            raise
        body = response.get("Body")
        if body is None:
            raise RuntimeError(f"S3 get_object 响应缺少 Body: object_key={object_key}")
        return self._iter_body_chunks(body)

    def _iter_body_chunks(self, body: Any, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        try:
            while True:
                chunk = body.read(chunk_size)
                if not chunk:
                    break
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                yield chunk
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()

    def _build_boto3_client(
        self,
        *,
        endpoint_url: str | None,
        region_name: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
    ) -> Any:
        try:
            import boto3
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on deployment env
            raise RuntimeError("JOBS_ARTIFACT_STORAGE_BACKEND=s3 需要安装 boto3。") from exc

        kwargs: dict[str, str] = {}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        if region_name:
            kwargs["region_name"] = region_name
        if access_key_id:
            kwargs["aws_access_key_id"] = access_key_id
        if secret_access_key:
            kwargs["aws_secret_access_key"] = secret_access_key
        return boto3.client("s3", **kwargs)

    def _normalize_key_prefix(self, key_prefix: str) -> str:
        stripped = key_prefix.strip().strip("/")
        if not stripped:
            return ""
        prefix = PurePosixPath(stripped)
        if prefix.is_absolute() or any(part in {"", ".", ".."} for part in prefix.parts):
            raise ValueError(f"S3 object_key prefix 非法: {key_prefix}")
        return prefix.as_posix()

    def _is_missing_object_error(self, exc: Exception) -> bool:
        response = getattr(exc, "response", None)
        if not isinstance(response, dict):
            return False
        error = response.get("Error")
        if not isinstance(error, dict):
            return False
        return str(error.get("Code")) in {"NoSuchKey", "NoSuchBucket", "404", "NotFound"}
