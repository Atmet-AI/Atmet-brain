import io
import json
import unittest
from unittest.mock import patch

from atmet_brain import BrainError
from atmet_brain.extraction import CompatibleExtractor


class ProviderCase(unittest.TestCase):
    def extractor(self):
        return CompatibleExtractor("https://provider.example/v1", "chosen-model", "fixture-secret")

    def response(self, statement="The price is 100 USD.", quote="The price is 100 USD.", kind="fact"):
        content = json.dumps({"candidates": [{"statement": statement, "quote": quote, "kind": kind, "claim_key": "price"}]})
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

    def test_compatible_adapter_preserves_exact_evidence(self):
        with patch("atmet_brain.extraction.build_opener") as opener:
            opener.return_value.open.return_value = self.response()
            result = self.extractor().extract("The price is 100 USD.")
            request = opener.return_value.open.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual("chosen-model", body["model"])
            self.assertEqual("https://provider.example/v1/chat/completions", request.full_url)
            self.assertEqual("The price is 100 USD.", result[0].quote)

    def test_unsupported_quote_is_rejected(self):
        with patch("atmet_brain.extraction.build_opener") as opener:
            opener.return_value.open.return_value = self.response(quote="Invented source")
            with self.assertRaises(BrainError) as result:
                self.extractor().extract("The price is 100 USD.")
            self.assertEqual("unsupported_evidence", result.exception.code)

    def test_rule_text_cannot_be_promoted_by_model_kind(self):
        with patch("atmet_brain.extraction.build_opener") as opener:
            opener.return_value.open.return_value = self.response(statement="Manager approval is required.", quote="Manager approval is required.")
            result = self.extractor().extract("Manager approval is required.")
            self.assertEqual("rule_candidate", result[0].kind)

    def test_insecure_remote_endpoint_is_rejected(self):
        with self.assertRaises(BrainError):
            CompatibleExtractor("http://public.example/v1", "model", "fixture")

    def test_provider_errors_are_redacted(self):
        with patch("atmet_brain.extraction.build_opener") as opener:
            opener.return_value.open.side_effect = RuntimeError("fixture-secret and customer data")
            with self.assertRaises(BrainError) as result:
                self.extractor().extract("The price is 100 USD.")
            self.assertNotIn("fixture-secret", str(result.exception))
