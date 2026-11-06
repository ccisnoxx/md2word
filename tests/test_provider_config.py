"""验证 AI Provider 配置的私有创建、失败清理与 API 失败合同。"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from tempfile import TemporaryDirectory, mkstemp
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import require_admin_user
from app.api.errors import register_api_error_handlers
from app.core.config import Settings
from app.domains.translation.provider_config import AiProviderConfigRecord, AiProviderConfigService
from app.domains.translation.provider_config_router import router


class AiProviderConfigPermissionsTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.service = AiProviderConfigService(Settings(_env_file=None, data_dir=directory.name))
        self.path = self.service.config_path
        self.path.parent.mkdir(parents=True)
        self.old_content = b'{"api_key": "old-test-key"}\n'
        self.path.write_bytes(self.old_content)
        self.path.chmod(0o640)
        self.old_inode = self.path.stat().st_ino
        self.record = AiProviderConfigRecord(api_key="new-test-key", updated_by="测试管理员")

    def assert_old_record_preserved(self):
        self.assertEqual(self.path.read_bytes(), self.old_content)
        self.assertEqual(self.path.stat().st_ino, self.old_inode)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o640)

    def assert_no_temporary_files(self):
        self.assertEqual(set(self.path.parent.iterdir()), {self.path})

    def test_creation_and_atomic_replacement_use_private_permissions(self):
        real_open = os.open
        real_replace = Path.replace
        created_inodes = []

        def inspect_creation(path, flags, mode):
            descriptor = real_open(path, flags, mode)
            created_inodes.append(os.fstat(descriptor).st_ino)
            self.assertEqual(stat.S_IMODE(os.fstat(descriptor).st_mode), 0o600)
            self.assertEqual(Path(path).parent, self.path.parent)
            self.assertTrue(Path(path).name.startswith(f"{self.path.name}."))
            self.assertTrue(Path(path).name.endswith(".tmp"))
            self.assertNotEqual(Path(path).name, f"{self.path.name}.tmp")
            self.assertEqual(Path(path).read_bytes(), b"")
            return descriptor

        def inspect_replacement(temp_path, target):
            self.assert_old_record_preserved()
            self.assertEqual(stat.S_IMODE(temp_path.stat().st_mode), 0o600)
            self.assertEqual(temp_path.stat().st_ino, created_inodes[0])
            return real_replace(temp_path, target)

        # 宽松 umask 下也必须在创建瞬间私有，不能依赖进程环境掩盖权限窗口。
        previous_umask = os.umask(0)
        try:
            with patch("app.domains.translation.provider_config.os.open", side_effect=inspect_creation), patch.object(
                Path, "replace", inspect_replacement
            ):
                self.service._write_record(self.record)
        finally:
            os.umask(previous_umask)

        self.assertEqual(len(created_inodes), 1)
        self.assertEqual(self.path.stat().st_ino, created_inodes[0])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(
            self.path.read_text(encoding="utf-8"),
            json.dumps(self.record.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        )
        self.assertEqual(self.service.get_record(), self.record)
        self.assert_no_temporary_files()

    def test_permission_operation_failures_precede_secret_write_and_preserve_old_record(self):
        for operation in ("fchmod", "fstat"):
            with self.subTest(operation=operation):
                def fail_permission_operation(*_args):
                    temporary_files = list(self.path.parent.glob(f"{self.path.name}.*.tmp"))
                    self.assertEqual(len(temporary_files), 1)
                    self.assertEqual(temporary_files[0].read_bytes(), b"")
                    raise PermissionError("测试权限操作失败")

                with patch(
                    f"app.domains.translation.provider_config.os.{operation}", side_effect=fail_permission_operation
                ), patch("app.domains.translation.provider_config.os.fdopen") as open_stream:
                    with self.assertRaisesRegex(OSError, "无法设置或确认.*0600"):
                        self.service._write_record(self.record)

                open_stream.assert_not_called()
                self.assert_old_record_preserved()
                self.assert_no_temporary_files()

    def test_successful_chmod_with_wrong_actual_mode_is_rejected(self):
        real_fchmod = os.fchmod

        def leave_incorrect_mode(descriptor, _mode):
            real_fchmod(descriptor, 0o644)

        with patch("app.domains.translation.provider_config.os.fchmod", side_effect=leave_incorrect_mode), patch(
            "app.domains.translation.provider_config.os.fdopen"
        ) as open_stream:
            with self.assertRaisesRegex(OSError, "权限必须为 0600"):
                self.service._write_record(self.record)

        open_stream.assert_not_called()
        self.assert_old_record_preserved()
        self.assert_no_temporary_files()

    def test_creation_failure_is_explicit_and_preserves_old_record(self):
        with patch("app.domains.translation.provider_config.os.open", side_effect=PermissionError("测试创建失败")):
            with self.assertRaisesRegex(OSError, "无法创建.*临时文件"):
                self.service._write_record(self.record)

        self.assert_old_record_preserved()
        self.assert_no_temporary_files()

    def test_existing_fixed_and_random_temporary_files_do_not_block_save(self):
        descriptor, random_name = mkstemp(dir=self.path.parent, prefix=f"{self.path.name}.", suffix=".tmp")
        os.close(descriptor)
        residual_paths = [self.path.with_suffix(f"{self.path.suffix}.tmp"), Path(random_name)]
        residual_inodes = {}
        for residual_path in residual_paths:
            residual_path.write_bytes(b"existing-temporary-data")
            residual_path.chmod(0o644)
            residual_inodes[residual_path] = residual_path.stat().st_ino

        self.service._write_record(self.record)

        self.assertEqual(self.service.get_record(), self.record)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(set(self.path.parent.iterdir()), {self.path, *residual_paths})
        for residual_path in residual_paths:
            self.assertEqual(residual_path.read_bytes(), b"existing-temporary-data")
            self.assertEqual(residual_path.stat().st_ino, residual_inodes[residual_path])
            self.assertEqual(stat.S_IMODE(residual_path.stat().st_mode), 0o644)

    def test_existing_fixed_and_random_temporary_symlinks_do_not_block_save(self):
        target = self.path.parent / "unrelated-config.json"
        target.write_bytes(b"unrelated-file-content")
        target.chmod(0o640)
        target_inode = target.stat().st_ino
        descriptor, random_name = mkstemp(dir=self.path.parent, prefix=f"{self.path.name}.", suffix=".tmp")
        os.close(descriptor)
        Path(random_name).unlink()
        residual_paths = [self.path.with_suffix(f"{self.path.suffix}.tmp"), Path(random_name)]
        residual_inodes = {}
        for residual_path in residual_paths:
            residual_path.symlink_to(target)
            residual_inodes[residual_path] = residual_path.lstat().st_ino

        self.service._write_record(self.record)

        self.assertEqual(self.service.get_record(), self.record)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(set(self.path.parent.iterdir()), {self.path, target, *residual_paths})
        for residual_path in residual_paths:
            self.assertTrue(residual_path.is_symlink())
            self.assertEqual(residual_path.readlink(), target)
            self.assertEqual(residual_path.lstat().st_ino, residual_inodes[residual_path])
        self.assertEqual(target.read_bytes(), b"unrelated-file-content")
        self.assertEqual(target.stat().st_ino, target_inode)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)

    def test_stream_setup_and_replace_failures_clean_up_without_changing_old_record(self):
        for target in ("app.domains.translation.provider_config.os.fdopen", "pathlib.Path.replace"):
            with self.subTest(target=target):
                with patch(target, side_effect=OSError("测试持久化失败")):
                    with self.assertRaisesRegex(OSError, "测试持久化失败"):
                        self.service._write_record(self.record)

                self.assert_old_record_preserved()
                self.assert_no_temporary_files()

    def test_api_write_failures_return_500_without_success_audit(self):
        audit_service = Mock()
        app = FastAPI()
        app.state.runtime = SimpleNamespace(ai_provider_config_service=self.service, audit_service=audit_service)
        app.dependency_overrides[require_admin_user] = lambda: SimpleNamespace(id="admin-test", role="admin")
        register_api_error_handlers(app)
        app.include_router(router, prefix="/api/v1")

        # 使用真实路由及配置服务，仅替换管理员身份和本地文件失败点，不装配数据库或 Provider。
        with TestClient(app, raise_server_exceptions=False) as client:
            for operation in ("open", "fchmod", "fstat"):
                with self.subTest(operation=operation):
                    with patch(
                        f"app.domains.translation.provider_config.os.{operation}",
                        side_effect=PermissionError("测试持久化失败"),
                    ):
                        response = client.put(
                            "/api/v1/ai-provider-config",
                            json={"backend": "openai_compatible", "api_key": "new-test-key"},
                        )

                    self.assertEqual(response.status_code, 500)
                    self.assertNotIn("new-test-key", response.text)
                    audit_service.record.assert_not_called()
                    self.assert_old_record_preserved()
                    self.assert_no_temporary_files()
