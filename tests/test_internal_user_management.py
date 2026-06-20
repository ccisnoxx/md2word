"""Tests for managed internal user lifecycle APIs and auth bootstrap."""

from __future__ import annotations

# File: tests/test_internal_user_management.py
# Purpose: Cover internal user management API, token invalidation, audit safety, and bootstrap behavior.

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.infrastructure.persistence import build_file_persistence_adapters
from app.main import create_app
from app.services.auth import AuthService
from tests.test_fastapi_jobs_backend import (
    build_auth_header,
    build_auth_users_json,
    build_multi_operator_auth_users_json,
    build_test_runtime,
)


class InternalUserManagementTests(TestCase):
    def test_config_bootstrap_imports_only_when_managed_repository_is_empty(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapters = build_file_persistence_adapters(Path(temp_dir))
            settings = Settings(
                _env_file=None,
                data_dir=temp_dir,
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            AuthService(settings, adapters.internal_user_repository)

            second_settings = Settings(
                _env_file=None,
                data_dir=temp_dir,
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_multi_operator_auth_users_json(),
            )
            AuthService(second_settings, adapters.internal_user_repository)

            self.assertEqual(adapters.internal_user_repository.count_internal_users(), 2)
            self.assertIsNone(adapters.internal_user_repository.get_internal_user_by_username("operator2"))

    def test_admin_user_management_lifecycle_audit_and_token_invalidation(self) -> None:
        with TemporaryDirectory() as temp_dir:
            runtime = build_test_runtime(
                Path(temp_dir),
                auth_jwt_secret_key="test-jwt-secret",
                auth_internal_users_json=build_auth_users_json(),
            )
            app = create_app(runtime)

            with TestClient(app) as client:
                admin_headers = build_auth_header(client, username="admin", password="admin-pass")
                operator_headers = build_auth_header(client, username="operator", password="operator-pass")

                operator_forbidden = client.get("/api/v1/users", headers=operator_headers)
                last_admin_conflict = client.patch(
                    "/api/v1/users/user_admin",
                    headers=admin_headers,
                    json={"status": "disabled"},
                )
                create_admin = client.post(
                    "/api/v1/users",
                    headers=admin_headers,
                    json={
                        "username": "second-admin",
                        "display_name": "Second Admin",
                        "role": "admin",
                        "status": "active",
                        "initial_password": "SecondAdmin123!",
                    },
                )
                create_operator = client.post(
                    "/api/v1/users",
                    headers=admin_headers,
                    json={
                        "username": "managed",
                        "display_name": "Managed Operator",
                        "role": "operator",
                        "status": "active",
                        "initial_password": "Managed123!",
                    },
                )
                duplicate_operator = client.post(
                    "/api/v1/users",
                    headers=admin_headers,
                    json={
                        "username": "MANAGED",
                        "display_name": "Duplicate",
                        "role": "operator",
                        "status": "active",
                        "initial_password": "Managed123!",
                    },
                )
                list_filtered = client.get("/api/v1/users", headers=admin_headers, params={"keyword": "managed"})

                managed_user_id = create_operator.json()["id"]
                managed_login = client.post(
                    "/api/v1/auth/login",
                    json={"username": "managed", "password": "Managed123!"},
                )
                managed_token = managed_login.json()["access_token"]
                reset_password = client.post(
                    f"/api/v1/users/{managed_user_id}/reset-password",
                    headers=admin_headers,
                    json={"new_password": "Reset123!"},
                )
                stale_after_reset = client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {managed_token}"},
                )
                old_password_login = client.post(
                    "/api/v1/auth/login",
                    json={"username": "managed", "password": "Managed123!"},
                )
                reset_login = client.post(
                    "/api/v1/auth/login",
                    json={"username": "managed", "password": "Reset123!"},
                )
                reset_token = reset_login.json()["access_token"]
                change_password = client.post(
                    "/api/v1/auth/change-password",
                    headers={"Authorization": f"Bearer {reset_token}"},
                    json={"current_password": "Reset123!", "new_password": "Changed123!"},
                )
                stale_after_change = client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {reset_token}"},
                )
                changed_login = client.post(
                    "/api/v1/auth/login",
                    json={"username": "managed", "password": "Changed123!"},
                )
                changed_token = changed_login.json()["access_token"]
                disable_user = client.patch(
                    f"/api/v1/users/{managed_user_id}",
                    headers=admin_headers,
                    json={"status": "disabled"},
                )
                stale_after_disable = client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {changed_token}"},
                )
                disabled_login = client.post(
                    "/api/v1/auth/login",
                    json={"username": "managed", "password": "Changed123!"},
                )
                enable_user = client.patch(
                    f"/api/v1/users/{managed_user_id}",
                    headers=admin_headers,
                    json={"status": "active"},
                )
            events = runtime.audit_event_repository.list_audit_events()

        self.assertEqual(operator_forbidden.status_code, 403)
        self.assertEqual(last_admin_conflict.status_code, 409)
        self.assertEqual(last_admin_conflict.json()["error_code"], "last_admin_conflict")
        self.assertEqual(create_admin.status_code, 201)
        self.assertEqual(create_operator.status_code, 201)
        self.assertNotIn("password_hash", create_operator.text)
        self.assertEqual(duplicate_operator.status_code, 409)
        self.assertEqual(duplicate_operator.json()["error_code"], "user_conflict")
        self.assertEqual(list_filtered.status_code, 200)
        self.assertEqual(list_filtered.json()["total"], 1)
        self.assertEqual(managed_login.status_code, 200)
        self.assertEqual(reset_password.status_code, 200)
        self.assertEqual(stale_after_reset.status_code, 401)
        self.assertEqual(old_password_login.status_code, 401)
        self.assertEqual(reset_login.status_code, 200)
        self.assertEqual(change_password.status_code, 200)
        self.assertEqual(stale_after_change.status_code, 401)
        self.assertEqual(changed_login.status_code, 200)
        self.assertEqual(disable_user.status_code, 200)
        self.assertEqual(stale_after_disable.status_code, 401)
        self.assertEqual(disabled_login.status_code, 401)
        self.assertEqual(enable_user.status_code, 200)

        actions = [event.action for event in events]
        for expected in (
            "users.create",
            "users.reset_password",
            "auth.change_password",
            "users.disable",
            "users.enable",
        ):
            self.assertIn(expected, actions)
        details_text = json.dumps([event.details for event in events], ensure_ascii=False)
        for secret in ("Managed123!", "Reset123!", "Changed123!", "pbkdf2_sha256"):
            self.assertNotIn(secret, details_text)
