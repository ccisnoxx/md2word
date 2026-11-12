from __future__ import annotations

import io
import logging
import os
import tempfile
import traceback
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient
from requests.adapters import HTTPAdapter
from urllib3.exceptions import ReadTimeoutError

from app.clients.mineru_client import MinerUClient, MinerUError
from app.main import create_app
from tests import test_fastapi_jobs_backend as fixtures


SECRET = "synthetic-download-secret"
START_URL = f"https://mineru.net/result.zip?signature={SECRET}"
BODY = bytes(range(256)) * 8193


class ResponseBody(io.BytesIO):
    """提供 Requests 所需的流和释放接口，保留关闭证据。"""

    def __init__(self, content: bytes, *, interrupted: bool = False) -> None:
        super().__init__(content)
        self.interrupted = interrupted

    def stream(self, chunk_size, decode_content=True):
        while chunk := self.read(chunk_size):
            yield chunk
            if self.interrupted:
                raise ReadTimeoutError(None, START_URL, SECRET)

    def release_conn(self):
        self.close()


class DownloadTransport:
    """只替换网络适配器，真实 Session 负责准备请求、跳转与响应消费。"""

    def __init__(self, steps):
        self.steps = steps
        self.requests = []
        self.options = []
        self.responses = []
        self.closed_sessions = []

    def send(self, adapter, request, **kwargs):
        self.requests.append(request)
        self.options.append(kwargs)
        step = self.steps[min(len(self.requests) - 1, len(self.steps) - 1)]
        if isinstance(step, Exception):
            raise step
        status, location, body, interrupted = step
        response = requests.Response()
        response.status_code = status
        response.url = request.url
        response.request = request
        response.raw = ResponseBody(body, interrupted=interrupted)
        if location is not None:
            response.headers["Location"] = location
        self.responses.append(response)
        return response

    @contextmanager
    def installed(self):
        original_close = requests.Session.close

        def close(session):
            self.closed_sessions.append(session)
            original_close(session)

        with patch.object(HTTPAdapter, "send", autospec=True, side_effect=self.send), patch.object(
            requests.Session, "close", autospec=True, side_effect=close,
        ):
            yield self


class MinerUDownloadBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        # 防止测试读取开发机 netrc；代理和 CA 合并仍走 Requests 的真实入口。
        self.environment = patch.dict(os.environ, {"NETRC": str(self.root / "absent.netrc")}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.log_text = io.StringIO()
        handler = logging.StreamHandler(self.log_text)
        logger = logging.getLogger("system")
        self.addCleanup(logger.setLevel, logger.level)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)

    def make_client(self, allowed_hosts=("mineru.net", "cdn-mineru.openxlab.org.cn")):
        client = MinerUClient(
            api_token=f"api-{SECRET}", user_token=f"uid-{SECRET}", result_host_allowlist=allowed_hosts,
        )
        self.addCleanup(client.session.close)
        return client

    def assert_safe_failure(self, client, url, output):
        try:
            client.download_result_zip(url, output)
        except MinerUError as error:
            self.assertNotIn(SECRET, str(error))
            self.assertNotIn(SECRET, traceback.format_exc())
            self.assertNotIn(SECRET, self.log_text.getvalue())
            return error
        self.fail("下载应以安全错误拒绝")

    def assert_released(self, transport):
        self.assertEqual(len(transport.closed_sessions), 1)
        self.assertTrue(all(response.raw.closed for response in transport.responses))

    def test_initial_url_rejected_before_transport_and_output(self):
        invalid_urls = [
            "", "/result.zip", "https:///result.zip", "http://mineru.net/result.zip",
            "https://evil.test/result.zip", "https://mineru.net.evil.test/result.zip",
            "https://evilmineru.net/result.zip", f"https://{SECRET}@mineru.net/result.zip",
            f"https://user:{SECRET}@mineru.net/result.zip", "https://@mineru.net/result.zip",
            f"https://mineru.net:{SECRET}/result.zip", "https://mineru.net:65536/result.zip",
            f"https://[{SECRET}/result.zip", "https://*.mineru.net/result.zip",
        ]
        client = self.make_client()
        for url, allowed_client in [(url, client) for url in invalid_urls] + [(START_URL, self.make_client(()))]:
            for existing in (False, True):
                with self.subTest(url=url, existing=existing):
                    output = self.root / "result.zip"
                    if existing:
                        output.write_bytes(b"sentinel")
                    transport = DownloadTransport([(200, None, BODY, False)])
                    with transport.installed():
                        self.assert_safe_failure(allowed_client, url, output)
                    self.assertEqual(transport.requests, [])
                    if existing:
                        self.assertEqual(output.read_bytes(), b"sentinel")
                        output.unlink()
                    else:
                        self.assertFalse(output.exists())

    def test_allowed_urls_preserve_signed_query_and_bytes(self):
        for host in ("mineru.net", "a.mineru.net", "MiNeRu.NeT", "mineru.net:8443"):
            with self.subTest(host=host):
                client = self.make_client()
                output = self.root / "nested" / "result.zip"
                transport = DownloadTransport([(200, None, BODY, False)])
                with transport.installed():
                    result = client.download_result_zip(f"https://{host}/result.zip?signature={SECRET}", output)
                self.assertEqual(result, output)
                self.assertEqual(output.read_bytes(), BODY)
                self.assertIn(f"signature={SECRET}", transport.requests[0].url)
                self.assert_released(transport)
                self.assertIn("MinerU 结果 zip 下载完成", self.log_text.getvalue())
                self.assertNotIn(SECRET, self.log_text.getvalue())

    def test_allowed_redirects_use_real_requests_resolution(self):
        for status in (301, 302, 303, 307, 308):
            for location, expected in (
                ("/next.zip", "https://mineru.net/next.zip"),
                ("next.zip", "https://mineru.net/next.zip"),
                ("//a.mineru.net/next.zip", "https://a.mineru.net/next.zip"),
                ("https://cdn-mineru.openxlab.org.cn/next.zip", "https://cdn-mineru.openxlab.org.cn/next.zip"),
            ):
                with self.subTest(status=status, location=location):
                    transport = DownloadTransport([
                        (status, location, b"redirect", False),
                        (302, f"/final.zip?signature={SECRET}", b"redirect", False),
                        (200, None, BODY, False),
                    ])
                    output = self.root / "result.zip"
                    client = self.make_client()
                    with transport.installed():
                        client.download_result_zip(START_URL, output)
                    self.assertEqual([request.url for request in transport.requests], [
                        START_URL, expected, expected.replace("next.zip", f"final.zip?signature={SECRET}"),
                    ])
                    self.assertTrue(all(request.method == "GET" for request in transport.requests))
                    self.assertEqual(output.read_bytes(), BODY)
                    self.assert_released(transport)

    def test_disallowed_redirect_never_reaches_transport_or_truncates_output(self):
        for target in (
            f"http://mineru.net/result.zip?signature={SECRET}",
            f"https://evil.test/result.zip?signature={SECRET}",
            f"https://user:{SECRET}@mineru.net/result.zip",
        ):
            for preceding_hops in (1, 2):
                for existing in (False, True):
                    with self.subTest(target=target, hops=preceding_hops, existing=existing):
                        steps = [(302, "/second.zip", b"redirect", False)] * (preceding_hops - 1)
                        transport = DownloadTransport(steps + [(302, target, b"redirect", False)])
                        output = self.root / "result.zip"
                        if existing:
                            output.write_bytes(b"sentinel")
                        client = self.make_client()
                        with transport.installed():
                            self.assert_safe_failure(client, START_URL, output)
                        self.assertEqual(len(transport.requests), preceding_hops)
                        self.assertTrue(all(request.url.startswith("https://mineru.net/") for request in transport.requests))
                        self.assert_released(transport)
                        if existing:
                            self.assertEqual(output.read_bytes(), b"sentinel")
                            output.unlink()
                        else:
                            self.assertFalse(output.exists())

    def test_failure_paths_are_bounded_safe_and_release_resources(self):
        cases = {
            "redirect_loop": ([(302, START_URL, b"redirect", False)], 31, False),
            "missing_location": ([(302, None, b"redirect", False)], 1, False),
            "not_found": ([(404, None, SECRET.encode(), False)], 1, False),
            "timeout": ([requests.Timeout(START_URL)], 1, False),
            "connection": ([requests.ConnectionError(START_URL)], 1, False),
            "stream_interrupted": ([(200, None, b"partial", True)], 1, True),
            "redirect_stream_interrupted": ([(302, "/next.zip", b"partial", True)], 1, False),
            "malformed_location": ([(302, f"https://[{SECRET}", b"redirect", False)], 1, False),
        }
        for name, (steps, request_count, partial) in cases.items():
            with self.subTest(case=name):
                transport = DownloadTransport(steps)
                output = self.root / f"{name}.zip"
                if not partial:
                    output.write_bytes(b"sentinel")
                client = self.make_client()
                with transport.installed():
                    self.assert_safe_failure(client, START_URL, output)
                self.assertEqual(len(transport.requests), request_count)
                self.assert_released(transport)
                self.assertEqual(output.read_bytes(), b"partial" if partial else b"sentinel")

    def test_download_isolates_api_credentials_and_preserves_environment(self):
        client = self.make_client()
        client.session.cookies.set("api_cookie", SECRET, domain="mineru.net")
        client.session.auth = ("api_user", SECRET)
        transport = DownloadTransport([
            (302, f"https://cdn-mineru.openxlab.org.cn/result.zip?signature={SECRET}", b"redirect", False),
            (200, None, BODY, False),
        ])
        with patch.dict(os.environ, {
            "HTTPS_PROXY": "http://proxy.test:8080", "REQUESTS_CA_BUNDLE": "/synthetic/ca.pem",
        }), transport.installed(), self.assertLogs("system", level="INFO") as logs:
            client.download_result_zip(START_URL, self.root / "result.zip")
        for request, options in zip(transport.requests, transport.options):
            for name in ("Authorization", "token", "Cookie"):
                self.assertNotIn(name, request.headers)
            self.assertEqual(options["verify"], "/synthetic/ca.pem")
            self.assertEqual(options["proxies"]["https"], "http://proxy.test:8080")
            self.assertEqual(options["timeout"], 300)
            self.assertTrue(options["stream"])
        self.assertTrue(transport.closed_sessions[0].trust_env)
        self.assertNotIn(SECRET, "\n".join(logs.output))
        self.assert_released(transport)

    def make_runtime(self, root, *, callback=False, allowed_hosts="mineru.net,cdn-mineru.openxlab.org.cn"):
        return fixtures.build_test_runtime(
            root, mineru_api_token=f"api-{SECRET}", mineru_uid="synthetic-uid",
            mineru_result_host_allowlist=allowed_hosts, jobs_artifact_storage_backend="local_object",
            auth_jwt_secret_key="synthetic-auth-key-for-boundary-tests",
            auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            mineru_callback_url="https://md2word.example/api/v1/mineru-callbacks/result" if callback else "",
        )

    def test_production_factories_use_custom_allowlist_and_existing_resolver(self):
        runtime = self.make_runtime(self.root, allowed_hosts="custom.test")
        runtime.mineru_config_service.update_credentials(
            api_token="synthetic-rotated-api", uid="synthetic-rotated-uid", updated_by="boundary-test",
        )
        for factory in (runtime.document_job_execution_service.mineru.build_mineru_client,):
            with self.subTest(factory=factory.__qualname__):
                client = factory()
                self.addCleanup(client.session.close)
                self.assertEqual(client.api_token, "synthetic-rotated-api")
                self.assertEqual(client.session.headers["Authorization"], "Bearer synthetic-rotated-api")
                self.assertEqual(client.session.headers["token"], "synthetic-rotated-uid")
                self.assertEqual(client.model_version, runtime.settings.mineru_model_version)
                transport = DownloadTransport([(200, None, BODY, False)])
                with transport.installed():
                    client.download_result_zip("https://custom.test/result.zip", self.root / "custom.zip")
                    self.assert_safe_failure(client, START_URL, self.root / "denied.zip")
                self.assertEqual([request.url for request in transport.requests], ["https://custom.test/result.zip"])
                self.assertFalse((self.root / "denied.zip").exists())

    def create_document_job(self, api):
        headers = fixtures.build_auth_header(api)
        content = fixtures.make_pdf_bytes()
        authorization = api.post("/api/v1/files/upload-url", headers=headers, json={
            "filename": "source.pdf", "mime_type": "application/pdf", "size_bytes": len(content),
        })
        self.assertEqual(authorization.status_code, 201, authorization.text)
        uploaded = api.put(authorization.json()["upload_url"].replace("http://testserver", ""),
                           headers={**headers, "Content-Type": "application/pdf"}, content=content)
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        created = api.post("/api/v1/document-jobs", headers=headers,
                           json={"source_file_id": uploaded.json()["file"]["id"]})
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()["job_id"]

    def assert_document_download_failed(self, runtime, job_id):
        job = runtime.document_job_repository.get_document_job(job_id)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.failed_stage, "parsing")
        self.assertEqual(job.error_code, "mineru_failed")
        self.assertIsNone(job.mineru_raw_result_file_id)
        self.assertNotIn(SECRET, job.error_message)
        files = runtime.document_file_repository.list_document_files()
        self.assertEqual([item for item in files if item.job_id == job_id and item.file_type != "source_pdf"], [])

    def test_formal_polling_rejects_initial_and_redirect_targets(self):
        for redirect in (False, True):
            with self.subTest(redirect=redirect):
                runtime = self.make_runtime(self.root / str(redirect))
                execution = runtime.document_job_execution_service
                client = execution.mineru.build_mineru_client()
                self.addCleanup(client.session.close)
                execution.mineru.mineru_client_factory = lambda: client
                url = START_URL if redirect else f"https://evil.test/result.zip?signature={SECRET}"
                transport = DownloadTransport([(302, f"https://evil.test/result.zip?signature={SECRET}", b"redirect", False)])
                with patch.object(client, "upload_files_batch", return_value=("batch-boundary", [])), patch.object(
                    client, "query_batch_extract_results", return_value={
                        "batch_id": "batch-boundary", "extract_result": [{"state": "done", "full_zip_url": url}],
                    },
                ), transport.installed(), TestClient(create_app(runtime)) as api:
                    job_id = self.create_document_job(api)
                self.assert_document_download_failed(runtime, job_id)
                self.assertEqual([request.url for request in transport.requests], [START_URL] if redirect else [])

    def test_formal_callback_checks_before_enqueue_and_again_in_worker(self):
        for redirect in (False, True):
            with self.subTest(redirect=redirect):
                runtime = self.make_runtime(self.root / str(redirect), callback=True)
                execution = runtime.document_job_execution_service
                client = execution.mineru.build_mineru_client()
                self.addCleanup(client.session.close)
                execution.mineru.mineru_client_factory = lambda: client
                transport = DownloadTransport([(302, f"https://evil.test/result.zip?signature={SECRET}", b"redirect", False)])
                with patch.object(client, "upload_files_batch", return_value=("batch-boundary", [])), patch.object(
                    client, "query_batch_extract_results", return_value={
                        "batch_id": "batch-boundary", "extract_result": [{"state": "running"}],
                    },
                ), transport.installed(), TestClient(create_app(runtime)) as api:
                    job_id = self.create_document_job(api)
                    waiting = runtime.document_job_repository.get_document_job(job_id)
                    payload, content = fixtures.build_callback_payload(
                        batch_id=waiting.mineru_batch_id, data_id=job_id, state="done",
                        full_zip_url=START_URL if redirect else f"https://evil.test/result.zip?signature={SECRET}",
                    )
                    payload["checksum"] = fixtures.build_callback_checksum(
                        uid="synthetic-uid", seed=waiting.mineru_callback_seed, content=content,
                    )
                    result = api.post("/api/v1/mineru-callbacks/result", json=payload)
                    queued = runtime.document_job_callback_message_store.list_replayable_callback_messages(job_id)
                    if redirect:
                        self.assertEqual(result.status_code, 200, result.text)
                        self.assertEqual(len(queued), 1)
                        self.assertEqual(transport.requests, [])
                        execution.execute_job(job_id, trace_id="boundary-callback")
                        self.assert_document_download_failed(runtime, job_id)
                    else:
                        self.assertEqual(result.status_code, 400, result.text)
                        self.assertNotIn(SECRET, result.text)
                        self.assertEqual(queued, [])
                        self.assertEqual(runtime.document_job_repository.get_document_job(job_id).stage, "parsing")
                self.assertEqual([request.url for request in transport.requests], [START_URL] if redirect else [])



if __name__ == "__main__":
    unittest.main()
