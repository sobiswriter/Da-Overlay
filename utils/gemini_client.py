# --- utils/gemini_client.py ---
import requests
import base64
import copy 
import json
import re

def get_gemini_response_stream(api_key, conversation_history, model_name="gemini-2.5-flash", persona_text="You are a helpful AI.", image_path=None, active_context=None):
    """
    Sends the conversation history, an optional image, and active window context
    to a specified Gemini model and yields the text chunks from the streaming response.
    """
    api_key = api_key.strip()
    # Handle both "models/gemini-..." and "gemini-..." identifiers
    model_id = model_name.strip()
    if model_id.startswith("models/"):
        model_id = model_id.replace("models/", "", 1)
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:streamGenerateContent?key={api_key}&alt=sse"
    print(f"[CLIENT] Requesting model: {model_id}")
    headers = {'Content-Type': 'application/json'}

    if not api_key:
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
            for message in reversed(request_history):
                if message['role'] == 'user':
                    message['parts'].append({"inline_data": {"mime_type": "image/png", "data": image_data}})
                    break
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
            f"* Active Window Context: {active_context}"
        )
    else:
        # This is your existing, excellent prompt for normal conversation!
        full_persona = (
            f"{persona_text}\n\n---\n"
            "INSTRUCTIONS: Your primary focus is the user's question and conversation history. Use the 'Active Window Context' to understand what the user is doing and proactively mention it to make the conversation more relevant, especially if the user's message is a simple greeting or a question without much context. Don't mention about the 'Active Window itself' though, make your responses sound natural. Don't mention you're an AI model and give structed responses. Keep your responses relevant to the user's needs.\n"
            f"* Active Window Context: {active_context}"
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