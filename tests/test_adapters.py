import unittest
from unittest.mock import patch

from kakanyo.adapters import OpenAICompatibleAdapter, ClaudeMessagesAdapter, ProviderError
from kakanyo.core import ContractError, assert_external_release, read_json
from pathlib import Path

class AdapterTests(unittest.TestCase):
    def test_missing_token_fails_without_request(self):
        adapter = OpenAICompatibleAdapter("https://example.org/v1/chat/completions", "example", "KAKANYO_TEST_TOKEN_NOT_SET")
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ProviderError):
                adapter.invoke("test")
    def test_openai_response_schema(self):
        body = '{"claims":[],"contradictions":[],"newly_open":[],"weakened_claims":[],"next_pressure_tests":[],"self_limitations":[]}'
        with patch.dict("os.environ", {"KAKANYO_TEST_TOKEN": "synthetic-token"}):
            with patch("kakanyo.adapters._post", return_value={"choices": [{"message": {"content": body}}]}) as call:
                result = OpenAICompatibleAdapter("https://example.org/api", "example", "KAKANYO_TEST_TOKEN").invoke("hello")
                self.assertEqual(result["claims"], [])
                self.assertIn("Authorization", call.call_args.args[2])
    def test_invalid_model_json_is_rejected(self):
        with patch.dict("os.environ", {"KAKANYO_TEST_TOKEN": "synthetic-token"}):
            with patch("kakanyo.adapters._post", return_value={"choices": [{"message": {"content": "not json"}}]}):
                with self.assertRaises(ProviderError):
                    OpenAICompatibleAdapter("https://example.org", "test", "KAKANYO_TEST_TOKEN").invoke("test")
    def test_claude_text_response_schema(self):
        body = '{"claims":[],"contradictions":[],"newly_open":[],"weakened_claims":[],"next_pressure_tests":[],"self_limitations":[]}'
        with patch.dict("os.environ", {"KAKANYO_TEST_TOKEN": "synthetic-token"}):
            with patch("kakanyo.adapters._post", return_value={"content": [{"type": "text", "text": body}]}):
                result = ClaudeMessagesAdapter("model", "KAKANYO_TEST_TOKEN").invoke("hello")
                self.assertEqual(result["claims"], [])

if __name__ == "__main__":
    unittest.main()
