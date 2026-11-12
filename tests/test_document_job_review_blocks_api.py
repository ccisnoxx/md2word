"""复核内容接口的真实装配回归：/review/blocks 与 /review/blocks/{block_id} 经正式用例组装可读。

单元测试 test_document_job_review_hints 以 Mock 替代 service，覆盖不到用例装配；这里走完整 runtime。
"""

import tempfile
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient

from app.main import create_app
from tests import test_fastapi_jobs_backend as fixtures


class DocumentJobReviewBlocksApiTests(TestCase):
    def test_review_blocks_list_and_detail_use_real_use_case_wiring(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = fixtures.build_test_runtime(
                Path(directory), auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=fixtures.build_auth_users_json(), document_jobs_worker_backend="eager",
            )
            with TestClient(create_app(runtime)) as client:
                headers = fixtures.build_auth_header(client)
                source = fixtures.FastAPIJobsBackendTests._upload_source_pdf(self, client, headers)
                job_id = client.post("/api/v1/document-jobs", headers=headers,
                                     json={"source_file_id": source["id"]}).json()["job_id"]
                job = client.get(f"/api/v1/document-jobs/{job_id}", headers=headers).json()
                self.assertEqual(job["status"], "succeeded", (job["error_code"], job["error_message"]))

                listed = client.get(f"/api/v1/document-jobs/{job_id}/review/blocks", headers=headers)
                self.assertEqual(listed.status_code, 200, listed.text)
                body = listed.json()
                self.assertEqual(body["source"]["generation"], job["retry_count"])
                self.assertTrue(body["items"])

                block = body["items"][0]
                detail = client.get(
                    f"/api/v1/document-jobs/{job_id}/review/blocks/{block['block_id']}",
                    headers=headers, params={"snapshot_id": body["content_snapshot"]["snapshot_id"]},
                )
                self.assertEqual(detail.status_code, 200, detail.text)
                self.assertEqual(detail.json()["block"]["block_id"], block["block_id"])
