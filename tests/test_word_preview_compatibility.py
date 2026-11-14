"""锁内预览领取、部分产物登记和完整预览下载期限的兼容回归。"""

from datetime import datetime, timedelta
from io import BytesIO
import multiprocessing
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from app.domains.document_jobs.preview_state import PreviewClaimRequest
from app.domains.resources.models import utc_now
from app.services.preview.models import PreviewPolicy, sha256
from tests.document_job_list_query_v2_publication_fixtures import V2PublicationFixture
from tests.test_document_job_result_persistence import _adapters, _candidate, _job


def _claim_in_process(kind, directory, job_id, request_data, ready, start, output):
    repository = _adapters(kind, directory).document_job_repository
    request = PreviewClaimRequest.model_validate(request_data)
    ready.put(True)
    if not start.wait(15):
        raise RuntimeError("等待预览领取竞争开始超时。")
    claim = repository.claim_document_job_preview(job_id, request=request)
    output.put(claim.disposition)


class WordPreviewClaimCompatibilityTests(TestCase):
    def test_file_and_sqlite_allow_only_one_preview_claim_across_processes(self):
        context = multiprocessing.get_context("spawn")
        for kind in ("file", "sqlite"):
            with self.subTest(kind=kind), TemporaryDirectory() as directory:
                repository = _adapters(kind, directory).document_job_repository
                policy = PreviewPolicy(backend="sandboxed")
                job = _job().model_copy(update={"request_snapshot": {
                    "word_preview": policy.model_dump(mode="json"),
                }})
                repository.create_document_job(job)
                candidate = _candidate()
                prepared = repository.prepare_document_job_result(
                    job.id, expected_retry_count=job.retry_count,
                    expected_document_ir_file_id=job.document_ir_file_id, candidate=candidate,
                )
                self.assertEqual(prepared.prepared_result.file.id, candidate.id)
                request = PreviewClaimRequest(
                    generation=prepared.retry_count, result_file_id=candidate.id,
                    docx_sha256=candidate.checksum_sha256, policy=policy, request_key="initial",
                    request_fingerprint=sha256(b"initial"), requested_by=job.created_by,
                    reason_sha256=sha256(b"initial"), resume=True,
                )
                ready, output, start = context.Queue(), context.Queue(), context.Event()
                processes = [
                    context.Process(target=_claim_in_process, args=(
                        kind, directory, job.id, request.model_dump(mode="json"), ready, start, output,
                    ))
                    for _ in range(2)
                ]
                try:
                    for process in processes:
                        process.start()
                    for _ in processes:
                        self.assertTrue(ready.get(timeout=15))
                    start.set()
                    self.assertCountEqual([output.get(timeout=15) for _ in processes], ["claimed", "busy"])
                    for process in processes:
                        process.join(15)
                        self.assertEqual(process.exitcode, 0)
                    reopened = _adapters(kind, directory).document_job_repository
                    state = reopened.get_document_job(job.id).word_preview_state
                    self.assertEqual(state.current_request_key, request.request_key)
                    self.assertEqual(set(state.runs_by_request_key), {request.request_key})
                    self.assertEqual((state.current_run.status, state.current_run.attempt_count), ("running", 1))
                finally:
                    for process in processes:
                        if process.is_alive():
                            process.terminate()
                            process.join(5)
                    ready.close()
                    output.close()


