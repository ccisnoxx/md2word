"""覆盖 Translation Profile 内嵌 Prompt 的版本、不变量和草稿生命周期。"""

from __future__ import annotations

from copy import deepcopy
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.config import Settings
from app.domains.resources.models import ResourceVersionRecord, ResourceVersionStatus
from app.domains.resources.service import ResourceVersionService
from app.domains.translation.audit import TranslationCallAuditRecorder
from app.domains.translation.models import TranslationProviderRequest, TranslationTextItem
from app.domains.translation.profiles_service import (
    DEFAULT_PROMPT_VERSIONS,
    DRAFT_VERSION,
    TranslationProfileDraftSnapshotConflictError,
    TranslationProfileVersionService,
    prompt_content_hash,
    translation_profile_snapshot_from_record,
)
from app.domains.translation.provider import OpenAICompatibleTranslationProvider
from app.domains.translation.schemas import TranslationProfileDraftUpdateRequest
from tests.test_resource_versioning import HASH_V1, _MemoryResourceVersionRepository


class TranslationProfilePromptTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.settings = Settings(_env_file=None, data_dir=self.temp_dir.name)
        self.repository = _MemoryResourceVersionRepository()
        self.resource_service = ResourceVersionService(self.repository)
        self.service = TranslationProfileVersionService(
            self.settings,
            self.resource_service,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_bootstrap_seeds_four_profiles_without_overwriting_defaults(self) -> None:
        created = self.service.bootstrap_default_profiles_if_missing()
        defaults_before = dict(self.repository.defaults)

        created_again = self.service.bootstrap_default_profiles_if_missing()

        self.assertEqual(len(created), 4)
        self.assertEqual(created_again, [])
        self.assertEqual(self.repository.defaults, defaults_before)
        expected_targets = {
            "en2zh": "zh-CN",
            "ru2zh": "zh-CN",
            "zh2en": "en",
            "zh2ru": "ru",
        }
        for language_pair, target_language in expected_targets.items():
            with self.subTest(language_pair=language_pair):
                snapshot = self.service.resolve_default_snapshot(language_pair)
                self.assertIsNotNone(snapshot)
                self.assertEqual(snapshot.target_language, target_language)
                self.assertEqual(
                    snapshot.prompt.id,
                    DEFAULT_PROMPT_VERSIONS[language_pair],
                )
                self.assertTrue(snapshot.prompt.built_in)
                self.assertTrue(snapshot.prompt.markdown)
                self.assertTrue(snapshot.prompt.content_hash.startswith("sha256:"))

    def test_new_payload_invariant_rejects_invalid_prompt_state(self) -> None:
        self.service.bootstrap_default_profiles_if_missing()
        record = self.repository.get_default_resource_version(
            "translation_profile",
            "electronics-en2zh",
        )
        self.assertIsNotNone(record)
        base_payload = deepcopy(record.payload)
        cases = {
            "duplicate_name": lambda payload: payload["prompt_schemes"].append(
                {
                    **payload["prompt_schemes"][0],
                    "id": "prompt_duplicate",
                    "built_in": False,
                }
            ),
            "bad_hash": lambda payload: payload["prompt_schemes"][0].__setitem__(
                "content_hash",
                "sha256:" + "0" * 64,
            ),
            "missing_active": lambda payload: payload.__setitem__(
                "prompt_version",
                "prompt_missing",
            ),
            "missing_builtin": lambda payload: payload["prompt_schemes"][0].__setitem__(
                "built_in",
                False,
            ),
            "unknown_schema": lambda payload: payload.__setitem__(
                "schema_version",
                3,
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                payload = deepcopy(base_payload)
                mutate(payload)
                invalid_record = record.model_copy(update={"payload": payload})
                with self.assertRaises(ValueError):
                    translation_profile_snapshot_from_record(
                        self.settings,
                        invalid_record,
                    )

    def test_legacy_published_and_draft_materialize_seed_prompt(self) -> None:
        legacy_payload = {
            "translation_profile_id": "electronics-ru2zh",
            "language_pair": "ru2zh",
            "version": "legacy",
            "target_language": "zh-CN",
            "domain": "electronics datasheet",
            "prompt_version": "ru2zh@v1",
            "model": "legacy-model",
            "max_pages_per_batch": 7,
            "max_chars_per_batch": 1234,
        }
        published = ResourceVersionRecord(
            resource_type="translation_profile",
            resource_id="electronics-ru2zh",
            version="legacy",
            status=ResourceVersionStatus.PUBLISHED,
            snapshot_hash=HASH_V1,
            payload=legacy_payload,
        )
        snapshot = translation_profile_snapshot_from_record(
            self.settings,
            published,
        )
        self.assertEqual(snapshot.prompt.id, "ru2zh@v1")
        self.assertTrue(snapshot.prompt.markdown)

        self.resource_service.create_draft(
            resource_type="translation_profile",
            resource_id="electronics-ru2zh",
            version=DRAFT_VERSION,
            snapshot_hash=HASH_V1,
            payload=legacy_payload,
        )
        draft = self.service.get_draft("electronics-ru2zh")
        stored = self.repository.get_resource_version(
            "translation_profile",
            "electronics-ru2zh",
            DRAFT_VERSION,
        )
        self.assertEqual(draft.prompt_version, "ru2zh@v1")
        self.assertEqual(stored.payload["schema_version"], 2)
        self.assertEqual(stored.payload["prompt_schemes"][0]["id"], "ru2zh@v1")

    def test_prompt_crud_uses_cas_and_controlled_delete(self) -> None:
        self.service.bootstrap_default_profiles_if_missing()
        draft = self.service.get_draft("electronics-en2zh")
        built_in_id = draft.prompt_version
        created = self.service.create_prompt(
            "electronics-en2zh",
            name="精简方案",
            source_prompt_id=built_in_id,
            expected_snapshot_hash=draft.snapshot_hash,
        )
        custom = next(prompt for prompt in created.prompt_schemes if not prompt.built_in)
        self.assertEqual(created.prompt_version, built_in_id)
        self.assertEqual(
            custom.markdown,
            next(prompt for prompt in draft.prompt_schemes if prompt.id == built_in_id).markdown,
        )

        with self.assertRaises(TranslationProfileDraftSnapshotConflictError):
            self.service.update_prompt(
                "electronics-en2zh",
                custom.id,
                name="过期写入",
                markdown="stale",
                expected_snapshot_hash=draft.snapshot_hash,
            )

        updated = self.service.update_prompt(
            "electronics-en2zh",
            custom.id,
            name="精简方案 v2",
            markdown="# bound-prompt-marker",
            expected_snapshot_hash=created.snapshot_hash,
        )
        activated = self.service.activate_prompt(
            "electronics-en2zh",
            custom.id,
            expected_snapshot_hash=updated.snapshot_hash,
        )
        self.assertEqual(activated.prompt_version, custom.id)
        with self.assertRaisesRegex(ValueError, "当前启用"):
            self.service.delete_prompt(
                "electronics-en2zh",
                custom.id,
                expected_snapshot_hash=activated.snapshot_hash,
            )

        switched = self.service.activate_prompt(
            "electronics-en2zh",
            built_in_id,
            expected_snapshot_hash=activated.snapshot_hash,
        )
        deleted = self.service.delete_prompt(
            "electronics-en2zh",
            custom.id,
            expected_snapshot_hash=switched.snapshot_hash,
        )
        self.assertNotIn(custom.id, [prompt.id for prompt in deleted.prompt_schemes])

    def test_published_prompt_cannot_be_deleted_and_rollback_restores_it(self) -> None:
        self.service.bootstrap_default_profiles_if_missing()
        draft = self.service.get_draft("electronics-en2zh")
        built_in_id = draft.prompt_version
        created = self.service.create_prompt(
            "electronics-en2zh",
            name="已发布方案",
            source_prompt_id=built_in_id,
            expected_snapshot_hash=draft.snapshot_hash,
        )
        custom = next(prompt for prompt in created.prompt_schemes if not prompt.built_in)
        updated = self.service.update_prompt(
            "electronics-en2zh",
            custom.id,
            name=custom.name,
            markdown="# published-prompt-marker",
            expected_snapshot_hash=created.snapshot_hash,
        )
        active_custom = self.service.activate_prompt(
            "electronics-en2zh",
            custom.id,
            expected_snapshot_hash=updated.snapshot_hash,
        )
        first = self.service.publish_draft(
            "electronics-en2zh",
            make_default=True,
        )
        active_builtin = self.service.activate_prompt(
            "electronics-en2zh",
            built_in_id,
            expected_snapshot_hash=active_custom.snapshot_hash,
        )
        second = self.service.publish_draft(
            "electronics-en2zh",
            make_default=True,
        )

        with self.assertRaisesRegex(ValueError, "历史 Profile 版本"):
            self.service.delete_prompt(
                "electronics-en2zh",
                custom.id,
                expected_snapshot_hash=active_builtin.snapshot_hash,
            )
        self.service.rollback(
            "electronics-en2zh",
            first.version,
        )
        restored = self.service.resolve_default_snapshot("en2zh")
        self.assertEqual(restored.prompt.id, custom.id)
        self.assertEqual(restored.prompt.markdown, "# published-prompt-marker")
        self.assertNotEqual(first.version, second.version)

    def test_basic_draft_update_preserves_prompt_invariant(self) -> None:
        self.service.bootstrap_default_profiles_if_missing()
        draft = self.service.get_draft("electronics-zh2en")
        updated = self.service.update_draft(
            "electronics-zh2en",
            TranslationProfileDraftUpdateRequest(
                language_pair="zh2en",
                target_language="en",
                domain="electronics",
                model="model-v2",
                max_pages_per_batch=8,
                max_chars_per_batch=2048,
                expected_snapshot_hash=draft.snapshot_hash,
            ),
        )

        self.assertEqual(updated.prompt_version, draft.prompt_version)
        self.assertEqual(updated.prompt_schemes, draft.prompt_schemes)
        self.assertEqual(updated.target_language, "en")

    def test_prompt_markdown_round_trip_and_provider_use_exact_bound_content(self) -> None:
        self.service.bootstrap_default_profiles_if_missing()
        draft = self.service.get_draft("electronics-zh2en")
        created = self.service.create_prompt(
            "electronics-zh2en",
            name="保留空白方案",
            source_prompt_id=draft.prompt_version,
            expected_snapshot_hash=draft.snapshot_hash,
        )
        custom = next(prompt for prompt in created.prompt_schemes if not prompt.built_in)
        markdown = "  # bound-prompt-marker\n\n保留末尾换行。\n"
        updated = self.service.update_prompt(
            "electronics-zh2en",
            custom.id,
            name=custom.name,
            markdown=markdown,
            expected_snapshot_hash=created.snapshot_hash,
        )
        stored = next(prompt for prompt in updated.prompt_schemes if prompt.id == custom.id)
        request = TranslationProviderRequest(
            language_pair="zh2en",
            source_language="zh",
            target_language="en",
            items=(TranslationTextItem(id="item-1", text="输入失调电压"),),
            prompt_id=stored.id,
            prompt_content_hash=stored.content_hash,
            system_prompt_markdown=stored.markdown,
        )

        system_prompt = OpenAICompatibleTranslationProvider(self.settings)._system_prompt(request)

        self.assertEqual(stored.markdown, markdown)
        self.assertEqual(stored.content_hash, prompt_content_hash(markdown))
        self.assertTrue(system_prompt.startswith(markdown))
        self.assertIn("source=zh; target=en", system_prompt)

    def test_audit_projection_and_error_redaction_exclude_prompt_markdown(self) -> None:
        markdown = "# secret-system-prompt\nDo not expose this marker."
        request = TranslationProviderRequest(
            language_pair="zh2en",
            source_language="zh",
            target_language="en",
            items=(TranslationTextItem(id="item-1", text="正文"),),
            prompt_id="prompt-test",
            prompt_content_hash=prompt_content_hash(markdown),
            system_prompt_markdown=markdown,
        )
        recorder = object.__new__(TranslationCallAuditRecorder)

        full_request = recorder._full_request_payload(request)
        summary = recorder._system_prompt_summary(request)
        redacted_error = recorder._redact_error_message(
            f"provider error: {markdown}",
            sensitive_text=markdown,
        )

        self.assertNotIn("system_prompt_markdown", full_request)
        self.assertNotIn(markdown, str(full_request))
        self.assertEqual(summary["id"], "prompt-test")
        self.assertEqual(summary["content_hash"], prompt_content_hash(markdown))
        self.assertNotIn(markdown, redacted_error)


if __name__ == "__main__":
    import unittest

    unittest.main()
