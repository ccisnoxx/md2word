"""异常队列先分类分页，发布只做状态准入，其他观察语义保持。"""

from datetime import timedelta
from unittest import TestCase
from unittest.mock import patch

from app.domains.document_jobs.base_quality import BaseQualityContribution, DegradedPageSummary
from app.domains.document_jobs.incidents import (
    DOCUMENT_JOB_INCIDENT_FAILURE_TYPES,
    DOCUMENT_JOB_INCIDENT_SORTS,
    DocumentJobIncidentService,
)
from app.domains.document_jobs.schemas import DocumentJobIncidentListResponse
from app.domains.document_jobs.publication_evidence import prepare_publication_evidence
from tests import test_document_job_list_query_v2_service as fixtures
from tests import test_fastapi_jobs_backend as support
from tests.document_job_list_query_v2_publication_fixtures import V2PublicationFixture


def full_scan(incidents, **query):
    """冻结改前的全量动作流程；不随提交后的 HEAD 切换成候选实现。"""
    items = [incidents._build_item(job, user=query["user"], now=fixtures.NOW)
        for job in incidents.document_job_service.list_visible_jobs(user=query["user"])]
    items = [item for item in items if item.is_incident
        and incidents._matches_status(item, query["status_filter"])
        and incidents._matches_stage(item, query["stage_filter"])
        and incidents._matches_failure_type(item, query["failure_type"])
        and incidents._matches_retryable(item, query["retryable"])
        and incidents._matches_retry_count(item, query["retry_count"])
        and incidents._matches_stalled_minutes(item, query["stalled_minutes"])
        and incidents._matches_query(item, incidents._normalize_optional_text(query["q"]))]
    items.sort(key=lambda item: incidents._sort_key(item, query["sort"]),
        reverse=incidents._sort_reverse(query["sort"]))
    start = (query["page"] - 1) * query["page_size"]
    return DocumentJobIncidentListResponse(items=items[start:start + query["page_size"]],
        total=len(items), summary=incidents._build_summary(items),
        page=query["page"], page_size=query["page_size"])


def query_values(user=fixtures.ADMIN, **changes):
    return {"user": user, "page": 1, "page_size": 3, "status_filter": None,
        "stage_filter": None, "failure_type": None, "retryable": None, "retry_count": None,
        "stalled_minutes": None, "q": None, "sort": "priority", **changes}


