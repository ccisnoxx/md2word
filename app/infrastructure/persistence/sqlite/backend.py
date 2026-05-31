from __future__ import annotations

# app/infrastructure/persistence/sqlite/backend.py: sqlite metadata backend 的连接和 payload 辅助能力。

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.infrastructure.persistence.sqlite.schema import initialize_schema


class SqlitePersistenceBackend:
    """保存 sqlite database 路径并提供每次方法调用的短连接语义。"""

    def __init__(self, database_path: Path, *, initialize: bool = True) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        if initialize:
            self.initialize_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.database_path), timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize_schema(self) -> None:
        with self.connect() as connection:
            initialize_schema(connection)

    def dump_payload(self, model: Any) -> str:
        return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)
