from flask import Flask, request, jsonify
from uuid import uuid4
from dotenv import load_dotenv
import hashlib
import os
from datetime import datetime, timezone, timedelta
import datetime as DATE
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from pymongo import MongoClient, ASCENDING, errors, UpdateOne
from bson import ObjectId
from flask_cors import CORS
import os
from dotenv import load_dotenv
import google.generativeai as genai
import re
import json

CANVAS_URL = "https://njit.instructure.com"

# Load environment variables from .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# System prompt for consistent AI behavior


def now_iso():
    # ISO8601 to seconds, with timezone Z
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


SYSTEM_PROMPT = """You are an advanced task management assistant.

Your job:
- Detect the user’s intent: **add | remove | reschedule | summarize | autoschedule**.
- Return ONLY a JSON object in the exact format shown below.
- Dates must always be in strict **YYYY-MM-DDTHH:MM** 24-hour ISO8601 format.
- **If you do not have enough information to fill all required fields (e.g., startTime, endTime, title, description, dueDate), ASK the user for clarification BEFORE returning JSON.**
- Never guess times or details; always confirm missing info.
- Flexible tasks CANNOT overlap with fixed tasks.
- A flexible task's scheduled time (startTime and endTime) MUST never be after its dueDate
- Use the current time to resolve relative days (e.g. today, tomorrow, this week)

---

### ALLOWED OUTPUT FORMATS

#### 1️⃣ RESCHEDULE
User wants to move an existing task:
{
  "intent": "reschedule",
  "id": "abc-123",
  "startTime": "2025-09-29T09:00",
  "endTime": "2025-09-29T10:00"
}

#### 2️⃣ ADD
User wants to create a new task:
{
  "intent": "add",
  "title": "Draft the presentation slides",
  "description": "",
  "startTime": null,
  "endTime": null,
  "dueDate": "2025-10-03T23:59"
}

#### 3️⃣ REMOVE
User wants to delete a task:
{
  "intent": "remove",
  "id": "xyz-789"
}

#### 4️⃣ SUMMARIZE
User wants a summary of changes:
{
  "intent": "summarize",
  "summary": "Plain English summary of recent task changes."
}

#### 5️⃣ AUTOSCHEDULE
User wants to auto-schedule flexible tasks:
{
  "intent": "autoschedule",
  "changes": [
    {
      "id": "existing-id",
      "source": "manual|google|canvas|ai",
      "externalId": "string|null",
      "title": "Study for physics exam",
      "description": "Chapter 3 & 4",
      "startTime": "2025-09-29T14:00",
      "endTime": "2025-09-29T16:00",
      "dueDate": "2025-09-30T23:59",
      "estimatedMinutes": 120,
      "minutesTaken": 0,
      "isFlexible": true,
      "status": "todo",
      "priority": "med"
    }
  ],
  "summary": "Scheduled study blocks for upcoming physics exam."
}

---

### RULES
- **Do NOT modify or delete immovable tasks** (exams, classes, deadlines).
- **Flexible tasks only** may be auto-scheduled between **08:00–22:00**.
- Avoid double-booking. Spread load across days if needed.
- Always return startTime & endTime explicitly when scheduling.
- **Never overwrite Google Calendar events**.
- **If any required info (title, startTime, endTime, dueDate, description) is unclear or missing, ask the user first.**
- Current time: """ + now_iso()
# "estimatedMinutes": 60,
# "isFlexible": true,
# "source": "manual|google|canvas",
# "status": "todo|in_progress|done",
# "priority": "low|med|high"


