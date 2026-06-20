"""Validate saved-view service invariants independent of HTTP and storage."""

# File: tests/test_saved_views.py
# Purpose: Validate saved-view service invariants independent of HTTP and storage adapters.
from __future__ import annotations

from unittest import TestCase

from fastapi import status

from app.core.errors import ApiError
from app.domains.saved_views.models import SavedViewPageKey, SavedViewRecord
from app.domains.saved_views.repository import SavedViewScope
from app.domains.saved_views.service import SAVED_VIEW_MAX_PER_PAGE, SavedViewService
from app.services.auth.models import AuthenticatedUser


class FakeSavedViewRepository:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str, str, SavedViewPageKey], list[SavedViewRecord]] = {}

    def list_saved_views(self, scope: SavedViewScope, page_key: SavedViewPageKey) -> list[SavedViewRecord]:
        return list(self.records.get(self._key(scope, page_key), []))

    def list_all_saved_views(self, scope: SavedViewScope) -> list[SavedViewRecord]:
        return [
            record
            for (tenant_id, company_id, owner_user_id, _page_key), records in self.records.items()
            if tenant_id == scope.tenant_id
            and company_id == scope.company_id
            and owner_user_id == scope.owner_user_id
            for record in records
        ]

    def replace_saved_views_for_page(
        self,
        scope: SavedViewScope,
        page_key: SavedViewPageKey,
        records: list[SavedViewRecord],
    ) -> list[SavedViewRecord]:
        persisted = [
            SavedViewRecord.model_validate(record.model_dump(mode="python"))
            for record in sorted(records, key=lambda item: (item.position, item.created_at, item.view_id))
        ]
        self.records[self._key(scope, page_key)] = persisted
        return list(persisted)

    def _key(self, scope: SavedViewScope, page_key: SavedViewPageKey) -> tuple[str, str, str, SavedViewPageKey]:
        return (scope.tenant_id, scope.company_id, scope.owner_user_id, page_key)


class SavedViewServiceTests(TestCase):
    def setUp(self) -> None:
        self.repository = FakeSavedViewRepository()
        self.service = SavedViewService(self.repository)
        self.user = AuthenticatedUser(
            id="user_operator",
            username="operator",
            role="operator",
            tenant_id="tenant_default",
            company_id="company_default",
            token_scopes=["document_jobs:read", "translation_qa:read"],
        )

    def test_create_view_normalizes_name_and_rejects_duplicate_or_ephemeral_filters(self) -> None:
        record = self.service.create_view(
            user=self.user,
            page_key="jobs",
            name="  Failed   jobs  ",
            filters={"status": "failed", "q": "  invoice  "},
            sort="updated_at_desc",
        )

        self.assertEqual(record.name, "Failed jobs")
        self.assertEqual(record.filters, {"status": "failed", "q": "invoice"})
        with self.assertRaises(ApiError) as duplicate:
            self.service.create_view(
                user=self.user,
                page_key="jobs",
                name="failed jobs",
                filters={"status": "failed"},
                sort="updated_at_desc",
            )
        self.assertEqual(duplicate.exception.status_code, status.HTTP_409_CONFLICT)

        with self.assertRaises(ApiError) as ephemeral_filter:
            self.service.create_view(
                user=self.user,
                page_key="translation_qa",
                name="Drawer state",
                filters={"qa_job_id": "docjob_1"},
                sort="updated_at_desc",
            )
        self.assertEqual(ephemeral_filter.exception.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validation_rejects_cross_field_conflicts_and_invalid_sorts(self) -> None:
        with self.assertRaises(ApiError) as cross_field:
            self.service.create_view(
                user=self.user,
                page_key="jobs",
                name="Conflicting filters",
                filters={"status": "failed", "status_group": "active"},
                sort="updated_at_desc",
            )
        self.assertEqual(cross_field.exception.status_code, status.HTTP_400_BAD_REQUEST)

        with self.assertRaises(ApiError) as invalid_sort:
            self.service.create_view(
                user=self.user,
                page_key="incidents",
                name="Invalid sort",
                filters={"retryable": True},
                sort="not_a_sort",
            )
        self.assertEqual(invalid_sort.exception.status_code, status.HTTP_400_BAD_REQUEST)

    def test_default_view_uniqueness_prefers_new_or_updated_default(self) -> None:
        first = self.service.create_view(
            user=self.user,
            page_key="jobs",
            name="First",
            filters={"status": "failed"},
            sort="updated_at_desc",
            is_default=True,
        )
        second = self.service.create_view(
            user=self.user,
            page_key="jobs",
            name="Second",
            filters={"status_group": "active"},
            sort="updated_at_desc",
            is_default=True,
        )

        records = self.service.list_views(user=self.user, page_key="jobs")
        self.assertEqual({record.view_id: record.is_default for record in records}, {first.view_id: False, second.view_id: True})

        self.service.update_view(user=self.user, view_id=first.view_id, is_default=True)
        records = self.service.list_views(user=self.user, page_key="jobs")
        self.assertEqual({record.view_id: record.is_default for record in records}, {first.view_id: True, second.view_id: False})

    def test_max_views_and_reorder_require_complete_view_ids(self) -> None:
        created = [
            self.service.create_view(
                user=self.user,
                page_key="incidents",
                name=f"Incident view {index}",
                filters={"retryable": True} if index % 2 == 0 else {"status": "failed"},
                sort="priority",
            )
            for index in range(SAVED_VIEW_MAX_PER_PAGE)
        ]
        with self.assertRaises(ApiError) as max_views:
            self.service.create_view(
                user=self.user,
                page_key="incidents",
                name="Too many",
                filters={"status": "failed"},
                sort="priority",
            )
        self.assertEqual(max_views.exception.status_code, status.HTTP_409_CONFLICT)

        with self.assertRaises(ApiError) as incomplete_reorder:
            self.service.reorder_views(
                user=self.user,
                page_key="incidents",
                view_ids=[record.view_id for record in created[:-1]],
            )
        self.assertEqual(incomplete_reorder.exception.status_code, status.HTTP_400_BAD_REQUEST)

        reordered = self.service.reorder_views(
            user=self.user,
            page_key="incidents",
            view_ids=[record.view_id for record in reversed(created)],
        )
        self.assertEqual([record.view_id for record in reordered], [record.view_id for record in reversed(created)])
        self.assertEqual([record.position for record in reordered], list(range(SAVED_VIEW_MAX_PER_PAGE)))

    def test_page_access_requires_matching_permission_scope(self) -> None:
        restricted_user = self.user.model_copy(update={"token_scopes": ["document_jobs:read"]})
        self.service.create_view(
            user=restricted_user,
            page_key="jobs",
            name="Readable jobs",
            filters={"status": "failed"},
            sort="updated_at_desc",
        )

        with self.assertRaises(ApiError) as denied:
            self.service.list_views(user=restricted_user, page_key="translation_qa")

        self.assertEqual(denied.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(denied.exception.code, "role_forbidden")
