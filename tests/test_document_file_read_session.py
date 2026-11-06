"""请求内连接生命周期、原错误边界与 singleton 并发隔离。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
import json
from threading import Barrier, get_ident
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from app.core.config import Settings
from app.core.errors import ApiError
from app.domains.document_jobs.incidents import DocumentJobIncidentService
from app.domains.document_jobs.service import DocumentJobService
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.files import MysqlDocumentFileRepository
from tests.test_document_job_list_query_v2_writers import FakeMysqlConnection
from tests import test_document_job_list_query_v2_service as fixtures
from tests.test_document_job_incident_publish_light_check import query_values


class ReadConnection(FakeMysqlConnection):
    """记录真实仓储调用顺序；不模拟数据库隔离。"""
    def __init__(self, payload=None, protected="[]"):
        super().__init__(payload)
        self.protected = protected
        self.events = []
        self.owner = get_ident()

    def execute(self, sql, params=()):
        assert self.owner == get_ident(), "连接不能跨请求线程共享"
        self.events.append("execute")
        super().execute(sql, params)

    def fetchall(self):
        return [{"protected_file_ids": self.protected}]

    def commit(self):
        self.events.append("commit")
        super().commit()

    def rollback(self):
        self.events.append("rollback")
        super().rollback()

    def close(self):
        self.events.append("close")
        super().close()


def backend(factory):
    return MysqlPersistenceBackend(MysqlPersistenceConfig("unused", 3306, "unused", "", "unused"),
                                   initialize=False, connect_factory=factory)


class DocumentFileReadSessionTests(TestCase):
    def test_lazy_connection_and_68_gets_24_protection_reads_keep_each_commit(self):
        connection = ReadConnection(fixtures.make_file().model_dump_json())
        factory = Mock(return_value=connection)
        files = MysqlDocumentFileRepository(backend(factory))
        with files.read_session():
            factory.assert_not_called()
        with files.read_session() as reader:
            self.assertIsNot(reader, files)
            for _ in range(68):
                self.assertEqual(reader.get_document_file("result").id, "result")
            for _ in range(24):
                self.assertFalse(reader.is_document_file_protected("result"))
            self.assertEqual((connection.commits, connection.rollbacks, connection.closes), (92, 0, 0))
        factory.assert_called_once_with()
        self.assertEqual(connection.events, ["execute", "commit"] * 92 + ["close"])

    def test_file_payload_and_id_errors_remain_after_commit(self):
        for payload in ("{broken", "{}", fixtures.make_file(file_id="different").model_dump_json()):
            with self.subTest(payload=payload[:10]):
                connection = ReadConnection(payload)
                factory = Mock(return_value=connection)
                with self.assertRaises(ValueError), MysqlDocumentFileRepository(backend(factory)).read_session() as reader:
                    reader.get_document_file("result")
                self.assertEqual(connection.events, ["execute", "commit", "close"])
                factory.assert_called_once()

    def test_protection_json_error_rolls_back_before_close(self):
        connection = ReadConnection(protected="{broken")
        with self.assertRaises(json.JSONDecodeError), MysqlDocumentFileRepository(
                backend(lambda: connection)).read_session() as reader:
            reader.is_document_file_protected("result")
        self.assertEqual(connection.events, ["execute", "rollback", "close"])

    def test_sql_and_commit_failures_preserve_error_and_do_not_reconnect(self):
        for stage in ("execute", "commit"):
            for session in (False, True):
                with self.subTest(stage=stage, session=session):
                    connection = ReadConnection(fixtures.make_file().model_dump_json())
                    failure = RuntimeError("测试读取失败")
                    setattr(connection, stage, Mock(side_effect=failure))
                    factory = Mock(return_value=connection)
                    files = MysqlDocumentFileRepository(backend(factory))
                    with self.assertRaises(RuntimeError) as caught:
                        if session:
                            with files.read_session() as reader:
                                reader.get_document_file("result")
                        else:
                            files.get_document_file("result")
                    self.assertIs(caught.exception, failure)
                    self.assertEqual((connection.rollbacks, connection.closes), (1, 1))
                    factory.assert_called_once()

    def test_connect_and_close_failures_are_not_hidden(self):
        failure = RuntimeError("测试建连失败")
        factory = Mock(side_effect=failure)
        with self.assertRaises(RuntimeError) as caught, MysqlDocumentFileRepository(backend(factory)).read_session() as reader:
            reader.get_document_file("missing")
        self.assertIs(caught.exception, failure)
        factory.assert_called_once()
        connection = ReadConnection()
        connection.close = Mock(side_effect=RuntimeError("测试关闭失败"))
        with self.assertRaisesRegex(RuntimeError, "测试关闭失败"), MysqlDocumentFileRepository(
                backend(lambda: connection)).read_session() as reader:
            self.assertIsNone(reader.get_document_file("missing"))
        self.assertEqual((connection.commits, connection.rollbacks), (1, 0))

    def test_session_reader_does_not_redirect_regular_reads_or_writes(self):
        connections = []
        def connect():
            connection = ReadConnection(fixtures.make_file().model_dump_json())
            connections.append(connection)
            return connection
        files = MysqlDocumentFileRepository(backend(connect))
        with files.read_session() as reader:
            reader.get_document_file("result")
            files.get_document_file("result")
            # 即使局部仓储被内部写者持有，其写锁仍只能走原 backend.connect。
            with reader._locked_file("result"):
                pass
            reader.get_document_file("result")
            self.assertEqual([c.closes for c in connections], [0, 1, 1])
        self.assertEqual([c.commits for c in connections], [2, 1, 1])
        self.assertEqual([c.closes for c in connections], [1, 1, 1])
        self.assertIsNone(files._read_connect)


class IncidentReadSessionTests(TestCase):
    def test_validation_precedes_session_and_page_actions_follow_close(self):
        fixture = fixtures.DocumentJobListV2ServiceTests()
        with fixture.environment("sqlite") as (jobs, files, service):
            jobs.create_document_job(fixtures.make_job(status="failed", stage="failed"))
            incidents = DocumentJobIncidentService(service)
            with patch.object(files, "read_session") as session:
                with self.assertRaises(ApiError):
                    incidents.list_incidents(**query_values(sort="invalid"))
                session.assert_not_called()
            events = []
            original = files.read_session
            @contextmanager
            def session():
                events.append("enter")
                with original() as reader:
                    yield reader
                events.append("exit")
            build = service.build_job_read_view
            def page(*args, **kwargs):
                self.assertEqual(events, ["enter", "exit"])
                return build(*args, **kwargs)
            with patch.object(files, "read_session", session), patch.object(service, "build_job_read_view", page):
                self.assertEqual(incidents.list_incidents(**query_values()).total, 1)

    def test_first_review_downgrade_cannot_be_promoted_by_later_observation(self):
        fixture = fixtures.DocumentJobListV2ServiceTests()
        with fixture.environment("sqlite") as (jobs, files, service), patch(
                "app.domains.document_jobs.service.utc_now", return_value=fixtures.NOW):
            _, file = fixture.verified(jobs, files, review="blocked")
            reader = SimpleNamespace(get_document_file=Mock(side_effect=[
                file.model_copy(update={"review_source_revision": 1}), file]),
                is_document_file_protected=Mock(return_value=False))
            @contextmanager
            def session():
                yield reader
            with patch.object(files, "read_session", session):
                result = DocumentJobIncidentService(service).list_incidents(**query_values())
            self.assertEqual(result.total, 0)
            self.assertEqual(reader.get_document_file.call_count, 2)

    def test_naive_expiry_propagates_and_closes_session_after_file_commit(self):
        file = fixtures.make_file().model_copy(update={"expires_at": fixtures.NOW.replace(tzinfo=None)})
        connection = ReadConnection(file.model_dump_json())
        files = MysqlDocumentFileRepository(backend(lambda: connection))
        job = fixtures.make_job(status="succeeded", stage="completed", result_file_id=file.id)
        service = DocumentJobService(Settings.model_construct(),
            SimpleNamespace(list_document_jobs=lambda: [job]), SimpleNamespace(), files)
        with patch("app.domains.document_jobs.service.utc_now", return_value=fixtures.NOW), self.assertRaises(TypeError):
            DocumentJobIncidentService(service).list_incidents(**query_values())
        self.assertEqual(connection.events, ["execute", "commit", "close"])

    def test_same_singleton_concurrent_requests_use_separate_sessions(self):
        file = fixtures.make_file().model_copy(update={"expires_at": fixtures.NOW - timedelta(seconds=1)})
        barrier = Barrier(2)
        connections = []
        def connect():
            connection = ReadConnection(file.model_dump_json())
            connections.append(connection)
            barrier.wait(timeout=5)
            return connection
        files = MysqlDocumentFileRepository(backend(connect))
        job = fixtures.make_job(status="succeeded", stage="completed", result_file_id=file.id)
        service = DocumentJobService(Settings.model_construct(),
            SimpleNamespace(list_document_jobs=lambda: [job]), SimpleNamespace(), files)
        incidents = DocumentJobIncidentService(service)
        with patch("app.domains.document_jobs.service.utc_now", return_value=fixtures.NOW), ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(incidents.list_incidents, **query_values()) for _ in range(2)]
            self.assertEqual([future.result(timeout=10).total for future in futures], [0, 0])
        self.assertEqual(len({c.owner for c in connections}), 2)
        self.assertEqual([(c.commits, c.rollbacks, c.closes) for c in connections], [(2, 0, 1), (2, 0, 1)])
        self.assertIs(service.file_repository, files)
        self.assertIsNone(files._read_connect)