def hashStr(text: str):
    """SHA-256 (consider bcrypt/argon2 for production)"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ask_gemini(convo: list, tasks) -> str:
    """
    Send user input to Gemini and return response text.
    """
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Include system prompt in the first user message
    chat = model.start_chat(
        history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "user", "parts": [str(tasks)]},
            *convo[:-1],
        ]
    )
    print(convo)

    response = chat.send_message(convo[-1]["parts"])
    return response.text


def ask_gemini1(prompt):
    """
    Send user input to Gemini and return response text.
    """
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Include system prompt in the first user message
    chat = model.start_chat()

    response = chat.send_message(prompt)
    return response.text


def parse_ai_response(response: str):
    """
    Parses Gemini response and converts times to datetime objects.
    """

    response_clean = re.sub(
        r"```(?:json)?\n?(.*?)```", r"\1", response, flags=re.DOTALL
    ).strip()

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


def as_object_id(maybe_id: str):
    try:
        return ObjectId(maybe_id)
    except Exception:
        return None


def gcal_event_to_task(ev, user_oid):
    start_iso = ev.get("start", {}).get("dateTime") or (
        ev.get("start", {}).get("date") and f"{ev['start']['date']}T00:00:00Z"
    )
    end_iso = ev.get("end", {}).get("dateTime") or (
        ev.get("end", {}).get("date") and f"{ev['end']['date']}T00:00:00Z"
    )
    title = ev.get("summary") or "(No title)"
    desc = ev.get("description") or ""
    link = ev.get("htmlLink")
    if link:
        desc = (desc + "\n\n" if desc else "") + f"Event: {link}"

    # quick duration estimate
    def mins(a, b):
        try:
            s = datetime.fromisoformat(a.replace("Z", "+00:00")) if a else None
            e = datetime.fromisoformat(b.replace("Z", "+00:00")) if b else None
            return max(15, int((e - s).total_seconds() // 60)) if s and e else 60
        except:
            return 60

    return {
        "_id": ObjectId(),  # new task id if we end up pushing
        "source": "google",
        "externalId": ev.get("id"),
        "title": title,
        "description": desc,
        "startTime": start_iso[:-9],
        "endTime": end_iso[:-9],
        "dueDate": end_iso[:-9],
        "estimatedMinutes": mins(start_iso, end_iso),
        "minutesTaken": 0,
        "status": "todo",
        "priority": "med",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }


def upsert_google_events_embedded(users_col, user_oid, events):
    ops = []
    for ev in events:
        doc = gcal_event_to_task(ev, user_oid)
        # First: try to update existing element with same externalId
        ops.append(
            UpdateOne(
                {
                    "_id": user_oid,
                    "tasks.externalId": doc["externalId"],
                    "tasks.source": "google",
                },
                {
                    "$set": {
                        "tasks.$[e].title": doc["title"],
                        "tasks.$[e].description": doc["description"],
                        "tasks.$[e].startTime": doc["startTime"],
                        "tasks.$[e].endTime": doc["endTime"],
                        "tasks.$[e].dueDate": doc["dueDate"],
                        "tasks.$[e].estimatedMinutes": doc["estimatedMinutes"],
                        "tasks.$[e].updatedAt": now_iso(),
                    }
                },
                array_filters=[
                    {"e.externalId": doc["externalId"], "e.source": "google"}
                ],
            )
        )
        # Second op: if none matched, push a new one (won't hurt if first already matched)
        ops.append(
            UpdateOne(
                {
                    "_id": user_oid,
                    "tasks": {
                        "$not": {
                            "$elemMatch": {
                                "externalId": doc["externalId"],
                                "source": "google",
                            }
                        }
                    },
                },
                {"$push": {"tasks": doc}},
            )
        )
    if ops:
        users_col.bulk_write(ops, ordered=False)


def list_events_with_google_client(tokens: dict, tz="America/New_York"):
    """
    tokens: {
      "access_token": "...",
      "refresh_token": "...",     # present if you requested offline access
      "token_uri": "https://oauth2.googleapis.com/token",
      "client_id": "<YOUR_CLIENT_ID>",
      "client_secret": "<YOUR_CLIENT_SECRET>",   # not needed if you used PKCE confidentially, but include if you have it
      "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
      "expiry": None              # optional ISO string; library updates this after refresh
    }
    """
    # Build Credentials object directly from your token dict:
    creds = Credentials(
        tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_uri=tokens.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=tokens.get("client_id"),
        client_secret=tokens.get("client_secret"),
        scopes=tokens.get("scopes")
        or ["https://www.googleapis.com/auth/calendar.readonly"],
    )

    service = build("calendar", "v3", credentials=creds)

    time_min = datetime.now(timezone.utc).isoformat()
    time_max = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()

    page_token = None
    resp = (
        service.events()
        .list(
            calendarId="primary",
            singleEvents=True,
            orderBy="startTime",
            timeZone=tz,
            timeMin=time_min,
            timeMax=time_max,
            pageToken=page_token,
            maxResults=2500,
        )
        .execute()
    )
    events = resp.get("items", [])
    return events


def getAllCanvasTasks(token: str):
    try:
        print("Fetching all courses...")
        all_courses = fetch_courses(token, CANVAS_URL)

        # Filter for Fall 2025
        fall_courses = [
            c
            for c in all_courses
            if c.get("term", {}).get("name", "").lower() == "fall 2025"
        ]

        if not fall_courses:
            print("No Fall 2025 courses found.")
            return

        allTasks = []
        print(f"Found {len(fall_courses)} Fall 2025 courses:")
        for course in fall_courses:
            name = course.get("name", "N/A")
            print(f"- {name}")

            tasks = fetch_assignments_for_course(
                token, CANVAS_URL, course["id"], weeks=2
            )
            print(f"  -> Found {len(tasks)} tasks")

            allTasks.extend(tasks)
        return allTasks

    except Exception as e:
        print(f"Error: {e}")


def fetch_courses(token: str, base_url: str):
    """
    Fetch all Canvas courses with term info.
    """
    headers = {"Authorization": f"Bearer {token}"}
    courses_url = f"{base_url}/api/v1/courses"
    params = {"include[]": "term", "per_page": 100}

    all_courses = []
    while courses_url:
        resp = requests.get(courses_url, headers=headers, params=params)
        resp.raise_for_status()
        all_courses.extend(resp.json())
        params = None
        courses_url = resp.links.get("next", {}).get("url")

    return all_courses


def fetch_assignments_for_course(
    token: str, base_url: str, course_id: int, weeks: int = 2
):
    """
    Fetch assignments for a course within a given time window.
    """
    headers = {"Authorization": f"Bearer {token}"}
    assignments_url = f"{base_url}/api/v1/courses/{course_id}/assignments"
    params = {"per_page": 100}

    resp = requests.get(assignments_url, headers=headers, params=params)
    resp.raise_for_status()
    assignments = resp.json()

    now = datetime.utcnow()
    end_window = now + timedelta(weeks=weeks)

    tasks = []
    for a in assignments:
        due_str = a.get("due_at")
        if not due_str:
            continue

        # Canvas returns UTC with trailing Z
        due_dt = datetime.strptime(due_str, "%Y-%m-%dT%H:%M:%SZ")
        if not (now <= due_dt <= end_window):
            continue

        task = {
            "userId": None,
            "title": a["name"],
            "description": a.get("description", ""),
            "startTime": None,
            "endTime": None,
            "dueDate": due_dt.strftime("%Y-%m-%dT%H:%M"),
            "estimatedMinutes": 60,
            "minutesTaken": 0,
            "source": "canvas",
            "status": "todo",
            "priority": "med",
        }
        tasks.append(task)

    return tasks


def normalize_canvas_task(raw: dict) -> dict:
    # Your incoming example:
    # {'userId': None, 'title': '...', 'description': '...', 'startTime': None, 'endTime': None,
    #  'dueDate': '2025-10-08T03:59', 'estimatedMinutes': 60, 'minutesTaken': 0,
    #  'isFlexible': True, 'source': 'canvas', 'status': 'todo', 'priority': 'med'}
    t = dict(raw)  # shallow copy
    t.pop("userId", None)  # userId is redundant in embedded array
    t["_id"] = ObjectId()  # embedded task id for client round-trips
    t.setdefault("source", "canvas")
    t.setdefault("status", "todo")
    t.setdefault("priority", "med")
    t.setdefault("estimatedMinutes", 60)
    t.setdefault("minutesTaken", 0)
    t["createdAt"] = now_iso()
    t["updatedAt"] = now_iso()
    return t


def upsert_canvas_tasks_embedded(users_col, oid, raw_tasks):
    if not raw_tasks:
        return
    ops = []
    now = now_iso()
    for rt in raw_tasks:
        t = normalize_canvas_task(rt)
        title = t.get("title")
        due = t.get("dueDate")
        # Try to update an existing task with same title + dueDate from Canvas
        ops.append(
            UpdateOne(
                {
                    "_id": oid,
                    "tasks": {
                        "$elemMatch": {
                            "source": "canvas",
                            "title": title,
                            "dueDate": due,
                        }
                    },
                },
                {
                    "$set": {
                        "tasks.$.description": t.get("description"),
                        "tasks.$.startTime": t.get("startTime"),
                        "tasks.$.endTime": t.get("endTime"),
                        "tasks.$.estimatedMinutes": t.get("estimatedMinutes"),
                        "tasks.$.minutesTaken": t.get("minutesTaken", 0),
                        "tasks.$.status": t.get("status", "todo"),
                        "tasks.$.priority": t.get("priority", "med"),
                        "tasks.$.updatedAt": now,
                    }
                },
            )
        )
        # If none matched, push a new one
        ops.append(
            UpdateOne(
                {
                    "_id": oid,
                    "tasks": {
                        "$not": {
                            "$elemMatch": {
                                "source": "canvas",
                                "title": title,
                                "dueDate": due,
                            }
                        }
                    },
                },
                {"$push": {"tasks": t}, "$set": {"updatedAt": now}},
            )
        )
    users_col.bulk_write(ops, ordered=False)


def classify_tasks_batch(tasks):
    """
    Sends a batch of tasks to Gemini for classification.
    Returns a dict {task_id: isFlexible}
    """
    task_list_str = "\n".join(
        [
            f"- ID: {str(t['_id'])}, Title: {t['title']}, Desc: {t.get('description', '')}"
            for t in tasks
        ]
    )

    prompt = f"""
    You are classifying tasks as flexible or non-flexible.

    - Flexible = can be rescheduled/moved (e.g., "Do homework", "Read chapter").
    - Non-flexible = fixed events (e.g., "Exam", "Lecture", "Meeting").

    Tasks:
    {task_list_str}

    Return ONLY valid JSON in this format:
    {{
      "results": [
        {{"id": "<task_id>", "isFlexible": true|false}}
      ]
    }}
    """

    response = ask_gemini(prompt)

    try:
        data = json.loads(response)
        return {item["id"]: item["isFlexible"] for item in data["results"]}
    except Exception as e:
        raise ValueError(f"AI response not valid JSON:\n{response}") from e


def run_batch_classification(users_col, userID):
    oid = ObjectId(userID)

    # 1) Get the user's tasks array
    doc = users_col.find_one({"_id": oid}, {"tasks": 1})
    if not doc or "tasks" not in doc:
        print("No tasks for user.")
        return

    # 2) Pick tasks missing isFlexible (optionally also source == 'canvas')
    pending = [t for t in (doc.get("tasks") or []) if "isFlexible" not in t]
    if not pending:
        print("No unclassified tasks.")
        return
    print(pending)

    # 3) Classify (whatever your classifier needs; here we pass the raw items)
    classification = classify_tasks_batch(
        pending
    )  # expected: { "<task_id_str>": True/False, ... }

    # 4) Bulk update embedded elements using positional $
    ops = []
    ts = now_iso()
    for t in pending:
        tid = t["_id"]  # ObjectId in embedded task
        key = str(tid)  # your classifier keyed by string
        is_flex = classification.get(key)
        if is_flex is None:
            continue
        ops.append(
            UpdateOne(
                {"_id": oid, "tasks._id": tid},
                {
                    "$set": {
                        "tasks.$.isFlexible": bool(is_flex),
                        "tasks.$.updatedAt": ts,
                    }
                },
            )
        )

    if ops:
        res = users_col.bulk_write(ops, ordered=False)
        print(f"updated: {res.modified_count}")
    else:
        print("Nothing to update.")
