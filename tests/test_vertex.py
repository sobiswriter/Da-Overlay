import unittest
from unittest.mock import Mock, patch

from utils import google_connection
from utils.gemini_client import stream_events
from tests.test_gemini import Response


class VertexTests(unittest.TestCase):
    def test_vertex_uses_bearer_credentials_and_project_endpoint(self):
        headers = {"Authorization": "Bearer private-access-token"}
        with patch("utils.google_connection.vertex_headers", return_value=headers), patch("utils.gemini_client.requests.post", return_value=Response([{"candidates": [{"content": {"parts": [{"text": "Connected"}]}}]}])) as post:
            events = list(stream_events("", [{"role": "user", "parts": [{"text": "hi"}]}],
                provider="vertex", project="test-project-123", audio_bytes=b"RIFFfixture"))
        self.assertEqual(events[0]["text"], "Connected")
        self.assertIn("/projects/test-project-123/locations/global/publishers/google/models/gemini-3.8-flash", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["headers"], headers)
        self.assertNotIn("private-access-token", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["json"]["contents"][0]["parts"][1]["inlineData"]["mimeType"], "audio/wav")

    def test_account_mismatch_prevents_model_request(self):
        credentials = Mock(valid=True, token="private-token")
        identity = Mock()
        identity.json.return_value = {"email": "different@example.com"}
        with patch.object(google_connection, "_credentials", credentials), patch.object(google_connection, "_identity", None), patch("utils.google_connection.requests.post", return_value=identity) as post:
            with self.assertRaisesRegex(ValueError, "another account"):
                google_connection.vertex_headers("test-project-123", "requested@example.com")
        self.assertEqual(post.call_args.args[0], "https://oauth2.googleapis.com/tokeninfo")
        self.assertNotIn("private-token", post.call_args.args[0])

    def test_invalid_project_or_location_cannot_be_used_as_an_endpoint(self):
        for project, location in [("../other", "global"), ("test-project-123", "evil.example/path")]:
            with self.assertRaises(ValueError):
                google_connection.validate_vertex(project, location)
