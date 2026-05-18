from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from app.core.job_models import JobFile, JobRecord
from app.core.job_paths import JobPaths, resolve_artifact_path


ArtifactAlias = Literal["source-package", "source-pdf", "translation-request", "result"]
ArtifactFileType = Literal["source_package", "source_pdf", "translation_request", "result_docx"]


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    file_type: ArtifactFileType
    alias: ArtifactAlias
    path_attr: str
    media_type: str


ARTIFACT_SPECS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec(
        file_type="source_package",
        alias="source-package",
        path_attr="source_package",
        media_type="application/zip",
    ),
    ArtifactSpec(
        file_type="source_pdf",
        alias="source-pdf",
        path_attr="source_pdf",
        media_type="application/pdf",
    ),
    ArtifactSpec(
        file_type="translation_request",
        alias="translation-request",
        path_attr="translation_request",
        media_type="application/json",
    ),
    ArtifactSpec(
        file_type="result_docx",
        alias="result",
        path_attr="result_docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
)

ARTIFACT_SPEC_BY_ALIAS = {spec.alias: spec for spec in ARTIFACT_SPECS}
ARTIFACT_SPEC_BY_FILE_TYPE = {spec.file_type: spec for spec in ARTIFACT_SPECS}
ARTIFACT_ORDER = {spec.file_type: index for index, spec in enumerate(ARTIFACT_SPECS)}


class JobArtifactService:
    def sort_files(self, files: list[JobFile]) -> list[JobFile]:
        return sorted(files, key=lambda item: (ARTIFACT_ORDER.get(item.file_type, 999), item.path))

    def build_registered_file(self, file_type: ArtifactFileType, paths: JobPaths) -> JobFile:
        return JobFile(file_type=file_type, path=self.logical_path_for_file_type(file_type, paths))

    def logical_path_for_file_type(self, file_type: ArtifactFileType, paths: JobPaths) -> str:
        spec = self.spec_for_file_type(file_type)
        absolute_path = getattr(paths, spec.path_attr)
        return str(absolute_path.relative_to(paths.root))

    def spec_for_alias(self, alias: str) -> ArtifactSpec:
        spec = ARTIFACT_SPEC_BY_ALIAS.get(alias)
        if spec is None:
            raise KeyError(f"不支持的产物 alias: {alias}")
        return spec

    def spec_for_file_type(self, file_type: str) -> ArtifactSpec:
        spec = ARTIFACT_SPEC_BY_FILE_TYPE.get(file_type)
        if spec is None:
            raise KeyError(f"不支持的产物 file_type: {file_type}")
        return spec

    def alias_for_file(self, file: JobFile) -> ArtifactAlias:
        return self.spec_for_file_type(file.file_type).alias

    def media_type_for_file(self, file: JobFile) -> str:
        return self.spec_for_file_type(file.file_type).media_type

    def resolve_download_path(self, paths: JobPaths, file: JobFile) -> Path:
        expected_logical_path = self.logical_path_for_file_type(file.file_type, paths)
        if file.path != expected_logical_path:
            raise ValueError(
                f"产物逻辑路径不匹配: expected={expected_logical_path} actual={file.path}"
            )
        return resolve_artifact_path(paths, file.path)

    def build_download_url(
        self,
        *,
        job_id: str,
        file: JobFile,
        url_for: Callable[..., str],
    ) -> str:
        return str(url_for("download_artifact", job_id=job_id, artifact_alias=self.alias_for_file(file)))

    def build_download_filename(self, job: JobRecord, file: JobFile) -> str:
        if file.file_type == "source_package":
            return job.source_filename
        if file.file_type == "source_pdf":
            return job.source_filename
        if file.file_type == "translation_request":
            return f"{job.id}-translation-request.json"
        if file.file_type == "result_docx":
            return f"{Path(job.source_filename).stem}.docx"
        return Path(file.path).name
