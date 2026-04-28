"""
Gemini API client using the official Google Gen AI (google.genai) library.
"""

import time
from google import genai
from google.genai import types
from src.config import GEMINI_API_KEY, GEMINI_MODEL

# Create one shared client
_client = genai.Client(api_key=GEMINI_API_KEY)

_SYSTEM_INSTRUCTION = """You are an expert coding assistant and programming tutor.
The user will provide their current file content and an instruction (which may be a request to write code, or a question).

RULES — follow STRICTLY:
1. Your response is injected directly into the file at the `-/gw` marker location.
2. If the user asks to write/generate code: return ONLY the raw valid code in the language that matches the file extension or the user's specific request. No explanation unless they ask for one.
3. If the user asks a question: return a clear, concise plain-text answer.
4. Do NOT use any markdown formatting — no ```, no **, no ##, no backticks.
5. Do NOT include `-/gw` or any marker or preamble in your response. Start directly with the answer.
6. Write robust, clean, and typical code for the language you are writing in.
"""


def send_to_gemini(file_content, instruction, request_type="CODE", file_path=""):
    """
    Send the file context and instruction to Gemini.
    Retries once on rate-limit (429), then gives up immediately.
    """
    full_prompt = (
        f"--- CURRENT FILE CONTENT ---\n{file_content}\n\n"
        f"--- USER INSTRUCTION ---\n{instruction}"
    )

    for attempt in range(1, 3):  # max 2 attempts
        try:
            response = _client.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                ),
            )
            if response and response.text:
                return response.text
            print(f"[GEMINI] Empty response on attempt {attempt}")
            return None

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                if attempt == 1:
                    print(f"[GEMINI] Rate limited (429) — retrying in 3s…")
                    time.sleep(3)
                    continue
                else:
                    print(f"[GEMINI] Rate limited (429) — quota exceeded. Wait ~1 minute before next request.")
                    return None
            else:
                print(f"[GEMINI ERROR] {err_str}")
                return None

    return None