class WordPreviewArtifactCompatibilityTests(V2PublicationFixture, TestCase):
    def test_partial_preview_registration_preserves_docx_and_hides_preview_pdf(self):
        with self.runtime(pages=True) as (runtime, execution, _, job, _, client, headers):
            job = self.install_publication_resources(runtime, execution, job)
            file_service = runtime.file_upload_service
            register_content = file_service.register_generated_content
            files = runtime.document_file_repository
            selected_results = []

            def fail_page_registration(**kwargs):
                if kwargs["file_type"] == "word_preview_page":
                    receipt = runtime.document_job_repository.get_document_job(job.id).prepared_result
                    docx = files.get_document_file(receipt.file.id)
                    selected_results.append((receipt, file_service.read_file_content(docx)))
                    raise OSError("测试注入页图登记失败。")
                return register_content(**kwargs)

            with patch.object(file_service, "register_generated_content", side_effect=fail_page_registration):
                failed = execution.execute_job(job.id)

            self.assertEqual((failed.status, failed.failed_stage, failed.error_code), ("failed", "uploading", "oss_failed"))
            self.assertEqual(len(selected_results), 1)
            receipt, content = selected_results[0]
            self.assertEqual(failed.prepared_result, receipt)
            docx = files.get_document_file(receipt.file.id)
            self.assertEqual(docx.status, "uploaded")
            self.assertEqual(file_service.read_file_content(docx), content)
            self.assertEqual(sha256(content), receipt.file.checksum_sha256)
            run = failed.word_preview_state.current_run
            self.assertEqual(run.artifact_stage, "registering")
            self.assertIsNone(run.confirmed_attempt)
            self.assertIsNone(run.manifest_file_id)

            partial_pdf, = self._files(runtime, job.id, "word_preview_pdf")
            self.assertEqual(partial_pdf.status, "uploaded")
            self.assertEqual(partial_pdf.metadata["source_result_file_id"], receipt.file.id)
            self.assertEqual(partial_pdf.metadata["attempt"], run.attempt_count)
            self.assertEqual(sha256(file_service.read_file_content(partial_pdf)), partial_pdf.checksum_sha256)
            listed = client.get(f"/api/v1/document-jobs/{job.id}/files", headers=headers)
            self.assertEqual(listed.status_code, 200, listed.text)
            self.assertNotIn(partial_pdf.id, {item["id"] for item in listed.json()["files"]})
            denied = client.get(f"/api/v1/document-jobs/{job.id}/download-url",
                                params={"file_id": partial_pdf.id}, headers=headers)
            self.assertEqual(denied.status_code, 409, denied.text)
            self.assertEqual(denied.json()["error"]["reason_code"], "file_not_current")

    def test_s3_preview_pdf_download_ttl_is_bounded_by_manifest_and_page(self):
        for limiting_type, ttl in (("word_preview_manifest", 45), ("word_preview_page", 75)):
            with self.subTest(limiting_type=limiting_type), self.runtime(pages=True) as (
                runtime, execution, _, job, _, client, headers,
            ):
                job = self.install_publication_resources(runtime, execution, job)
                result = execution.execute_job(job.id)
                self.assertEqual(result.status, "succeeded", result.error_message)
                self.assertEqual(result.word_preview_state.current_run.status, "succeeded")

                files = runtime.document_file_repository
                service = runtime.file_upload_service
                pdf, = self._files(runtime, job.id, "word_preview_pdf")
                limiting_file, = self._files(runtime, job.id, limiting_type)
                pdf_content = service.read_file_content(pdf)
                now = utc_now()
                deadline = now + timedelta(seconds=ttl)
                files.update_document_file(limiting_file.id, expires_at=deadline)
                pdf = files.update_document_file(pdf.id, storage_provider="s3", bucket="test-preview")
                s3 = Mock()
                s3.get_object.side_effect = lambda **kwargs: {"Body": BytesIO(pdf_content)}
                s3.generate_presigned_url.return_value = "https://s3.example.invalid/preview.pdf"
                with (
                    patch.object(service, "_s3_client", return_value=s3),
                    patch("app.domains.document_jobs.preview_evidence.utc_now", return_value=now),
                    patch("app.domains.document_jobs.use_cases.downloads.utc_now", return_value=now),
                ):
                    response = client.get(f"/api/v1/document-jobs/{job.id}/download-url",
                                          params={"file_id": pdf.id}, headers=headers)

                self.assertEqual(response.status_code, 200, response.text)
                s3.get_object.assert_any_call(Bucket=pdf.bucket, Key=pdf.object_key)
                s3.generate_presigned_url.assert_called_once_with(
                    "get_object", Params={"Bucket": pdf.bucket, "Key": pdf.object_key}, ExpiresIn=ttl,
                )
                self.assertEqual(response.json()["download_url"], s3.generate_presigned_url.return_value)
                self.assertEqual(datetime.fromisoformat(response.json()["expires_at"]), deadline)
