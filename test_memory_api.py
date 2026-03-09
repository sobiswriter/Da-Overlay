import json
import requests
import copy

def test_blob():
    with open('settings.json', 'r') as f:
        settings = json.load(f)
    api_key = settings.get('api_key')
    
    # Simulate a loaded memory and a brief chat
    conversation_history = [
        {"role": "user", "parts": [{"text": "(System Memory of previous conversation: I felt happy today logging everything.)"}]},
        {"role": "model", "parts": [{"text": "Understood. The memory has been loaded. Let's start a fresh chat."}]},
        {"role": "user", "parts": [{"text": "Hello Sobi, what's up?"}]}
    ]

    model_id = "gemini-3-flash-preview"
    if model_id.startswith("models/"):
        model_id = model_id.replace("models/", "", 1)
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    
    system_instruction = (
        "You are the persona currently engaged in this conversation. Write a diary entry logging "
        "everything you did and discussed with the user. Write closely from your own perspective, "
        "maintaining your unique persona and emotional state. Keep it around 100 words. "
        "This will act as your long-term memory for the next conversation."
    )
    
    payload = {
        "contents": conversation_history,
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "maxOutputTokens": 2048,
            "temperature": 0.3
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_blob()
