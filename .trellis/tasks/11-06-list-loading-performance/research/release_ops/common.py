"""本任务专用运维连接：显式环境、逐连接身份绑定与会话保护。"""
from __future__ import annotations

import json
import os


class OpsError(RuntimeError):
    """只携带受控错误代码，不含连接信息或业务内容。"""


def mysql_environment():
    names = ("host", "port", "user", "password", "database")
    if any("JOBS_MYSQL_" + name.upper() not in os.environ for name in names):
        raise OpsError("explicit_mysql_environment_required")
    values = {name: os.environ["JOBS_MYSQL_" + name.upper()] for name in names}
    if any(not values[name] for name in names):
        raise OpsError("empty_mysql_environment")
    values["port"] = int(values["port"])
    return values


def connection_factory(values, expected_database, expected_uuid, *, readonly, connector=None):
    """每条真正交给业务 owner 的连接都核对；不预检另一连接或自动重连。"""
    if values["database"] != expected_database or not expected_uuid:
        raise OpsError("target_binding_required")

    def connect():
        import pymysql
        connection = (connector or pymysql.connect)(
            **values, charset="utf8mb4", autocommit=False,
            connect_timeout=10, read_timeout=120, write_timeout=30,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT DATABASE() AS db, @@server_uuid AS uuid")
                identity = cursor.fetchone()
                if identity != {"db": expected_database, "uuid": expected_uuid}:
                    raise OpsError("database_identity_mismatch")
                cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                cursor.execute("SET SESSION TRANSACTION " + ("READ ONLY" if readonly else "READ WRITE"))
                cursor.execute("SET SESSION innodb_lock_wait_timeout=10")
                cursor.execute("SET SESSION lock_wait_timeout=10")
                cursor.execute("SET SESSION time_zone='+00:00'")
                cursor.execute("SELECT @@session.transaction_read_only AS ro, "
                               "@@session.transaction_isolation AS isolation_level, "
                               "@@session.innodb_lock_wait_timeout AS row_wait, "
                               "@@session.lock_wait_timeout AS ddl_wait")
                guards = cursor.fetchone()
                if guards != {"ro": int(readonly), "isolation_level": "REPEATABLE-READ",
                              "row_wait": 10, "ddl_wait": 10}:
                    raise OpsError("session_protection_not_effective")
            connection.rollback()
            return connection
        except BaseException:
            connection.close()
            raise
    return connect


def target_arguments(parser):
    parser.add_argument("--expect-database", required=True)
    parser.add_argument("--expect-server-uuid", required=True)


def safe_main(run):
    """入口阻止原异常消息泄漏；非成功始终保留非零退出状态。"""
    try:
        return run()
    except Exception as error:
        category = str(error) if isinstance(error, OpsError) else type(error).__name__
        print(json.dumps({"exit_code": 1, "error_category": category}, ensure_ascii=False))
        return 1
