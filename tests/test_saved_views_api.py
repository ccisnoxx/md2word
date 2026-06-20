"""Cover saved_views HTTP API behavior with real auth and runtime wiring."""

# File: tests/test_saved_views_api.py
# Purpose: Cover saved_views HTTP API behavior with real auth and runtime wiring.
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.auth.models import AuthenticatedUser
from tests.test_fastapi_jobs_backend import (
    build_auth_header,
    build_multi_operator_auth_users_json,
    build_test_runtime,
)


class RestrictedSavedViewsAuthService:
    """Return a user who can access document jobs but not translation QA."""

    def authenticate_bearer_token(self, token: str) -> AuthenticatedUser:
        return AuthenticatedUser(
            id="user_restricted",
            username="restricted",
            role="operator",
            tenant_id="tenant_default",
            company_id="company_default",
            token_scopes=["document_jobs:read"],
        )


class SavedViewsApiTests(TestCase):
    def test_saved_views_crud_default_reorder_and_owner_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_multi_operator_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                owner_headers = build_auth_header(client)
                other_headers = build_auth_header(client, username="operator2", password="operator2-pass")

                empty_response = client.get("/api/v1/saved-views", params={"page_key": "jobs"}, headers=owner_headers)
                self.assertEqual(empty_response.status_code, 200)
                self.assertEqual(empty_response.json(), {"items": []})

                first_response = client.post(
                    "/api/v1/saved-views",
                    headers=owner_headers,
                    json={
                        "page_key": "jobs",
                        "name": "Failed jobs",
                        "filters": {"status": "failed"},
                        "sort": "updated_at_desc",
                        "is_default": True,
                    },
                )
                self.assertEqual(first_response.status_code, 201)
                first_view = first_response.json()
                self.assertTrue(first_view["is_default"])

                duplicate_response = client.post(
                    "/api/v1/saved-views",
                    headers=owner_headers,
                    json={
                        "page_key": "jobs",
                        "name": " failed jobs ",
                        "filters": {"status": "failed"},
                        "sort": "updated_at_desc",
                    },
                )
                self.assertEqual(duplicate_response.status_code, 409)

                second_response = client.post(
                    "/api/v1/saved-views",
                    headers=owner_headers,
                    json={
                        "page_key": "jobs",
                        "name": "Active jobs",
                        "filters": {"status_group": "active"},
                        "sort": "updated_at_desc",
                        "is_default": True,
                    },
                )
                self.assertEqual(second_response.status_code, 201)
                second_view = second_response.json()

                owner_list_response = client.get("/api/v1/saved-views", params={"page_key": "jobs"}, headers=owner_headers)
                other_list_response = client.get("/api/v1/saved-views", params={"page_key": "jobs"}, headers=other_headers)
                owner_items = owner_list_response.json()["items"]
                self.assertEqual(other_list_response.json(), {"items": []})
                self.assertEqual(
                    {item["view_id"]: item["is_default"] for item in owner_items},
                    {first_view["view_id"]: False, second_view["view_id"]: True},
                )

                other_update_response = client.patch(
                    f"/api/v1/saved-views/{first_view['view_id']}",
                    headers=other_headers,
                    json={"name": "Other cannot update"},
                )
                self.assertEqual(other_update_response.status_code, 404)

                invalid_filter_response = client.patch(
                    f"/api/v1/saved-views/{first_view['view_id']}",
                    headers=owner_headers,
                    json={"filters": {"qa_job_id": "docjob_1"}},
                )
                self.assertEqual(invalid_filter_response.status_code, 400)

                rename_response = client.patch(
                    f"/api/v1/saved-views/{first_view['view_id']}",
                    headers=owner_headers,
                    json={"name": "Failed and recent", "is_default": True},
                )
                self.assertEqual(rename_response.status_code, 200)
                self.assertEqual(rename_response.json()["name"], "Failed and recent")
                self.assertTrue(rename_response.json()["is_default"])

                reorder_response = client.post(
                    "/api/v1/saved-views/reorder",
                    headers=owner_headers,
                    json={"page_key": "jobs", "view_ids": [second_view["view_id"], first_view["view_id"]]},
                )
                self.assertEqual(reorder_response.status_code, 200)
                self.assertEqual(
                    [item["view_id"] for item in reorder_response.json()["items"]],
                    [second_view["view_id"], first_view["view_id"]],
                )
                self.assertEqual([item["position"] for item in reorder_response.json()["items"]], [0, 1])

                delete_response = client.delete(f"/api/v1/saved-views/{second_view['view_id']}", headers=owner_headers)
                self.assertEqual(delete_response.status_code, 204)
                after_delete_response = client.get("/api/v1/saved-views", params={"page_key": "jobs"}, headers=owner_headers)
                self.assertEqual([item["view_id"] for item in after_delete_response.json()["items"]], [first_view["view_id"]])

    def test_saved_views_api_rejects_pages_without_permission_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(Path(temp_dir))
            runtime.auth_service = RestrictedSavedViewsAuthService()
            app = create_app(runtime)

            with TestClient(app) as client:
                headers = {"Authorization": "Bearer restricted-token"}
                allowed_response = client.get("/api/v1/saved-views", params={"page_key": "jobs"}, headers=headers)
                self.assertEqual(allowed_response.status_code, 200)

                denied_response = client.get("/api/v1/saved-views", params={"page_key": "translation_qa"}, headers=headers)
                self.assertEqual(denied_response.status_code, 403)
                self.assertEqual(denied_response.json()["error_code"], "role_forbidden")