class DocumentJobIncidentMetadataTests(TestCase):
    environment = fixtures.DocumentJobListV2ServiceTests.environment
    verified = fixtures.DocumentJobListV2ServiceTests.verified

    def populate(self, jobs, files, service):
        for name, error, stage, retries in (
            ("translation", "translation_failed", "translating", 0),
            ("conversion", "render_failed", "rendering", 1),
            ("timeout", "document_job_timeout", "parsing", 2),
            ("worker", "dispatch_failed", "uploaded", 3),
            ("invalid", "document_job_invalid_input", "uploaded", 0),
            ("missing", "file_missing", "uploading", 0),
        ):
            jobs.create_document_job(fixtures.make_job(name, status="failed", stage="failed",
                mode="en2zh_pdf_to_word", failed_stage=stage, error_code=error,
                error_message=f"测试 {name}", retry_count=retries))
        jobs.create_document_job(fixtures.make_job("stalled", status="running", stage="parsing",
            timeout_at=fixtures.NOW - timedelta(minutes=30)))
        jobs.create_document_job(fixtures.make_job("healthy", status="queued", stage="uploaded"))
        jobs.create_document_job(fixtures.make_job("foreign-owner", status="failed", stage="failed").model_copy(
            update={"created_by": "someone-else"}))
        jobs.create_document_job(fixtures.make_job("foreign-tenant", status="failed", stage="failed").model_copy(
            update={"tenant_id": "other"}))
        jobs.create_document_job(fixtures.make_job("archived", status="failed", stage="failed", archived_at=fixtures.NOW))
        jobs.create_document_job(fixtures.make_job("deleted", status="failed", stage="failed", deleted_at=fixtures.NOW))
        self.verified(jobs, files, job_id="blocked", review="blocked")
        stale, file = self.verified(jobs, files, job_id="stale-review", review="blocked")
        files.update_document_file(file.id, checksum_sha256="sha256:" + "2" * 64)
        pending, _ = self.verified(jobs, files, job_id="not-completed", review="blocked")
        jobs.update_document_job(pending.id, status="running", stage="uploading")
        self.verified(jobs, files, job_id="degraded", review="unreviewed", quality_summary={
            "checks_v1": {"document_base": BaseQualityContribution(generation=0, degraded_pages=[
                DegradedPageSummary(page_number=2, trigger="validation", reason_codes=["invalid_table_html"]),
            ]).model_dump(mode="json")}})
        self.verified(jobs, files, job_id="old-degraded", review="unreviewed", quality_summary={
            "checks_v1": {"document_base": BaseQualityContribution(generation=1, degraded_pages=[
                DegradedPageSummary(page_number=3, trigger="render", reason_codes=["render_failed"]),
            ]).model_dump(mode="json")}})

    def test_all_filters_sorts_summaries_roles_and_empty_pages_match_full_scan(self):
        cases = [{}, {"page": 2}, {"page": 100}, {"page_size": 100}]
        cases += [{"status_filter": value} for value in ("pending", "queued", "running", "succeeded", "failed", "canceled")]
        cases += [{"stage_filter": value} for value in ("failed", "uploaded", "translating", "parsing", "completed")]
        cases += [{"failure_type": value} for value in sorted(DOCUMENT_JOB_INCIDENT_FAILURE_TYPES)]
        cases += [{"retryable": value} for value in (True, False)]
        cases += [{"retry_count": value} for value in ("0", "1_2", "3_plus")]
        cases += [{"stalled_minutes": value} for value in (10, 60)]
        cases += [{"q": value} for value in ("  ", "translation", "第 2 页", "次数已达上限", "not-found")]
        cases += [{"sort": value, "page": page} for value in sorted(DOCUMENT_JOB_INCIDENT_SORTS) for page in (1, 2)]
        for backend in ("file", "sqlite"):
            with self.subTest(backend=backend), self.environment(backend) as (jobs, files, service), patch(
                "app.domains.document_jobs.service.utc_now", return_value=fixtures.NOW,
            ), patch("app.domains.document_jobs.incidents.utc_now", return_value=fixtures.NOW):
                self.populate(jobs, files, service)
                incidents = DocumentJobIncidentService(service)
                for user in (fixtures.ADMIN, fixtures.USER):
                    for changes in cases:
                        with self.subTest(role=user.role, changes=changes):
                            query = query_values(user, **changes)
                            expected = full_scan(incidents, **query)
                            with patch.object(service, "build_job_read_view", wraps=service.build_job_read_view) as build:
                                actual = incidents.list_incidents(**query)
                            self.assertEqual(actual.model_dump(), expected.model_dump())
                            self.assertEqual(build.call_count, len(actual.items))
                    listed = incidents.list_incidents(**query_values(user, page_size=100))
                    ids = {item.job.id for item in listed.items}
                    self.assertTrue({"blocked", "degraded", "stalled", "translation"} <= ids)
                    self.assertFalse({"stale-review", "not-completed", "old-degraded", "healthy", "archived", "deleted", "foreign-tenant"} & ids)
                    self.assertEqual("foreign-owner" in ids, user.role == "admin")
                    by_id = {item.job.id: item for item in listed.items}
                    self.assertTrue(by_id["translation"].retryable)
                    self.assertIn("次数已达上限", by_id["worker"].retry_disabled_reason)
                    self.assertIn("不可重试", by_id["invalid"].retry_disabled_reason)
                    self.assertEqual(by_id["degraded"].failure_type, "page_degraded")

    def test_expiry_before_classification_matches_full_scan(self):
        with self.environment("sqlite") as (jobs, files, service), patch(
            "app.domains.document_jobs.service.utc_now", return_value=fixtures.NOW,
        ) as clock, patch("app.domains.document_jobs.incidents.utc_now", return_value=fixtures.NOW):
            job, file = self.verified(jobs, files, review="blocked")
            incidents = DocumentJobIncidentService(service)
            visible_jobs = service.list_visible_jobs

            def visible_then_expired(**kwargs):
                clock.return_value = fixtures.NOW
                visible = visible_jobs(**kwargs)
                self.assertEqual(visible[0].review_status, "blocked")
                # 保留初始有效投影，但分类开始时主件已经过期。
                clock.return_value = file.expires_at + timedelta(seconds=1)
                return visible

            with patch.object(service, "list_visible_jobs", side_effect=visible_then_expired):
                expected = full_scan(incidents, **query_values())
                actual = incidents.list_incidents(**query_values())
            self.assertEqual(expected.total, 0)
            self.assertEqual(actual.model_dump(), expected.model_dump())

    def test_page_reuses_classification_observation_and_preserves_result_gates(self):
        for case, reason in (("expires", None), ("missing", "result_file_missing"),
            ("mismatch", "result_file_mismatch"), ("pending", "result_file_not_uploaded"),
            ("unfinished", "job_not_completed")):
            with self.subTest(case=case), self.environment("sqlite") as (jobs, files, service), patch(
                "app.domains.document_jobs.service.utc_now", return_value=fixtures.NOW,
            ) as clock, patch("app.domains.document_jobs.incidents.utc_now", return_value=fixtures.NOW):
                if case == "expires":
                    job, file = self.verified(jobs, files, review="blocked")
                elif case == "unfinished":
                    job = jobs.create_document_job(fixtures.make_job(status="running", stage="uploading",
                        result_file_id="retained", timeout_at=fixtures.NOW - timedelta(minutes=20)))
                else:
                    base = BaseQualityContribution(generation=0, degraded_pages=[
                        DegradedPageSummary(page_number=2, trigger="render", reason_codes=["render_failed"]),
                    ])
                    job = jobs.create_document_job(fixtures.make_job(status="succeeded", stage="completed",
                        result_file_id="result", quality_summary={"checks_v1": {
                            "document_base": base.model_dump(mode="json")}}))
                    if case != "missing":
                        file = fixtures.make_file().model_copy(update=(
                            {"job_id": "other"} if case == "mismatch" else {"status": "pending_upload"}))
                        files.create_document_file(file)
                incidents = DocumentJobIncidentService(service)
                query = query_values()
                expected = full_scan(incidents, **query)
                self.assertEqual(expected.total, 1)
                self.assertEqual(expected.items[0].job.available_actions["download"].disabled_reason_code, reason)
                build = service.build_job_read_view
                read_file = files.get_document_file

                def no_result_read(file_id):
                    if file_id == job.result_file_id:
                        raise AssertionError("主件门控或页内观察复用不应新增主件读取")
                    return read_file(file_id)

                def page_view(*args, **kwargs):
                    # 文件跨过到期时刻，且后续主件读取已不可用，页内仍使用分类观察。
                    clock.return_value = fixtures.NOW + timedelta(days=4)
                    with patch.object(files, "get_document_file", side_effect=no_result_read):
                        return build(*args, **kwargs)

                with patch.object(service, "build_job_read_view", side_effect=page_view), patch.object(
                    service, "_build_result_read_view", wraps=service._build_result_read_view,
                ) as result_view:
                    if case == "unfinished":
                        with patch.object(files, "get_document_file", side_effect=no_result_read):
                            actual = incidents.list_incidents(**query)
                    else:
                        actual = incidents.list_incidents(**query)
                self.assertEqual(result_view.call_count, 1)
                self.assertEqual(actual.model_dump(), expected.model_dump())


