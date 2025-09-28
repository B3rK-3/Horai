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
from functions import (
    now_iso,
    hashStr,
    as_object_id,
    upsert_google_events_embedded,
    list_events_with_google_client,
    getAllCanvasTasks,
    upsert_canvas_tasks_embedded,
    ask_gemini,
)



MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

mongo = MongoClient(MONGODB_URI)
db = mongo[DB_NAME]
users_col = db["users"]
doc = users_col.find_one({"_id": as_object_id("68d88841c740ba7296bf10cd")}, {"tasks": 1})

tasks = []
for t in doc.get("tasks", []):
    tasks.append(
        {
            "id": str(t["_id"]),
            "title": t.get("title"),
            # "desc": t.get("description"),
            "startTime": t.get("startTime"),
            "endTime": t.get("endTime"),
            "dueDate": t.get("dueDate"),
            "priority": t.get("priority", "med"),
        }
    )
print(tasks)
res = ask_gemini([{"role": 'user', "parts": ["add another hackathon to next week"]}], tasks)
print(res)

