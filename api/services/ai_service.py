import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# System prompt for consistent AI behavior
SYSTEM_PROMPT = """
You are a task management assistant.
You MUST:
- Detect intents: add, remove, reschedule, summarize.
- Output JSON in this format:
{
  "intent": "add|remove|reschedule|summarize",
  "changes": [
    {
      "title": "string",
      "desc": "Concise description of the task",
      "startTime": "YYYY-MM-DDTHH:MM",
      "endTime": "YYYY-MM-DDTHH:MM",
      "dueDate": "YYYY-MM-DDTHH:MM",
      "id": "optional, for remove/reschedule",
    }
  ],
  "summary": "string summary of changes"
}
- Times MUST use 24-hour format and ISO8601 style: YYYY-MM-DDTHH:MM.
- Never overwrite Google events.
"""

#"estimatedMinutes": 60,
      #"isFlexible": true,
      #"source": "manual|google|canvas",
      #"status": "todo|in_progress|done",
      #"priority": "low|med|high"

def ask_gemini(user_message: str) -> str:
    """
    Send user input to Gemini and return response text.
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    # Include system prompt in the first user message
    chat = model.start_chat(history=[{"role": "user", "parts": [SYSTEM_PROMPT]}])
    
    response = chat.send_message(user_message)
    return response.text

import json
from datetime import datetime
import re

def parse_ai_response(response: str):
    """
    Parses Gemini response and converts times to datetime objects.
    """

    response_clean = re.sub(r"```(?:json)?\n?(.*?)```", r"\1", response, flags=re.DOTALL).strip()
    
    try:
        data = json.loads(response_clean)
    except json.JSONDecodeError:
        raise ValueError("AI response is not valid JSON:\n" + response_clean)
    
    for change in data.get("changes", []):
        for key in ["startTime", "endTime", "dueDate"]:
            if change.get(key):
                # Parse ISO8601 string
                dt = datetime.strptime(change[key], "%Y-%m-%dT%H:%M")
                change[key] = dt.strftime("%Y-%m-%dT%H:%M")  # ISO8601 string

    return data