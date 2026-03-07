import os
import json
import base64
import requests

api_key = os.getenv("GEMINI_API_KEY") 
if not api_key:
    # Try reading from settings.json
    try:
        with open("settings.json", "r") as f:
            api_key = json.load(f).get("api_key")
    except:
        pass

print(f"API Key found: {'Yes' if api_key else 'No'}")

# create dummy image
image_path = "test_img.png"
from PIL import Image
img = Image.new('RGB', (100, 100), color='red')
img.save(image_path)

with open(image_path, "rb") as image_file:
    image_data = base64.b64encode(image_file.read()).decode('utf-8')

payload = {
    "contents": [
        {
            "role": "user",
            "parts": [
                {"text": "What color is this image?"},
                {"inlineData": {"mimeType": "image/png", "data": image_data}}
            ]
        }
    ]
}

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
headers = {'Content-Type': 'application/json'}

print("Sending request...")
response = requests.post(url, headers=headers, json=payload)
print("Status Code:", response.status_code)
try:
    print(response.json())
except:
    print(response.text)

# Also test the old format (inline_data) to confirm it fails
print("\n--- Testing old format ---")
payload_old = {
    "contents": [
        {
            "role": "user",
            "parts": [
                {"text": "What color is this image?"},
                {"inline_data": {"mime_type": "image/png", "data": image_data}}
            ]
        }
    ]
}
response_old = requests.post(url, headers=headers, json=payload_old)
print("Status Code:", response_old.status_code)
try:
    print(response_old.json())
except:
    print(response_old.text)

os.remove(image_path)
