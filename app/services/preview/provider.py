"""Word 预览的唯一 I/O 端口，不依赖任务、DocumentIR 或翻译语义。"""

from typing import Protocol
from app.services.preview.models import PreviewPolicy, PreviewResult


class WordPreviewProvider(Protocol):
    def render(self, docx: bytes, *, policy: PreviewPolicy) -> PreviewResult: ...