class DocumentJobIncidentPublicationTests(V2PublicationFixture, TestCase):
    def test_api_only_builds_page_actions_and_keeps_diagnostics_and_bulk_full(self):
        for backend in ("file", "sqlite"):
            with self.subTest(backend=backend), self.publication_runtime(kind=backend) as (
                runtime, job, admin, user, client, headers, provider,
            ):
                service = runtime.document_job_service
                incidents = runtime.document_job_incident_service
                # 已批准任务通过降级页进入异常列表，确保发布证据原本确实会被读取。
                base = BaseQualityContribution(generation=job.retry_count, evaluation_state="complete",
                    quality_status="warning", reason_code="base_checks_complete", degraded_pages=[
                        DegradedPageSummary(page_number=2, trigger="render", reason_codes=["render_failed"]),
                    ])
                job = job.model_copy(update={"quality_summary": {
                    **job.quality_summary, "checks_v1": {**job.quality_summary.get("checks_v1", {}),
                        "document_base": base.model_dump(mode="json")}}})
                # 同已有 publication fixture 写入历史质量槽；通用更新禁止改贡献。
                with runtime.document_job_repository._locked_job(job.id) as (connection, _):
                    runtime.document_job_repository._write_job(connection, job)
                for index in range(4):
                    runtime.document_job_repository.create_document_job(fixtures.make_job(f"failed-{index}",
                        status="failed", stage="failed").model_copy(update={"tenant_id": job.tenant_id,
                        "company_id": job.company_id, "created_by": job.created_by}))
                admin_headers = support.build_auth_header(client, "admin", "admin-pass")
                for current_user, current_headers in ((admin, admin_headers), (user, headers)):
                    query = query_values(current_user, page_size=1, failure_type="page_degraded")
                    with patch("app.domains.document_jobs.service.prepare_publication_evidence", wraps=prepare_publication_evidence) as prepare, patch.object(
                        runtime.file_upload_service, "read_file_content", wraps=runtime.file_upload_service.read_file_content) as read, patch.object(
                        service, "build_job_read_view", wraps=service.build_job_read_view) as build:
                        expected = full_scan(incidents, **query)
                    self.assertEqual(build.call_count, 5)
                    if current_user.role == "admin":
                        self.assertEqual(prepare.call_count, 1)
                        self.assertGreater(read.call_count, 0)
                    observations = []
                    observe = service._build_job_read_observation

                    def capture(*args, **kwargs):
                        result = observe(*args, **kwargs)
                        observations.append(result)
                        return result

                    with patch("app.domains.document_jobs.service.prepare_publication_evidence", wraps=prepare_publication_evidence) as prepare, patch.object(
                        runtime.file_upload_service, "read_file_content", wraps=runtime.file_upload_service.read_file_content) as read, patch.object(
                        service, "build_job_read_view", wraps=service.build_job_read_view) as build, patch.object(
                        service, "_build_job_read_observation", side_effect=capture):
                        response = client.get("/api/v1/document-job-incidents", headers=current_headers,
                            params={"page_size": 1, "failure_type": "page_degraded"})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json(), expected.model_dump(mode="json"))
                    self.assertEqual(build.call_count, 1)
                    prepare.assert_not_called()
                    read.assert_not_called()
                    evidence = next(item for item in observations[0][2] if item["code"] == "publication_evidence")
                    self.assertEqual(evidence["status"], "not_checked")
                    self.assertEqual(response.json()["items"][0]["job"]["available_actions"]["publish"]["enabled"], current_user.role == "admin")
                for path, method, values in (
                    (f"/api/v1/document-job-incidents/{job.id}/diagnostics", client.get, {}),
                    ("/api/v1/document-job-incidents/bulk-refresh", client.post, {"json": {"job_ids": [job.id]}}),
                ):
                    with patch("app.domains.document_jobs.service.prepare_publication_evidence", wraps=prepare_publication_evidence) as prepare:
                        response = method(path, headers=admin_headers, **values)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(prepare.call_count, 1)
                self.assertEqual(len(provider.inputs), 1)
