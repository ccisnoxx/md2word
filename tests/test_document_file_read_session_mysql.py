"""真实 MySQL RR：同一物理连接的逐操作事务仍看见外部新提交。"""
import json
import os
from unittest import TestCase

import pymysql

from app.domains.document_jobs.list_query import document_file_review_storage_from_raw
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.files import MysqlDocumentFileRepository
from app.infrastructure.persistence.mysql.schema import MYSQL_SCHEMA_STATEMENTS
from tests.test_document_job_list_query_v2_mysql import _temporary_schema
from tests.test_document_job_list_query_v2_service import make_file


class TrackedConnection:
    """只记录事务收尾；SQL 与隔离行为交给真实连接。"""
    def __init__(self, connection):
        self.connection = connection
        self.commits = self.rollbacks = self.closes = 0

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        self.commits += 1
        self.connection.commit()

    def rollback(self):
        self.rollbacks += 1
        self.connection.rollback()

    def close(self):
        self.closes += 1
        self.connection.close()


class MysqlDocumentFileReadSessionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.options, cls.schema = cls.enterClassContext(_temporary_schema(os.environ))
        cls.config = MysqlPersistenceConfig(cls.options["host"], cls.options["port"], cls.options["user"],
                                           cls.options["password"], cls.schema)
        cls.backend = MysqlPersistenceBackend(cls.config, initialize=False, connect_factory=cls.connect)
        cls.files = MysqlDocumentFileRepository(cls.backend)
        with cls.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute(next(sql for sql in MYSQL_SCHEMA_STATEMENTS
                                if sql.strip().startswith("CREATE TABLE IF NOT EXISTS document_job_publications (")))

    @classmethod
    def connect(cls):
        return pymysql.connect(**cls.options, database=cls.schema, autocommit=False)

    def setUp(self):
        with self.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM document_job_publications")
            cursor.execute("DELETE FROM document_files")
        self.files.create_document_file(make_file())
        self.connections = []
        def connect():
            connection = self.connect()
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                cursor.execute("SELECT @@transaction_isolation AS isolation")
                self.assertEqual(cursor.fetchone()["isolation"], "REPEATABLE-READ")
            connection.rollback()
            tracked = TrackedConnection(connection)
            self.connections.append(tracked)
            return tracked
        self.reader_files = MysqlDocumentFileRepository(MysqlPersistenceBackend(
            self.config, initialize=False, connect_factory=connect))

    def test_each_read_starts_new_snapshot_after_external_writer_commit(self):
        with self.reader_files.read_session() as reader:
            self.assertIsNone(reader.get_document_file("result").etag)
            connection = self.connections[0]
            reader_id = connection.connection.thread_id()
            with self.backend.connect() as writer:
                self.assertNotEqual(reader_id, writer.thread_id())
            changed = self.files.update_document_file("result", etag="新观察")
            self.assertEqual(reader.get_document_file("result"), changed)
            self.assertFalse(reader.is_document_file_protected("result"))
            with self.backend.connect() as writer, writer.cursor() as cursor:
                cursor.execute("INSERT INTO document_job_publications "
                    "(publication_id,job_id,tenant_id,company_id,generation,source_file_id,result_file_id,"
                    "result_sha256,request_id,published_at,protected_file_ids,payload) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    ("publication", "job", "T", "C", 0, "source", "result", changed.checksum_sha256,
                     "request", changed.created_at.isoformat(), '["result"]', "{}"))
                cursor.execute("SELECT payload,review_query_json,review_descriptor_key,review_receipt_key "
                               "FROM document_files WHERE file_id='result'")
                row = cursor.fetchone()
                self.assertEqual(tuple(row[name] for name in ("review_query_json", "review_descriptor_key", "review_receipt_key")),
                                 document_file_review_storage_from_raw(row["payload"]))
            self.assertTrue(reader.is_document_file_protected("result"))
            self.assertEqual(connection.connection.thread_id(), reader_id)
            self.assertEqual((len(self.connections), connection.commits, connection.rollbacks, connection.closes), (1, 4, 0, 0))
        self.assertEqual(connection.closes, 1)
        self.assertFalse(connection.connection.open)

    def test_corrupt_file_commits_but_protection_parse_error_rolls_back(self):
        for payload in ("{broken", "{}", make_file(file_id="wrong").model_dump_json()):
            with self.subTest(payload=payload[:10]):
                with self.backend.connect() as connection, connection.cursor() as cursor:
                    cursor.execute("UPDATE document_files SET payload=%s WHERE file_id='result'", (payload,))
                with self.assertRaises(ValueError), self.reader_files.read_session() as reader:
                    reader.get_document_file("result")
                tracked = self.connections[-1]
                self.assertEqual((tracked.commits, tracked.rollbacks, tracked.closes), (1, 0, 1))
        with self.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("INSERT INTO document_job_publications "
                "(publication_id,job_id,tenant_id,company_id,generation,source_file_id,result_file_id,"
                "result_sha256,request_id,published_at,protected_file_ids,payload) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                ("publication", "job", "T", "C", 0, "source", "result", "hash", "request", "now", "{broken", "{}"))
        with self.assertRaises(json.JSONDecodeError), self.reader_files.read_session() as reader:
            reader.is_document_file_protected("result")
        tracked = self.connections[-1]
        self.assertEqual((tracked.commits, tracked.rollbacks, tracked.closes), (0, 1, 1))
