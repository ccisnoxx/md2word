from __future__ import annotations

# tests/test_terminology_releases.py: 校验术语治理包发布前校验和生命周期规则。

from unittest import TestCase

from app.core.errors import ApiError
from app.domains.resources.models import ResourceVersionRecord, ResourceVersionStatus
from app.domains.resources.service import ResourceVersionService
from app.domains.terminology.models import TerminologyReleaseRecord, TerminologyReleaseStatus
from app.domains.terminology.schemas import TerminologyReleaseCreateRequest, TerminologyReleaseScopeRequest
from app.domains.terminology.service import TerminologyReleaseService
from app.domains.translation.models import TranslationTermEntry, TranslationTermSetRecord, TranslationTermVersionRecord


HASH_RULE_A = "sha256:" + "a" * 64
HASH_RULE_B = "sha256:" + "b" * 64
HASH_TERMS_V1 = "sha256:" + "1" * 64
HASH_TERMS_V2 = "sha256:" + "2" * 64


class _MemoryTerminologyReleaseRepository:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], TerminologyReleaseRecord] = {}

    def save_release(self, record: TerminologyReleaseRecord) -> TerminologyReleaseRecord:
        self.records[(record.id, record.version)] = record
        return record

    def get_release(self, release_id: str, version: str | None = None) -> TerminologyReleaseRecord | None:
        matches = [record for key, record in self.records.items() if key[0] == release_id]
        if version is not None:
            return self.records.get((release_id, version))
        return sorted(matches, key=lambda record: (record.created_at, record.version))[-1] if matches else None

    def list_releases(
        self,
        *,
        status: TerminologyReleaseStatus | None = None,
        project: str | None = None,
        language_pair: str | None = None,
        content_type: str | None = None,
    ) -> list[TerminologyReleaseRecord]:
        records = list(self.records.values())
        if status is not None:
            records = [record for record in records if record.status == status]
        if project is not None:
            records = [record for record in records if record.scope.project == project]
        if language_pair is not None:
            records = [record for record in records if record.scope.language_pair == language_pair]
        if content_type is not None:
            records = [record for record in records if record.scope.content_type == content_type]
        return sorted(records, key=lambda record: (record.created_at, record.id, record.version))


class _MemoryResourceVersionRepository:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str, str], ResourceVersionRecord] = {}
        self.defaults: dict[tuple[str, str], str] = {}

    def save_resource_version(self, record: ResourceVersionRecord) -> ResourceVersionRecord:
        self.records[(record.resource_type, record.resource_id, record.version)] = record
        return record

    def get_resource_version(self, resource_type: str, resource_id: str, version: str) -> ResourceVersionRecord | None:
        return self.records.get((resource_type, resource_id, version))

    def list_resource_versions(self, resource_type: str, resource_id: str) -> list[ResourceVersionRecord]:
        return [
            record
            for key, record in sorted(self.records.items())
            if key[0] == resource_type and key[1] == resource_id
        ]

    def set_default_resource_version(self, resource_type: str, resource_id: str, version: str) -> None:
        self.defaults[(resource_type, resource_id)] = version

    def get_default_resource_version(self, resource_type: str, resource_id: str) -> ResourceVersionRecord | None:
        version = self.defaults.get((resource_type, resource_id))
        if version is None:
            return None
        return self.get_resource_version(resource_type, resource_id, version)


class _MemoryTranslationTermRepository:
    def __init__(self) -> None:
        self.sets: dict[str, TranslationTermSetRecord] = {}
        self.versions: dict[tuple[str, str], TranslationTermVersionRecord] = {}
        self.entries: dict[tuple[str, str], list[TranslationTermEntry]] = {}

    def save_set(self, record: TranslationTermSetRecord) -> TranslationTermSetRecord:
        self.sets[record.set_id] = record
        return record

    def get_set(self, set_id: str) -> TranslationTermSetRecord | None:
        return self.sets.get(set_id)

    def get_set_by_language_pair(self, language_pair: str) -> TranslationTermSetRecord | None:
        return next((record for record in self.sets.values() if record.language_pair == language_pair), None)

    def list_sets(self) -> list[TranslationTermSetRecord]:
        return list(self.sets.values())

    def save_version(self, record: TranslationTermVersionRecord) -> TranslationTermVersionRecord:
        self.versions[(record.set_id, record.version)] = record
        return record

    def get_version(self, set_id: str, version: str) -> TranslationTermVersionRecord | None:
        return self.versions.get((set_id, version))

    def list_versions(self, set_id: str) -> list[TranslationTermVersionRecord]:
        return [record for key, record in self.versions.items() if key[0] == set_id]

    def load_version(self, language_pair: str, version: str) -> list[TranslationTermEntry]:
        return list(self.entries.get((language_pair, version), []))

    def replace_terms(
        self,
        *,
        set_id: str,
        language_pair: str,
        version: str,
        snapshot_hash: str,
        entries: list[TranslationTermEntry],
        status: str = "published",
    ) -> None:
        self.save_set(TranslationTermSetRecord(set_id=set_id, language_pair=language_pair, default_version=version))
        self.save_version(
            TranslationTermVersionRecord(
                set_id=set_id,
                language_pair=language_pair,
                version=version,
                status=status,
                snapshot_hash=snapshot_hash,
                term_count=len(entries),
            )
        )
        self.entries[(language_pair, version)] = entries


