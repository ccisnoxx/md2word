from __future__ import annotations

# app/infrastructure/persistence/mysql/backend.py: MySQL metadata backend 的连接和 payload 辅助能力。

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from app.infrastructure.persistence.mysql.schema import initialize_schema

try:  # pragma: no cover - optional runtime dependency is exercised via fake connections in tests.
    import pymysql
except ImportError:  # pragma: no cover
    pymysql = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class MysqlPersistenceConfig:
    """MySQL connection settings for metadata persistence adapters."""

    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"
    connect_timeout_seconds: int = 10


ConnectFactory = Callable[[], Any]


class MysqlPersistenceBackend:
    """保存 MySQL 连接配置并提供当前 adapter 的 commit/rollback 语义。"""

    def __init__(
        self,
        config: MysqlPersistenceConfig,
        *,
        connect_factory: ConnectFactory | None = None,
        initialize: bool = True,
    ) -> None:
        self.config = config
        self._connect_factory = connect_factory or self._build_pymysql_connection
        if initialize:
            self.initialize_schema()

    def _build_pymysql_connection(self) -> Any:
        if pymysql is None:
            raise RuntimeError("JOBS_REPOSITORY_BACKEND=mysql 需要安装 PyMySQL 依赖。")
        return pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset=self.config.charset,
            connect_timeout=self.config.connect_timeout_seconds,
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )

    @contextmanager
    def connect(self) -> Iterator[Any]:
        connection = self._connect_factory()
        try:
            yield connection
            connection.commit()
        except Exception:
            if hasattr(connection, "rollback"):
                connection.rollback()
            raise
        finally:
            connection.close()

    def initialize_schema(self) -> None:
        with self.connect() as connection:
            initialize_schema(connection)

    def dump_payload(self, model: Any) -> str:
        return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)
