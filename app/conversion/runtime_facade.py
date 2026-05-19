from __future__ import annotations

from input_adapter_runtime import load_pages, materialize_input
from app.conversion.runtime_runner import run_conversion

from app.conversion.runtime_helpers import resolve_document_language

# Stage 1 compatibility seam:
# FastAPI imports shared conversion entrypoints from here instead of reaching
# into the root CLI script directly. Later refactor stages can replace the
# backing implementation without changing FastAPI call sites again.

__all__ = [
    "load_pages",
    "materialize_input",
    "run_conversion",
    "resolve_document_language",
]
