from __future__ import annotations

# app/infrastructure/persistence/__init__.py: 暴露 metadata persistence adapter 的组合入口。

from app.infrastructure.persistence.factory import (
    PersistenceAdapters,
    build_file_persistence_adapters,
    build_mysql_persistence_adapters,
    build_persistence_adapters,
    build_sqlite_persistence_adapters,
)

__all__ = [
    "PersistenceAdapters",
    "build_file_persistence_adapters",
    "build_mysql_persistence_adapters",
    "build_persistence_adapters",
    "build_sqlite_persistence_adapters",
]
