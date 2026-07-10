"""覆盖 MinerU 运行时账号与密钥文件的优先级、校验和安全写入合同。"""

from __future__ import annotations

import json
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from pydantic import ValidationError

from app.core.config import Settings
from app.domains.mineru.config import MinerUConfigError, MinerUConfigService


class MinerUConfigServiceTests(TestCase):
    """验证运行时文件是唯一覆盖源且不会保留历史密钥。"""

    def test_uses_settings_only_when_runtime_file_is_absent(self):
        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                data_dir=temp_dir,
                mineru_api_token="  env-token  ",
                mineru_uid="  env-uid  ",
            )

            config = MinerUConfigService(settings).get_effective_config()

        self.assertEqual(config.api_token, "env-token")
        self.assertEqual(config.uid, "env-uid")
        self.assertEqual(config.source, "settings")
        self.assertIsNone(config.updated_at)
        self.assertIsNone(config.updated_by)

    def test_update_replaces_current_record_atomically_with_private_permissions(self):
        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                data_dir=temp_dir,
                mineru_api_token="env-token",
                mineru_uid="env-uid",
            )
            service = MinerUConfigService(settings)

            first = service.update_credentials(
                api_token="  first-token  ",
                uid="  first-uid  ",
                updated_by="admin-1",
            )
            second = service.update_credentials(
                api_token="second-token",
                uid="second-uid",
                updated_by="admin-2",
            )
            payload = json.loads(settings.mineru_config_file.read_text(encoding="utf-8"))
            sibling_names = {path.name for path in settings.mineru_config_file.parent.iterdir()}
            file_mode = stat.S_IMODE(settings.mineru_config_file.stat().st_mode)

        self.assertEqual(first.api_token, "first-token")
        self.assertEqual(first.uid, "first-uid")
        self.assertEqual(second.api_token, "second-token")
        self.assertEqual(second.uid, "second-uid")
        self.assertEqual(second.source, "runtime_config")
        self.assertEqual(payload["api_token"], "second-token")
        self.assertEqual(payload["uid"], "second-uid")
        self.assertEqual(payload["updated_by"], "admin-2")
        self.assertEqual(set(payload), {"api_token", "uid", "updated_at", "updated_by"})
        self.assertEqual(sibling_names, {"mineru_config.json"})
        self.assertEqual(file_mode, 0o600)

    def test_invalid_runtime_file_never_falls_back_and_can_be_repaired(self):
        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                data_dir=temp_dir,
                mineru_api_token="env-token",
                mineru_uid="env-uid",
            )
            settings.mineru_config_file.parent.mkdir(parents=True, exist_ok=True)
            settings.mineru_config_file.write_text('{"api_token":', encoding="utf-8")
            service = MinerUConfigService(settings)

            with self.assertRaises(MinerUConfigError):
                service.get_effective_config()

            repaired = service.update_credentials(
                api_token="repaired-token",
                uid="repaired-uid",
                updated_by="admin-1",
            )
            effective = service.get_effective_config()

        self.assertEqual(repaired.api_token, "repaired-token")
        self.assertEqual(repaired.uid, "repaired-uid")
        self.assertEqual(effective.api_token, "repaired-token")
        self.assertEqual(effective.uid, "repaired-uid")
        self.assertEqual(effective.source, "runtime_config")

    def test_runtime_file_missing_uid_never_mixes_with_environment(self):
        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                data_dir=temp_dir,
                mineru_api_token="env-token",
                mineru_uid="env-uid",
            )
            settings.mineru_config_file.parent.mkdir(parents=True, exist_ok=True)
            settings.mineru_config_file.write_text(
                json.dumps(
                    {
                        "api_token": "runtime-token",
                        "updated_at": "2026-07-10T00:00:00Z",
                        "updated_by": "admin-1",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(MinerUConfigError):
                MinerUConfigService(settings).get_effective_config()

    def test_broken_runtime_config_symlink_never_falls_back(self):
        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                data_dir=temp_dir,
                mineru_api_token="env-token",
                mineru_uid="env-uid",
            )
            settings.mineru_config_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                settings.mineru_config_file.symlink_to(Path(temp_dir) / "missing-mineru-config.json")
            except OSError as exc:
                self.skipTest(f"当前平台不支持符号链接：{exc}")

            with self.assertRaises(MinerUConfigError):
                MinerUConfigService(settings).get_effective_config()

    def test_blank_update_is_rejected_without_creating_runtime_file(self):
        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                data_dir=temp_dir,
                mineru_api_token="env-token",
                mineru_uid="env-uid",
            )
            service = MinerUConfigService(settings)

            with self.assertRaises(ValidationError):
                service.update_credentials(api_token="   ", uid="new-uid", updated_by="admin-1")
            with self.assertRaises(ValidationError):
                service.update_credentials(api_token="new-token", uid="   ", updated_by="admin-1")

            exists = settings.mineru_config_file.exists()
            effective = service.get_effective_config()

        self.assertFalse(exists)
        self.assertEqual(effective.api_token, "env-token")
        self.assertEqual(effective.uid, "env-uid")
