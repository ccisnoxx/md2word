import json
import os
import unittest
from unittest import mock


# tests/test_llm_client_characterization.py: 固化 conversion LLM client 的现有行为。

try:
    from .runtime_direct_loaders import load_llm_client_module
except ImportError:  # pragma: no cover - compatibility for direct execution
    from runtime_direct_loaders import load_llm_client_module


class LLMClientCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.llm = load_llm_client_module()

    def test_build_client_requires_sdk(self):
        with mock.patch.object(self.llm, "OpenAI", None):
            with self.assertRaises(RuntimeError):
                self.llm.build_client(self.llm.LLMClientConfig())

    def test_build_client_requires_api_key(self):
        class FakeOpenAI:
            def __init__(self, **_kwargs):
                pass

        with (
            mock.patch.object(self.llm, "OpenAI", FakeOpenAI),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(self.llm.APP_CONFIG, "openai_api_key", ""),
        ):
            with self.assertRaises(RuntimeError):
                self.llm.build_client(self.llm.LLMClientConfig())

    def test_translate_payload_uses_chat_completion_items(self):
        class FakeRawResponse:
            def __init__(self):
                self.usage = mock.Mock(prompt_tokens=11, completion_tokens=22, total_tokens=33)
                self.choices = [mock.Mock(message=mock.Mock(content='{"items":[{"id":"p0001.b0001.text","text":"译文"}]}'))]

            def parse(self):
                return self

        class FakeCompletions:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return FakeRawResponse()

        class FakeWithRawResponse:
            def __init__(self):
                self.completions = FakeCompletions()

        class FakeChat:
            def __init__(self):
                self.completions = mock.Mock(with_raw_response=FakeCompletions())

        class FakeClient:
            def __init__(self):
                self.chat = mock.Mock(completions=mock.Mock(with_raw_response=FakeCompletions()))

        payload = {
            "target_language": "zh-CN",
            "domain": "electronics engineering technical document",
            "batches": [
                {
                    "batch_id": "batch_001",
                    "section": "1 Features",
                    "section_continuation": False,
                    "page_range": [1, 1],
                    "items": [{"id": "p0001.b0001.text", "text": "The device supports 5 V operation."}],
                }
            ],
        }

        with mock.patch.object(self.llm, "build_client", return_value=FakeClient()) as build_client:
            result = self.llm.translate_payload(payload, self.llm.LLMClientConfig(model="gpt-test"))

        build_client.assert_called_once()
        self.assertEqual(
            result,
            {"batches": [{"batch_id": "batch_001", "items": [{"id": "p0001.b0001.text", "text": "译文"}]}]},
        )

    def test_parse_json_response_accepts_code_fence(self):
        parsed = self.llm.parse_json_response(
            '```json\n{"items":[{"id":"p0001.b0001.text","text":"译文"}]}\n```'
        )

        self.assertEqual(parsed["items"][0]["text"], "译文")

    def test_build_system_prompt_reads_template_file(self):
        template_text = "固定英译中系统提示"
        with mock.patch.object(self.llm, "load_system_prompt_template", return_value=template_text):
            prompt = self.llm.build_system_prompt()

        self.assertEqual(prompt, "固定英译中系统提示")

    def test_build_system_prompt_selects_ru2zh_template(self):
        with mock.patch.object(self.llm, "load_system_prompt_template", return_value="固定俄译中系统提示") as loader:
            prompt = self.llm.build_system_prompt("ru2zh")

        self.assertEqual(prompt, "固定俄译中系统提示")
        self.assertTrue(str(loader.call_args.args[0]).endswith("resources/prompts/translation_ru2zh.md"))


if __name__ == "__main__":
    unittest.main()
