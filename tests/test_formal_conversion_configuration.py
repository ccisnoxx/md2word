"""固化正式配置归属迁移后的默认值、旧入口及离线健康判定。"""

from __future__ import annotations

import builtins
import importlib.util
import json
import os
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock

from app.clients import openai_sdk
from app.conversion import runtime_config
from app.conversion.runtime import llm_client, translation_runtime
from app.core import conversion_config
from app.domains.translation import modes
from scripts.dev import (
    migrate_md2word_main_sandbox,
    run_local_mineru_conversion,
    run_local_mineru_debug_config,
    run_local_mineru_quality_matrix,
)


class FormalConversionConfigurationTests(TestCase):
    def test_configuration_defaults_remain_literal_values(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            conversion_config, "load_dotenv_file", return_value={}
        ):
            config = conversion_config.load_app_config()
        self.assertEqual(asdict(config), {
            "openai_base_url": "", "openai_api_key": "", "openai_model": "deepseek-v4-flash",
            "openai_http_referer": "https://cherry-ai.com", "openai_x_title": "Cherry Studio",
            "openai_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "CherryStudio/1.7.24 Chrome/144.0.7559.220 Electron/40.6.1 Safari/537.36",
            "openai_accept_language": "zh-CN", "translation_max_pages": 20,
            "translation_max_chars": 60000,
        })

    def test_environment_keeps_empty_value_priority_and_integer_limits(self):
        dotenv = {"OPENAI_MODEL": "dotenv-model", "TRANSLATION_MAX_PAGES": "7",
                  "TRANSLATION_MAX_CHARS": "800"}
        cases = [
            ({}, ("dotenv-model", 7, 800)),
            ({"OPENAI_MODEL": "env-model"}, ("env-model", 7, 800)),
            ({"OPENAI_MODEL": "", "TRANSLATION_MAX_PAGES": "", "TRANSLATION_MAX_CHARS": ""},
             ("", 20, 60000)),
            ({"TRANSLATION_MAX_PAGES": "0", "TRANSLATION_MAX_CHARS": "-2"},
             ("dotenv-model", 1, 1)),
        ]
        for environ, expected in cases:
            with self.subTest(environ=environ), mock.patch.dict(os.environ, environ, clear=True), \
                mock.patch.object(conversion_config, "load_dotenv_file", return_value=dotenv):
                config = conversion_config.load_app_config()
                self.assertEqual((config.openai_model, config.translation_max_pages,
                                  config.translation_max_chars), expected)
        with mock.patch.dict(os.environ, {"TRANSLATION_MAX_PAGES": "invalid"}, clear=True), \
            mock.patch.object(conversion_config, "load_dotenv_file", return_value={}):
            with self.assertRaises(ValueError):
                conversion_config.load_app_config()

    def test_dotenv_parser_and_root_remain_unchanged(self):
        self.assertEqual(conversion_config.ROOT_DIR, Path(__file__).resolve().parents[1])
        self.assertEqual(conversion_config.DOTENV_PATH, conversion_config.ROOT_DIR / ".env")
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            self.assertEqual(conversion_config.load_dotenv_file(path), {})
            path.write_text('# 注释\nignored\n MODEL = "first"\nMODEL=\'second\'\nEMPTY=\nURL=a=b\n',
                            encoding="utf-8")
            self.assertEqual(conversion_config.load_dotenv_file(path),
                             {"MODEL": "second", "EMPTY": "", "URL": "a=b"})

    def test_legacy_exports_and_generated_config_share_formal_objects(self):
        for name in ("APP_CONFIG", "AppConfig", "ROOT_DIR", "DOTENV_PATH",
                     "load_app_config", "load_dotenv_file", "_env"):
            self.assertIs(getattr(runtime_config, name), getattr(conversion_config, name))
        self.assertIs(llm_client.OpenAI, openai_sdk.OpenAI)
        self.assertEqual(llm_client.DEFAULT_MODEL, openai_sdk.DEFAULT_MODEL)
        for name, expected in (
            ("DEFAULT_TARGET_LANGUAGE", "zh-CN"),
            ("DEFAULT_TRANSLATION_DOMAIN", "electronics engineering technical document"),
            ("TRANSLATION_PROMPT_VERSION", "translation-minimal-v1"),
        ):
            self.assertEqual(getattr(modes, name), expected)
            self.assertEqual(getattr(translation_runtime, name), expected)
        namespace = {}
        with mock.patch.dict(os.environ, {"MD2WORD_OFFICIAL_REPO": str(conversion_config.ROOT_DIR)}):
            exec(migrate_md2word_main_sandbox.build_compat_config(conversion_config.ROOT_DIR), namespace)
        self.assertIs(namespace["APP_CONFIG"], conversion_config.APP_CONFIG)
        self.assertIs(namespace["ROOT_DIR"], conversion_config.ROOT_DIR)
        self.assertEqual(namespace["__all__"], ["APP_CONFIG", "ROOT_DIR"])

    def test_sdk_probe_and_model_fallback_keep_import_time_semantics(self):
        original_import = builtins.__import__
        sdk = object()
        for model in ("", "configured-model"):
            for outcome in (sdk, ImportError("缺少测试 SDK"), RuntimeError("测试 SDK 初始化失败")):
                with self.subTest(model=model, outcome=type(outcome).__name__):
                    def import_sdk(name, *args, **kwargs):
                        if name == "openai":
                            if isinstance(outcome, Exception):
                                raise outcome
                            return SimpleNamespace(OpenAI=outcome)
                        return original_import(name, *args, **kwargs)

                    # 独立加载探测模块，避免 reload 改写其他测试持有的共享模块状态。
                    spec = importlib.util.spec_from_file_location("_test_openai_sdk", openai_sdk.__file__)
                    module = importlib.util.module_from_spec(spec)
                    with mock.patch.object(conversion_config.APP_CONFIG, "openai_model", model), \
                        mock.patch("builtins.__import__", side_effect=import_sdk):
                        if isinstance(outcome, RuntimeError):
                            with self.assertRaises(RuntimeError):
                                spec.loader.exec_module(module)
                            continue
                        spec.loader.exec_module(module)
                    self.assertIs(module.OpenAI, None if isinstance(outcome, ImportError) else sdk)
                    self.assertEqual(module.DEFAULT_MODEL, model or "deepseek-v4-flash")

    def test_cli_default_model_and_limits_share_configuration(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"input_path": "package"}), encoding="utf-8")
            for model in ("", "configured-model"):
                with self.subTest(model=model), mock.patch.object(conversion_config.APP_CONFIG, "openai_model", model):
                    cli = run_local_mineru_conversion.parse_args(["package"])
                    debug = run_local_mineru_debug_config.build_conversion_kwargs(path)
                    matrix = run_local_mineru_quality_matrix.parse_args([])
                    expected = model or openai_sdk.DEFAULT_MODEL
                    for actual in (vars(cli), debug, vars(matrix)):
                        self.assertEqual(actual["translation_model"], expected)
                        self.assertEqual(actual["translation_max_pages"], conversion_config.APP_CONFIG.translation_max_pages)
                        self.assertEqual(actual["translation_max_chars"], conversion_config.APP_CONFIG.translation_max_chars)
                    self.assertEqual(cli.translation_mode, "direct")
                    self.assertEqual(debug["translation_mode"], "direct")
            matrix_config = run_local_mineru_quality_matrix.MatrixConfig()
            self.assertEqual(matrix_config.translation_model,
                             conversion_config.APP_CONFIG.openai_model or openai_sdk.DEFAULT_MODEL)

    def test_health_sdk_availability_preserves_key_requirement_and_reason(self):
        from tests.test_fastapi_jobs_backend import build_test_runtime

        for sdk in (None, object()):
            for key in ("", "test-key"):
                with self.subTest(sdk_available=sdk is not None, key_present=bool(key)), \
                    TemporaryDirectory() as directory, mock.patch.object(openai_sdk, "OpenAI", sdk):
                    runtime = build_test_runtime(Path(directory), openai_api_key=key,
                        translation_provider_backend="openai_compatible", default_translation_mode="en2zh")
                    checks = runtime.health_service.build_dependency_checks()
                available = bool(key) and sdk is not None
                self.assertEqual(checks["translation_client_configured"], available)
                self.assertEqual(checks["translation_available"], available)
                self.assertEqual("default_translation_unavailable" in checks["readiness_blockers"], not available)
                if not key:
                    self.assertEqual(checks["translation_unavailable_reason"], "OPENAI_API_KEY 未配置")
                elif sdk is None:
                    self.assertEqual(checks["translation_unavailable_reason"], "openai Python SDK 不可用")
                else:
                    self.assertNotIn("translation_unavailable_reason", checks)