class TerminologyReleaseServiceTests(TestCase):
    def setUp(self) -> None:
        self.release_repository = _MemoryTerminologyReleaseRepository()
        self.term_repository = _MemoryTranslationTermRepository()
        self.resource_repository = _MemoryResourceVersionRepository()
        self.resource_service = ResourceVersionService(self.resource_repository)
        self.service = TerminologyReleaseService(
            self.release_repository,
            translation_term_repository=self.term_repository,
            resource_version_service=self.resource_service,
        )
        self.term_set_id = "translation-terms-en2zh"
        self._save_rule_set("rules-a", "1.0.0", HASH_RULE_A)
        self._save_rule_set("rules-b", "1.0.0", HASH_RULE_B)

    def test_preflight_blocks_when_selected_version_has_no_publishable_terms(self) -> None:
        self._save_terms(
            "2026.06.20-1",
            HASH_TERMS_V1,
            [self._entry("FPGA", "现场可编程门阵列", status="editing", version="2026.06.20-1")],
        )

        report = self.service.preflight(self._request(term_version="2026.06.20-1"))

        self.assertTrue(report.blocking)
        self.assertIn("no_publishable_terms", [finding.code for finding in report.errors])
        self.assertEqual(report.summary.publishable_term_count, 0)

    def test_publish_blocks_duplicate_exact_scope(self) -> None:
        self._save_terms("2026.06.20-1", HASH_TERMS_V1, [self._entry("FPGA", "现场可编程门阵列")])
        request = self._request(term_version="2026.06.20-1")
        self.service.publish(request, actor_id="admin-1")

        with self.assertRaises(ApiError) as caught:
            self.service.publish(request, actor_id="admin-1")

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(caught.exception.code, "conflict")

    def test_preflight_flags_overlapping_scope_with_different_rule_configuration(self) -> None:
        self._save_terms("2026.06.20-1", HASH_TERMS_V1, [self._entry("FPGA", "现场可编程门阵列")])
        self.service.publish(
            self._request(term_version="2026.06.20-1", project="*", rule_set_id="rules-a"),
            actor_id="admin-1",
        )

        report = self.service.preflight(
            self._request(term_version="2026.06.20-1", project="electronics", rule_set_id="rules-b")
        )

        self.assertTrue(report.blocking)
        self.assertIn("scope_overlap", [finding.code for finding in report.warnings])
        self.assertIn("rule_configuration_overlap", [finding.code for finding in report.conflicts])

    def test_preflight_blocks_recommended_translation_conflict_in_overlapping_scope(self) -> None:
        self._save_terms("2026.06.20-1", HASH_TERMS_V1, [self._entry("FPGA", "现场可编程门阵列")])
        self._save_terms(
            "2026.06.20-2",
            HASH_TERMS_V2,
            [self._entry("FPGA", "FPGA", version="2026.06.20-2", recommended=("FPGA",))],
        )
        self.service.publish(
            self._request(term_version="2026.06.20-1", project="*", rule_set_id="rules-a"),
            actor_id="admin-1",
        )

        report = self.service.preflight(
            self._request(term_version="2026.06.20-2", project="electronics", rule_set_id="rules-a")
        )

        self.assertTrue(report.blocking)
        self.assertIn("recommended_translation_conflict", [finding.code for finding in report.conflicts])

    def test_copy_request_and_rollback_preserve_release_lineage(self) -> None:
        self._save_terms("2026.06.20-1", HASH_TERMS_V1, [self._entry("FPGA", "现场可编程门阵列")])
        record = self.service.publish(self._request(term_version="2026.06.20-1"), actor_id="admin-1")

        draft = self.service.copy_request(record.id, record.version)
        rolled_back = self.service.rollback(record.id, actor_id="admin-2")

        self.assertEqual(draft.source_release_id, record.id)
        self.assertEqual(draft.source_release_version, record.version)
        self.assertEqual(draft.scope.project, "electronics")
        self.assertEqual(rolled_back.status, "rolled_back")
        self.assertEqual(rolled_back.rolled_back_by, "admin-2")

    def _save_rule_set(self, resource_id: str, version: str, snapshot_hash: str) -> None:
        self.resource_repository.save_resource_version(
            ResourceVersionRecord(
                resource_type="term_rule_set",
                resource_id=resource_id,
                version=version,
                status=ResourceVersionStatus.PUBLISHED,
                snapshot_hash=snapshot_hash,
                payload={"rule_count": 2},
            )
        )

    def _save_terms(
        self,
        version: str,
        snapshot_hash: str,
        entries: list[TranslationTermEntry],
        *,
        status: str = "published",
    ) -> None:
        self.term_repository.replace_terms(
            set_id=self.term_set_id,
            language_pair="en2zh",
            version=version,
            snapshot_hash=snapshot_hash,
            entries=entries,
            status=status,
        )

    def _entry(
        self,
        source_term: str,
        target_term: str,
        *,
        version: str = "2026.06.20-1",
        status: str = "publishable",
        recommended: tuple[str, ...] = (),
        forbidden: tuple[str, ...] = (),
    ) -> TranslationTermEntry:
        return TranslationTermEntry(
            set_id=self.term_set_id,
            language_pair="en2zh",
            version=version,
            source_term=source_term,
            target_term=target_term,
            recommended_translations=recommended,
            forbidden_translations=forbidden,
            status=status,
        )

    def _request(
        self,
        *,
        term_version: str,
        project: str = "electronics",
        language_pair: str = "en2zh",
        content_type: str = "datasheet",
        rule_set_id: str = "rules-a",
    ) -> TerminologyReleaseCreateRequest:
        return TerminologyReleaseCreateRequest(
            translation_term_set_id=self.term_set_id,
            translation_term_version=term_version,
            term_rule_set_id=rule_set_id,
            term_rule_set_version="1.0.0",
            scope=TerminologyReleaseScopeRequest(
                project=project,
                language_pair=language_pair,
                content_type=content_type,
            ),
        )
