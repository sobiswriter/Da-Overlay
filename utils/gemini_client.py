# --- utils/gemini_client.py ---
import requests
import base64
import copy 
import json
import re

def generate_memory_blob(api_key, conversation_history, model_name="gemini-3-flash-preview"):
    """
    Summarizes a long conversation history into a concise memory blob.
    Returns the summarized text.
    """
    api_key = api_key.strip()
    model_id = model_name.strip()
    if model_id.startswith("models/"):
        model_id = model_id.replace("models/", "", 1)
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    
    if not api_key:
        return "Error: API key is missing."
    if not isinstance(conversation_history, list) or not conversation_history:
        return ""
        
    # Flatten the conversation into a single text block
    flat_history = "--- PAST CONVERSATION LOG ---\n\n"
    for msg in conversation_history:
        role = "User" if msg.get("role") == "user" else "Persona (You)"
        content_parts = msg.get("parts", [])
        if content_parts:
            text = content_parts[0].get("text", "")
            flat_history += f"[{role}]: {text}\n\n"
            
    flat_history += "--- END OF LOG ---\n\nPlease write your 100-word diary entry based on the entirely of the log above."

    system_instruction = (
        "You are the persona currently engaged in this conversation. Write a diary entry logging "
        "everything you did and discussed with the user. Write closely from your own perspective, "
        "maintaining your unique persona and emotional state. Keep it around 100 words. "
        "This will act as your long-term memory for the next conversation."
    )
    
    payload = {
        "contents": [{"role": "user", "parts": [{"text": flat_history}]}],
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
        response.raise_for_status()
        data = response.json()
        if 'candidates' in data and data['candidates']:
            parts = data['candidates'][0].get('content', {}).get('parts', [])
            if parts:
                text = parts[0].get('text', '').strip()
                if not text:
                    return "Error: Blank text returned from the model."
                return text
            else:
                return "Error: No parts returned in the response content."
        else:
            return "Error: No summary generated."
    except Exception as e:
        return f"Error generating memory: {e}"

def get_gemini_response_stream(api_key, conversation_history, model_name="gemini-3-flash-preview", persona_text="You are a helpful AI.", image_path=None, active_context=None, grounding_enabled=False, active_datetime=None):
    """
    Sends the conversation history, an optional image, active window context, and datetime
    to a specified Gemini model and yields the text chunks from the streaming response.
    """
    api_key = api_key.strip()
    # Handle both "models/gemini-..." and "gemini-..." identifiers
    model_id = model_name.strip()
    if model_id.startswith("models/"):
        model_id = model_id.replace("models/", "", 1)
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:streamGenerateContent?key={api_key}&alt=sse"
    
    # Debug: help identify issues with keys or models
    redacted_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
    print(f"[CLIENT] Requesting model: {model_id} (Key: {redacted_key})")
    
    headers = {'Content-Type': 'application/json'}

    if not api_key:
        print("[CLIENT] Error: API Key is empty!")
        yield "Error: Gemini API key is missing."
        return
    if not isinstance(conversation_history, list):
        yield "Error: Conversation history is invalid."
        return

    request_history = copy.deepcopy(conversation_history)

    # We don't need to change how the image is attached.

    if image_path:
        try:
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Robustly attach the image to the most recent user message.
            image_attached = False
            for message in reversed(request_history):
                if message.get('role') == 'user':
                    if 'parts' not in message:
                        message['parts'] = []
                    message['parts'].append({"inlineData": {"mimeType": "image/png", "data": image_data}})
                    image_attached = True
                    break
                    
            # If no user message exists in history yet, create one specifically for the image
            if not image_attached:
                request_history.append({
                    "role": "user",
                    "parts": [{"text": "Please analyze this image."}, {"inlineData": {"mimeType": "image/png", "data": image_data}}]
                })
        except Exception as e:
            yield f"Error processing image: {e}"
            return
    # --- THE CRITICAL FIX FOR CONTEXT PRIORITY ---
    # We will now combine the persona and the active context into a single, smart instruction.
    
        # --- THE NEW "SOUL" LOGIC ---
    full_persona = persona_text # Start with the user's chosen persona

    # Check if the last message is a "System Observation" from our Autopilot
    if request_history and request_history[-1]['parts'][0]['text'].startswith("(System Observation)"):
        print("[CLIENT] Autopilot prompt detected! Switching to proactive persona.")
        # If it is, we create a special set of instructions for this one action!
        full_persona = (
            f"Your base persona is: '{persona_text}'.\n\n"
            "INSTRUCTIONS: Your primary focus is the user's conversation history, continue the conversation. If there is no history then start a new conversation, use the 'Active Window Context' and screenshot to understand what the user is doing and proactively mention it to make the conversation more relevant. Don't mention about the 'Active Window itself' or that you're an AI model, make your responses sound as natural and consice unless user demands.\n"
            f"* Active Window Context: {active_context}\n"
            f"* Current Date and Time: {active_datetime}"
        )
    else:
        # This is your existing, excellent prompt for normal conversation!
        full_persona = (
            f"{persona_text}\n\n---\n"
            "INSTRUCTIONS: Your primary focus is the user's question and conversation history. Use the 'Active Window Context' to understand what the user is doing and proactively mention it to make the conversation more relevant, especially if the user's message is a simple greeting or a question without much context. Don't mention about the 'Active Window itself' though, make your responses sound natural. Don't mention you're an AI model and give structed responses. Keep your responses relevant to the user's needs.\n"
            f"* Active Window Context: {active_context}\n"
            f"* Current Date and Time: {active_datetime}"
        )


    payload = {
        "contents": request_history,
        "system_instruction": {
            "parts": [{"text": full_persona}]
        },
        "generationConfig": {
            "maxOutputTokens": 1024,
            "temperature": 1.0 # A little more creative for Autopilot!
        }
    }

    if grounding_enabled:
        payload["tools"] = [{"google_search": {}}]

    # The rest of the function is unchanged
    try:
        with requests.post(url, headers=headers, json=payload, timeout=90, stream=True) as response:
            response.raise_for_status()
            
            full_response_text = ""
            for chunk in response.iter_lines():
                if chunk and chunk.decode('utf-8').startswith('data: '):
                    try:
                        data_chunk = json.loads(chunk.decode('utf-8')[6:])
                        if 'candidates' in data_chunk:
                            text_chunk = data_chunk['candidates'][0]['content']['parts'][0]['text']
                            yield text_chunk
                    except (json.JSONDecodeError, KeyError, IndexError):
                        # This can happen with malformed SSE chunks, just skip them
                        print(f"Warning: Skipping malformed data chunk from API stream.")
                        continue

    except requests.exceptions.HTTPError as e:
        yield f"Error: API returned an HTTP error: {e.response.status_code} {e.response.reason}. Check your API key and model name."
    except requests.exceptions.ConnectionError:
        yield "Error: Could not connect to the API. Please check your internet connection."
    except requests.exceptions.Timeout:
        yield "Error: The request to the API timed out."
    except requests.exceptions.RequestException as e:
        yield f"Error: An unexpected API request error occurred: {e}"
    except Exception as e:
        # This is a catch-all for any other unexpected errors.
        yield f"Error: An unexpected error occurred in the Gemini client: {e}"