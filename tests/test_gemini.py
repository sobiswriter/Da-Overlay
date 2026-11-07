import json
import threading
import unittest
from unittest.mock import patch

from utils import gemini_client


class Response:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    def iter_lines(self):
        for event in self.events:
            yield ("data: " + json.dumps(event)).encode()


class GeminiTests(unittest.TestCase):
    def test_stream_reads_all_visible_parts_and_skips_thoughts(self):
        response = Response([{"candidates": [{"content": {"parts": [
            {"text": "private thought", "thought": True},
            {"text": "Hello "}, {"text": "world"},
        ]}}]}])
        with patch("utils.gemini_client.requests.post", return_value=response):
            text = "".join(gemini_client.get_gemini_response_stream(
                "fake-key", [{"role": "user", "parts": [{"text": "hi"}]}]))
        self.assertEqual(text, "Hello world")

    def test_key_is_sent_in_header_not_url_and_history_is_not_mutated(self):
        history = [{"role": "user", "parts": [{"text": "hi"}]}]
        before = json.dumps(history)
        response = Response([{"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}])
        with patch("utils.gemini_client.requests.post", return_value=response) as post:
            list(gemini_client.get_gemini_response_stream("private-key", history))
        self.assertNotIn("private-key", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "private-key")
        self.assertEqual(json.dumps(history), before)

    def test_empty_or_blocked_response_is_an_explicit_error(self):
        with patch("utils.gemini_client.requests.post", return_value=Response([{"promptFeedback": {"blockReason": "SAFETY"}}])):
            text = "".join(gemini_client.get_gemini_response_stream("fake", []))
        self.assertTrue(text.startswith("Error:"))

    def test_cancelled_request_never_opens_network_connection(self):
        cancelled = threading.Event()
        cancelled.set()
        with patch("utils.gemini_client.requests.post") as post:
            result = list(gemini_client.stream_events("fake", [], cancel_event=cancelled))
        self.assertEqual(result, [])
        post.assert_not_called()

    def test_cancelling_during_authentication_does_not_upload_the_message(self):
        cancelled = threading.Event()
        def authenticate(*args):
            cancelled.set()
            return "https://example.invalid/models", {"Authorization": "Bearer fixture"}
        with patch("utils.gemini_client.connection", side_effect=authenticate), patch("utils.gemini_client.requests.post") as post:
            result = list(gemini_client.stream_events("", [{"role": "user", "parts": [{"text": "keep this private"}]}], cancel_event=cancelled))
        self.assertEqual(result, [])
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
