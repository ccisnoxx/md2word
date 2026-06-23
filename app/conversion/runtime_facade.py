from __future__ import annotations

from pathlib import Path
from typing import Any

from app.conversion.runtime.input_adapter_runtime import load_pages as _load_pages
from app.conversion.runtime.input_adapter_runtime import materialize_input
from app.conversion.runtime_runner import ensure_runtime_bound, run_conversion

from app.conversion.runtime_helpers import resolve_document_language

# Stage 1 compatibility seam:
# FastAPI imports shared conversion entrypoints from here instead of reaching
# into the root CLI script directly. Later refactor stages can replace the
# backing implementation without changing FastAPI call sites again.


def load_pages(package_root: Path) -> tuple[list[Any], Path]:
    ensure_runtime_bound()
    return _load_pages(package_root)


__all__ = [
    "load_pages",
    "materialize_input",
    "run_conversion",
    "resolve_document_language",
]
