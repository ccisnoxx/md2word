from __future__ import annotations

import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from starlette.requests import Request

from app.core.errors import ApiError
from app.domains.audit.models import ActorContext
from app.domains.files.models import DocumentFileRecord
from app.domains.files.router import upload_file_content
from app.services.auth.models import AuthenticatedUser


class FileUploadAsyncTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.user = AuthenticatedUser(
            id="user_upload",
            username="upload_operator",
            role="operator",
            tenant_id="tenant_upload",
            company_id="company_upload",
        )
        self.record = DocumentFileRecord(
            id="file_upload",
            tenant_id=self.user.tenant_id,
            company_id=self.user.company_id,
            file_type="source_pdf",
            storage_provider="local_object",
            bucket="",
            object_key="source/file_upload.pdf",
            original_filename="source.pdf",
            mime_type="application/pdf",
            size_bytes=8,
            status="uploaded",
            created_by=self.user.id,
        )
        self.runtime = SimpleNamespace(
            settings=SimpleNamespace(jobs_upload_max_bytes=8),
            file_upload_service=SimpleNamespace(upload_authorized_content=Mock(return_value=self.record)),
            audit_service=SimpleNamespace(record=Mock()),
        )

    def _request(self, *chunks: bytes) -> Request:
        loop_thread = threading.get_ident()
        messages = iter(
            {
                "type": "http.request",
                "body": chunk,
                "more_body": index < len(chunks) - 1,
            }
            for index, chunk in enumerate(chunks)
        )

        async def receive():
            self.assertEqual(threading.get_ident(), loop_thread)
            return next(messages)

        return Request(
            {
                "type": "http",
                "method": "PUT",
                "path": "/files/file_upload/content",
                "headers": [(b"content-type", b"application/pdf")],
            },
            receive,
        )

    async def test_upload_and_audit_allow_event_loop_to_progress(self) -> None:
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()
        phases: list[str] = []
        worker_threads: list[int] = []

        def observe_loop_progress(phase: str) -> None:
            # 同步步骤等待 loop 回调；直接在 loop 内执行时会超时，线程池执行时能立即交接。
            resumed = threading.Event()
            loop.call_soon_threadsafe(resumed.set)
            self.assertTrue(resumed.wait(timeout=2), f"{phase} 阶段阻塞了事件循环。")
            phases.append(phase)
            worker_threads.append(threading.get_ident())

        def upload(**kwargs):
            observe_loop_progress("upload")
            return self.record

        def audit(**kwargs):
            observe_loop_progress("audit")

        self.runtime.file_upload_service.upload_authorized_content.side_effect = upload
        self.runtime.audit_service.record.side_effect = audit

        response = await upload_file_content(
            self.record.id,
            self._request(b"%PDF", b"data"),
            self.runtime,
            self.user,
            "trace_upload",
        )

        self.assertEqual(phases, ["upload", "audit"])
        self.assertNotEqual(worker_threads[0], loop_thread)
        self.assertEqual(worker_threads[0], worker_threads[1])
        # C新增的删除预留和复核版本属于内部持久化事实，不进入现有公开文件响应。
        self.assertEqual(
            response.file.model_dump(),
            self.record.model_dump(exclude={"deletion_claim", "review_source_revision"}),
        )
        self.runtime.file_upload_service.upload_authorized_content.assert_called_once_with(
            file_id=self.record.id,
            user=self.user,
            content=b"%PDFdata",
            content_type="application/pdf",
        )
        self.runtime.audit_service.record.assert_called_once_with(
            actor=ActorContext(actor_id=self.user.id, actor_role=self.user.role, source="jwt"),
            action="file.upload_content",
            target_type="document_file",
            target_id=self.record.id,
            trace_id="trace_upload",
        )

    async def test_concurrent_uploads_serialize_without_blocking_event_loop(self) -> None:
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()
        first_upload_started = asyncio.Event()
        first_audit_started = asyncio.Event()
        second_reached_worker = asyncio.Event()
        release_upload = threading.Event()
        release_audit = threading.Event()
        process_lock = threading.Lock()
        phases: list[str] = []

        class ObservedLock:
            def __enter__(observed):
                self.assertNotEqual(threading.get_ident(), loop_thread, "上传锁不能在事件循环线程获取。")
                if not process_lock.acquire(blocking=False):
                    # 确认第二个工作线程已经排队，避免靠短暂等待推测它是否执行。
                    loop.call_soon_threadsafe(second_reached_worker.set)
                    process_lock.acquire()

            def __exit__(observed, *exc):
                process_lock.release()

        def upload(**kwargs):
            name = kwargs["content"].decode("ascii")
            phases.append(f"upload_{name}")
            if name == "first":
                loop.call_soon_threadsafe(first_upload_started.set)
                self.assertTrue(release_upload.wait(timeout=5), "首个上传没有被释放。")
            else:
                loop.call_soon_threadsafe(second_reached_worker.set)
            return self.record

        def audit(**kwargs):
            name = kwargs["trace_id"]
            phases.append(f"audit_{name}")
            if name == "first":
                loop.call_soon_threadsafe(first_audit_started.set)
                self.assertTrue(release_audit.wait(timeout=5), "首个审计没有被释放。")

        self.runtime.file_upload_service.upload_authorized_content.side_effect = upload
        self.runtime.audit_service.record.side_effect = audit

        with patch("app.domains.files.router._upload_content_lock", ObservedLock(), create=True):
            first = asyncio.create_task(
                upload_file_content(self.record.id, self._request(b"first"), self.runtime, self.user, "first")
            )
            second = None
            try:
                await asyncio.wait_for(first_upload_started.wait(), timeout=2)
                second = asyncio.create_task(
                    upload_file_content(self.record.id, self._request(b"second"), self.runtime, self.user, "second")
                )
                await asyncio.wait_for(second_reached_worker.wait(), timeout=2)
                self.assertEqual(phases, ["upload_first"], "并发请求的同步上传段发生了重叠。")
                release_upload.set()
                await asyncio.wait_for(first_audit_started.wait(), timeout=2)
                self.assertEqual(phases, ["upload_first", "audit_first"])
                release_audit.set()
                responses = await asyncio.wait_for(asyncio.gather(first, second), timeout=2)
            finally:
                release_upload.set()
                release_audit.set()
                await asyncio.gather(*(task for task in (first, second) if task is not None), return_exceptions=True)

        self.assertEqual(phases, ["upload_first", "audit_first", "upload_second", "audit_second"])
        self.assertEqual([response.file.id for response in responses], [self.record.id, self.record.id])

    async def test_upload_errors_propagate_without_audit(self) -> None:
        for error in (
            ApiError(409, "conflict", "文件当前状态不允许重复上传。"),
            OSError("测试对象写入失败。"),
        ):
            with self.subTest(error_type=type(error).__name__):
                self.runtime.file_upload_service.upload_authorized_content.side_effect = error
                with self.assertRaises(type(error)) as caught:
                    await upload_file_content(
                        self.record.id,
                        self._request(b"%PDFdata"),
                        self.runtime,
                        self.user,
                        "trace_upload",
                    )
                self.assertIs(caught.exception, error)
                self.runtime.audit_service.record.assert_not_called()
                self.runtime.file_upload_service.upload_authorized_content.side_effect = None
                response = await asyncio.wait_for(
                    upload_file_content(
                        self.record.id,
                        self._request(b"%PDFdata"),
                        self.runtime,
                        self.user,
                        "trace_upload",
                    ),
                    timeout=2,
                )
                self.assertEqual(response.file.id, self.record.id)
                self.runtime.audit_service.record.assert_called_once()
                self.runtime.audit_service.record.reset_mock()

    async def test_audit_error_remains_visible_after_upload(self) -> None:
        error = OSError("测试审计写入失败。")
        calls = Mock()
        calls.attach_mock(self.runtime.file_upload_service.upload_authorized_content, "upload")
        calls.attach_mock(self.runtime.audit_service.record, "audit")
        self.runtime.audit_service.record.side_effect = error

        with self.assertRaises(OSError) as caught:
            await upload_file_content(
                self.record.id,
                self._request(b"%PDFdata"),
                self.runtime,
                self.user,
                "trace_upload",
            )

        self.assertIs(caught.exception, error)
        self.assertEqual([call[0] for call in calls.mock_calls], ["upload", "audit"])
        self.runtime.audit_service.record.side_effect = None
        response = await asyncio.wait_for(
            upload_file_content(
                self.record.id,
                self._request(b"%PDFdata"),
                self.runtime,
                self.user,
                "trace_upload",
            ),
            timeout=2,
        )
        self.assertEqual(response.file.id, self.record.id)

    async def test_oversized_body_rejects_before_upload_and_audit(self) -> None:
        with self.assertRaises(ApiError) as caught:
            await upload_file_content(
                self.record.id,
                self._request(b"%PDF", b"large"),
                self.runtime,
                self.user,
                "trace_upload",
            )

        self.assertEqual(caught.exception.status_code, 413)
        self.assertEqual(caught.exception.code, "file_too_large")
        self.runtime.file_upload_service.upload_authorized_content.assert_not_called()
        self.runtime.audit_service.record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
