from __future__ import annotations

# app/domains/files/repository.py: 定义 document_files metadata repository 端口。

from typing import Any, Protocol

from app.domains.files.models import DocumentFileRecord


class DocumentFileRepositoryProtocol(Protocol):
    """独立文件资产 metadata 读写合同。"""

    def create_document_file(self, record: DocumentFileRecord) -> DocumentFileRecord: ...
    def get_document_file(self, file_id: str) -> DocumentFileRecord | None: ...
    def list_document_files(self) -> list[DocumentFileRecord]: ...
    def update_document_file(self, file_id: str, **patch: Any) -> DocumentFileRecord: ...
