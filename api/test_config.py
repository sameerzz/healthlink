"""Provider routing checks without live credentials or network requests."""
import os
import unittest
from unittest.mock import patch

import config
import llm


class ModelConfigTests(unittest.TestCase):
    def settings(self, provider, keys, model="test-model"):
        with patch.dict(os.environ, keys, clear=True), \
                patch.object(config, "MODEL_PROVIDER", provider), \
                patch.object(config, "MODEL_NAME", model):
            return config.get_model_settings()

    def test_provider_routes_and_keys(self):
        cases = [
            ("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
            ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1"),
            ("gemini", "GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/"),
            ("google", "GOOGLE_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/"),
        ]
        for provider, key_name, endpoint in cases:
            with self.subTest(provider=provider):
                self.assertEqual(self.settings(provider, {key_name: " test-key "}),
                                 {"api_key": "test-key", "base_url": endpoint, "model": "test-model"})

    def test_gemini_key_precedence_and_blank_fallback(self):
        self.assertEqual(self.settings("gemini", {"GEMINI_API_KEY": "first", "GOOGLE_API_KEY": "second"})["api_key"], "first")
        self.assertEqual(self.settings("gemini", {"GEMINI_API_KEY": " ", "GOOGLE_API_KEY": "second"})["api_key"], "second")

    def test_invalid_configuration(self):
        for provider, keys, model in [
            ("unknown", {}, "model"),
            ("openai", {"OPENROUTER_API_KEY": "wrong-provider"}, "model"),
            ("gemini", {}, "model"),
            ("openai", {"OPENAI_API_KEY": "key"}, " "),
        ]:
            with self.subTest(provider=provider, model=model):
                with self.assertRaises(config.ConfigurationError):
                    self.settings(provider, keys, model)

    def test_shared_client_uses_central_settings(self):
        settings = {"api_key": "test-key", "base_url": "https://example.com/v1", "model": "test-model"}
        llm.get_model.cache_clear()
        try:
            with patch("config.get_model_settings", return_value=settings), patch("llm.ChatOpenAI") as client:
                llm.get_model()
                self.assertEqual(client.call_args.kwargs["model"], "test-model")
                self.assertEqual(client.call_args.kwargs["base_url"], settings["base_url"])
                self.assertEqual(client.call_args.kwargs["api_key"], "test-key")
        finally:
            llm.get_model.cache_clear()
