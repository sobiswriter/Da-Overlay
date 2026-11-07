"""Gemini API keys or local Google Cloud ADC; credentials never cross the UI bridge."""
import re
import threading

import requests

DEFAULT_MODEL = "gemini-3.8-flash"
MODELS = [
    {"id": DEFAULT_MODEL, "name": "Gemini 3.8 Flash · Recommended"},
    {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash-Lite · Fast"},
    {"id": "gemini-4-argon", "name": "Gemini 4 Argon · Reasoning"},
]
_lock = threading.Lock()
_credentials = None
_identity = None


def validate_vertex(project, location, account=""):
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
        raise ValueError("Enter your Google Cloud project ID, not its display name.")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", location):
        raise ValueError("Choose a valid Google Cloud location, such as global.")
    if account and not re.fullmatch(r"[^\s@]{1,100}@[^\s@]{1,150}", account):
        raise ValueError("Enter a valid Google account email.")


def vertex_headers(project, account=""):
    global _credentials, _identity
    import google.auth
    from google.auth.transport.requests import Request
    from google.auth.exceptions import GoogleAuthError
    with _lock:
        try:
            if _credentials is None:
                _credentials, _ = google.auth.default(scopes=[
                    "https://www.googleapis.com/auth/cloud-platform",
                    "https://www.googleapis.com/auth/userinfo.email"])
            if not _credentials.valid:
                request = Request()
                def bounded_request(*args, **kwargs):
                    kwargs.setdefault("timeout", 20)
                    return request(*args, **kwargs)
                _credentials.refresh(bounded_request)
        except GoogleAuthError:
            raise ValueError("Google Cloud sign-in needs attention. Run gcloud auth application-default login, then test the connection again.") from None
        headers = {"Authorization": "Bearer " + _credentials.token,
                   "x-goog-user-project": project, "Content-Type": "application/json"}
        if account:
            if _identity is None:
                response = requests.post("https://oauth2.googleapis.com/tokeninfo",
                    data={"access_token": _credentials.token}, timeout=(10, 15))
                response.raise_for_status()
                _identity = response.json().get("email", "")
            if _identity.lower() != account.lower():
                raise ValueError("Google Cloud credentials belong to another account. Sign in to the selected account using gcloud auth application-default login.")
        return headers


def connection(api_key, provider="gemini", project="", location="global", account=""):
    if provider == "vertex":
        validate_vertex(project, location, account)
        host = "aiplatform.googleapis.com" if location == "global" else location + "-aiplatform.googleapis.com"
        return (f"https://{host}/v1/projects/{project}/locations/{location}/publishers/google/models",
                vertex_headers(project, account))
    if provider != "gemini":
        raise ValueError("Choose Gemini API or Google Cloud Vertex AI.")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("Add your Gemini API key or configure Vertex AI in Settings.")
    return "https://generativelanguage.googleapis.com/v1beta/models", {
        "Content-Type": "application/json", "x-goog-api-key": api_key.strip()}
