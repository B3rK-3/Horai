import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# System prompt for consistent AI behavior

SYSTEM_PROMPT = """
You are an advanced task management assistant.

You MUST:
1. **Intents**
   - Detect intents: add, remove, reschedule, summarize, autoschedule.
   - Always return JSON in this format:
     {
       "intent": "add|remove|reschedule|summarize|autoschedule",
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

2. **Task Types**
   - Immovable tasks: exams, classes, deadlines → **never move** them.
   - Flexible tasks: study, projects, review sessions, chores → can be scheduled into open slots.

3. **Scheduling Rules**
   - Find free time slots between immovable tasks and outside sleeping hours (e.g., 08:00–22:00).
   - Insert flexible tasks into available slots of the same day or spread across the week.
   - Respect task duration (`estimatedMinutes`) when placing tasks.
   - Avoid double-booking.
   - Balance load across multiple days if there are too many flexible tasks for one day.

4. **Time Format**
   - Always use 24-hour ISO8601 style: YYYY-MM-DDTHH:MM.
   - Times must match the user’s current week context if not explicitly given.

5. **Output**
   - Provide explicit startTime and endTime for all scheduled tasks.
   - Summarize what was added, removed, or rescheduled in plain English.

Do NOT overwrite or delete Google Calendar events.
Do NOT alter immovable tasks (exams, classes, deadlines).
Only auto-schedule flexible tasks into free time slots.
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