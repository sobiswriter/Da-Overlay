import os
import requests
import json
from dotenv import load_dotenv

with open("settings.json", "r") as f:
    settings = json.load(f)
api_key = settings.get("api_key")
model_id = "gemini-3-flash-preview"

url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:streamGenerateContent?key={api_key}&alt=sse"

payload = {
    "contents": [{"role": "user", "parts": [{"text": "Which model of iphone is on air right now in 2026?"}]}],
    "system_instruction": {"parts": [{"text": "You are a helpful AI."}]},
    "tools": [{"google_search": {}}]
}

headers = {'Content-Type': 'application/json'}

try:
    response = requests.post(url.replace('&alt=sse', ''), headers=headers, json=payload)
    with open('test_output.json', 'w') as f:
        json.dump(response.json(), f, indent=2)
except Exception as e:
    print("Error:", e)
