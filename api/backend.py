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
from api.functions import (
    now_iso,
    hashStr,
    as_object_id,
    upsert_google_events_embedded,
    list_events_with_google_client,
    getAllCanvasTasks,
    upsert_canvas_tasks_embedded,
    ask_gemini,
    parse_ai_response,
)
# from bson import

# import geminiChat  # NOTE: THIS IS THE PYTHON FILE THAT HANDLES GEMINI COMMUNICATION

load_dotenv()

app = Flask(__name__)

CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:3000",
                "https://horai-dun.vercel.app",  # if you also call from this origin
            ]
        }
    },
    supports_credentials=True,  # needed if you use cookies or credentials: 'include'
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type"],
    max_age=86400,
)

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

mongo = MongoClient(MONGODB_URI)
db = mongo[DB_NAME]
users_col = db["users"]
"""
users {
  _id: ObjectId,
  email: string,
  hashedPass: string,
  google: {...},
  canvas: {...},
  createdAt: ISO8601,
  updatedAt: ISO8601,

  tasks: [  // embedded array
    {
      _id: ObjectId,            // per-task id you return to the client
      source: "manual|google|canvas|ai",
      externalId: "string|null",// e.g., Google event id for de-dupe
      title: string,
      description: string,
      startTime: ISO8601|null,
      endTime: ISO8601|null,
      dueDate: ISO8601|null,
      estimatedMinutes: number,
      minutesTaken: number,
      isFlexible: bool,
      status: "todo|in_progress|done",
      priority: "low|med|high",
      createdAt: ISO8601,
      updatedAt: ISO8601
    }
  ]
}

"""

# Ensure email uniqueness
try:
    users_col.create_index([("email", ASCENDING)], unique=True)
except Exception as e:
    print("Index creation warning:", e)


# ---------- Response helpers ----------
class RETURNS:
    class ERRORS:
        @staticmethod
        def bad_userID():
            return jsonify(
                {
                    "status": "ERROR",
                    "ERROR": "invalid_userID",
                    "message": "INVALID USERID",
                }
            ), 401

        @staticmethod
        def bad_email():
            return jsonify(
                {
                    "status": "ERROR",
                    "ERROR": "email_exists",
                    "message": "EMAIL NOT UNIQUE",
                }
            ), 409

        @staticmethod
        def bad_refresh_token():
            return jsonify(
                {
                    "status": "ERROR",
                    "ERROR": "invalid_refresh_token",
                    "message": "INVALID REFRESH TOKEN",
                }
            ), 401

        @staticmethod
        def bad_login():
            return jsonify(
                {
                    "status": "ERROR",
                    "message": "USER DOES NOT EXIST",
                    "ERROR": "no_such_user",
                }
            ), 401

        @staticmethod
        def internal_error():
            return jsonify(
                {
                    "status": "ERROR",
                    "message": "INTERNAL SERVER ERROR",
                    "ERROR": "internal_server_error",
                }
            ), 500

        @staticmethod
        def bad_request(msg="BAD REQUEST"):
            return jsonify(
                {"status": "ERROR", "message": msg, "ERROR": "bad_request"}
            ), 400

    class SUCCESS:
        @staticmethod
        def return_garment_id(garment_id: str):
            return jsonify(
                {
                    "status": "SUCCESS",
                    "message": "UPLOADED IMAGE SUCCESSFULLY RETURN IMAGE_ID",
                    "image_id": garment_id,
                }
            ), 201

        @staticmethod
        def return_jwt_refresh_tokens(jwtString: str, refreshToken: str):
            return jsonify(
                {
                    "status": "SUCCESS",
                    "refreshToken": refreshToken,
                    "jwt": jwtString,
                    "message": "RETURNED REFRESHTOKEN, JWT",
                }
            ), 201

        @staticmethod
        def return_jwt_token(jwtString: str):
            return jsonify(
                {"status": "SUCCESS", "jwt": jwtString, "message": "RETURNED JWT"}
            ), 201

        @staticmethod
        def return_garment_images(images: dict):
            return jsonify(
                {"status": "SUCCESS", "images": images, "message": "RETURNED IMAGES"}
            ), 201

        @staticmethod
        def return_chat_message(text: str):
            return jsonify(
                {
                    "status": "SUCCESS",
                    "chatMessage": text,
                    "message": "RETURNED CHATBOT MESSAGE",
                }
            ), 201

        @staticmethod
        def return_user_id(userID: str):
            return jsonify(
                {"status": "SUCCESS", "userID": userID, "message": "RETURNED USERID"}
            ), 201

        @staticmethod
        def return_tasks(tasks: list):
            return jsonify(
                {
                    "status": "SUCCES",
                    "tasks": tasks,
                    "message": "RETURNED ALL USER TASKS",
                }
            ), 200


# ---------- Routes ----------
TOKEN_URL = "https://oauth2.googleapis.com/token"


@app.route("/register", methods=["POST"])
def register():
    try:
        payload = request.get_json(force=True)
        email = payload.get("email")
        password = payload.get("password")

        if not email or not password:
            return RETURNS.ERRORS.bad_request("email and password are required")

        # If the user already exists, return bad_login
        if users_col.find_one({"email": email}):
            return RETURNS.ERRORS.bad_login()

        hashedPass = hashStr(password)
        now = now_iso()

        doc = {
            "email": email,
            "hashedPass": hashedPass,
            "google": {},  # start empty; will fill after Google auth
            "canvas": {"base_url": None, "access_token": None},
            "createdAt": now,
            "updatedAt": now,
        }

        res = users_col.insert_one(doc)
        return RETURNS.SUCCESS.return_user_id(str(res.inserted_id))

    except BaseException as error:
        print(error)
        return RETURNS.ERRORS.internal_error()


@app.route("/login", methods=["POST"])
def login():
    try:
        payload = request.get_json(force=True)
        email = payload.get("email")
        password = payload.get("password")

        if not email or not password:
            return RETURNS.ERRORS.bad_request("email and password are required")

        hashedPass = hashStr(password)

        # Authenticate user via MongoDB
        user = users_col.find_one(
            {"email": email, "hashedPass": hashedPass}, {"_id": 1}
        )
        if not user:
            return RETURNS.ERRORS.bad_login()

        userID = str(user["_id"])
        return RETURNS.SUCCESS.return_user_id(userID)

    except BaseException as error:
        print(error)
        return RETURNS.ERRORS.internal_error()


@app.route("/canvasToken", methods=["POST"])
def pushCanvasToken():
    try:
        payload = request.get_json(force=True)
        canvasToken = payload.get("canvasToken")
        userID = payload.get("userID")
        if not canvasToken or not userID:
            return RETURNS.ERRORS.bad_request("canvasToken and userID are required")

        oid = as_object_id(userID)
        if not oid:
            return RETURNS.ERRORS.bad_request("invalid userID")

        # Put the canvas token where userID matches
        res = users_col.update_one(
            {"_id": oid},
            {
                "$set": {
                    "canvas.access_token": canvasToken,
                    "updatedAt": now_iso(),
                }
            },
        )
        if res.matched_count == 0:
            return RETURNS.ERRORS.bad_login()  # user not found

        canvasTasks = getAllCanvasTasks(canvasToken)
        # for each task in canvasTasks push to the tasks inside users document
        upsert_canvas_tasks_embedded(users_col, oid, canvasTasks)

        return RETURNS.SUCCESS.return_user_id(userID)
    except BaseException as error:
        print(error)
        return RETURNS.ERRORS.internal_error()


# @app.route("/calendarToken", methods=["POST"])
# def pushCalendarToken():
#     try:
#         payload = request.get_json(force=True)
#         creds = payload.get("creds")
#         userID = payload.get("userID")
#         if not creds or not userID:
#             return RETURNS.ERRORS.bad_request("calendarToken and userID are required")

#         oid = as_object_id(userID)
#         if not oid:
#             return RETURNS.ERRORS.bad_request("invalid userID")

#         # Put the calendar token (Google) where userID matches
#         res = users_col.update_one(
#             {"_id": oid},
#             {
#                 "$set": {
#                     "google": creds,
#                     "updatedAt": now_iso(),
#                 }
#             },
#         )
#         if res.matched_count == 0:
#             return RETURNS.ERRORS.bad_login()

#         return RETURNS.SUCCESS.return_user_id(userID)
#     except BaseException as error:
#         print(error)
#         return RETURNS.ERRORS.internal_error()


@app.route("/getTasks", methods=["POST"])
def getTasks():
    try:
        payload = request.get_json(force=True)
        userID = payload.get("userID")
        if not userID:
            return RETURNS.ERRORS.bad_request("userID is required")
        try:
            uoid = ObjectId(userID)
        except Exception:
            return RETURNS.ERRORS.bad_userID()

        doc = users_col.find_one({"_id": uoid}, {"tasks": 1})
        if not doc:
            return RETURNS.ERRORS.bad_login()

        tasks = []
        for t in doc.get("tasks", []):
            tasks.append(
                {
                    "id": str(t["_id"]),
                    "title": t.get("title"),
                    "desc": t.get("description"),
                    "startTime": t.get("startTime"),
                    "endTime": t.get("endTime"),
                    "dueDate": t.get("dueDate"),
                    "priority": t.get("priority", "med"),
                }
            )

        return RETURNS.SUCCESS.return_tasks(tasks)

    except Exception as e:
        print(e)
        return RETURNS.ERRORS.internal_error()


@app.route("/calendarToken", methods=["POST"])
def auth_google():
    try:
        payload = request.get_json(force=True)
        code = payload["code"]
        userID = payload["userID"]

        # Exchange code for tokens (redirect_uri MUST be 'postmessage' for JS code flow)
        token_req = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": "postmessage",
            "grant_type": "authorization_code",
        }
        tr = requests.post(TOKEN_URL, data=token_req, timeout=10)
        tr.raise_for_status()
        tokens = tr.json()
        # tokens: access_token, expires_in, scope, token_type, id_token, (maybe) refresh_token

        access_token = tokens.get("access_token")
        refresh_token = tokens.get(
            "refresh_token"
        )  # may be None if not granted this time
        expires_in = tokens.get("expires_in")
        scope = tokens.get("scope")
        token_type = tokens.get("token_type")
        id_token = tokens.get("id_token")

        # Compute absolute expiry (ISO8601) if present
        expires_at = (
            (
                datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            ).isoformat()
            if expires_in
            else None
        )

        # Build update (skip None so we don’t overwrite an existing refresh_token with null)
        update_fields = {
            "google.access_token": access_token,
            "google.expires_at": expires_at,
            "google.scope": scope,
            "google.token_type": token_type,
            "google.id_token": id_token,
            "updatedAt": now_iso(),
        }
        if refresh_token:  # only set if provided
            update_fields["google.refresh_token"] = refresh_token

        # Persist to the matching user
        try:
            oid = ObjectId(userID)
        except Exception:
            return jsonify({"status": "ERROR", "message": "invalid userID"}), 400

        res = users_col.update_one({"_id": oid}, {"$set": update_fields})
        if res.matched_count == 0:
            return RETURNS.ERRORS.bad_login()  # user not found

        googleTasks = list_events_with_google_client(tokens)
        upsert_google_events_embedded(users_col, oid, googleTasks)

        return jsonify(
            {
                "status": "SUCCESS",
                "message": "GOOGLE TOKENS SAVED",
                "expiresAt": expires_at,
                "hasRefreshToken": bool(refresh_token),
            }
        ), 200

    except requests.HTTPError as e:
        # Helpful debugging during hackathon
        print(
            "Google token exchange failed:", e.response.text if e.response else str(e)
        )
        return jsonify(
            {"status": "ERROR", "message": "GOOGLE TOKEN EXCHANGE FAILED"}
        ), 400
    except Exception as e:
        print(e)
        return RETURNS.ERRORS.internal_error()


@app.route("/chat", methods=["POST"])
def chat():
    try:
        payload = request.get_json()
        conversation = payload["convo"]
        userID = payload["userID"]

        try:
            uoid = ObjectId(userID)
        except Exception:
            return RETURNS.ERRORS.bad_userID()

        doc = users_col.find_one({"_id": uoid}, {"tasks": 1})
        if not doc:
            return RETURNS.ERRORS.bad_login()

        tasks = []
        for t in doc.get("tasks", []):
            tasks.append(
                {
                    "id": str(t["_id"]),
                    "title": t.get("title"),
                    "desc": t.get("description"),
                    "startTime": t.get("startTime"),
                    "endTime": t.get("endTime"),
                    "dueDate": t.get("dueDate"),
                    "priority": t.get("priority", "med"),
                    "isFlexible": t.get("isFlexible")
                }
            )

        response = ask_gemini(conversation, tasks)

        print(response)
        if response.strip().startswith("```json"):
            aiResponse = parse_ai_response(response)
            intent = aiResponse["intent"]
            # ---------- INTENT: RESCHEDULE ----------
            if intent == "reschedule":
                # expects: {"intent":"reschedule","id":"<taskId>","startTime":"ISO","endTime":"ISO"}
                tid = as_object_id(aiResponse.get("id"))
                if not tid:
                    return RETURNS.ERRORS.bad_request("invalid task id")

                updates = {}
                if "startTime" in aiResponse:
                    updates["tasks.$.startTime"] = aiResponse["startTime"]
                if "endTime" in aiResponse:
                    updates["tasks.$.endTime"] = aiResponse["endTime"]
                if "dueDate" in aiResponse:
                    updates["tasks.$.dueDate"] = aiResponse["dueDate"]
                if not updates:
                    return RETURNS.ERRORS.bad_request("no schedule fields provided")

                updates["tasks.$.updatedAt"] = now_iso()

                res = users_col.update_one(
                    {"_id": uoid, "tasks._id": tid}, {"$set": updates}
                )
                if res.matched_count == 0:
                    return jsonify(
                        {"status": "ERROR", "message": "Task not found"}
                    ), 404

                # return updated list
                doc = users_col.find_one({"_id": uoid}, {"tasks": 1})
                return jsonify(
                    {"status": "SUCCESS"}
                ), 200

            # ---------- INTENT: ADD ----------
            elif intent == "add":
                # expects: {"intent":"add","title": "...", "desc":"...", "startTime":"ISO|null",
                #           "endTime":"ISO|null","dueDate":"ISO|null","priority":"low|med|high"}
                title = aiResponse.get("title") or "(Untitled)"
                desc = aiResponse.get("desc") or aiResponse.get("description") or ""
                start = aiResponse.get("startTime")
                end = aiResponse.get("endTime")
                due = aiResponse.get("dueDate") or end
                priority = (aiResponse.get("priority") or "med").lower()
                if priority not in {"low", "med", "high"}:
                    priority = "med"

                new_task = {
                    "_id": ObjectId(),
                    "source": "ai",
                    "externalId": None,
                    "title": title,
                    "description": desc,
                    "startTime": start,
                    "endTime": end,
                    "dueDate": due,
                    "estimatedMinutes": int(aiResponse.get("estimatedMinutes") or 60),
                    "minutesTaken": 0,
                    "isFlexible": bool(aiResponse.get("isFlexible"))
                    if "isFlexible" in aiResponse
                    else True,
                    "status": aiResponse.get("status") or "todo",
                    "priority": priority,
                    "createdAt": now_iso(),
                    "updatedAt": now_iso(),
                }

                users_col.update_one(
                    {"_id": uoid},
                    {"$push": {"tasks": new_task}, "$set": {"updatedAt": now_iso()}},
                )

                # return updated list (including the new task id)
                doc = users_col.find_one({"_id": uoid}, {"tasks": 1})
                return jsonify(
                    {"status": "SUCCESS"}
                ), 201

            # ---------- INTENT: REMOVE ----------
            elif intent == "remove":
                # expects: {"intent":"remove","id":"<taskId>"}
                tid = as_object_id(aiResponse.get("id"))
                if not tid:
                    return RETURNS.ERRORS.bad_request("invalid task id")

                res = users_col.update_one(
                    {"_id": uoid},
                    {
                        "$pull": {"tasks": {"_id": tid}},
                        "$set": {"updatedAt": now_iso()},
                    },
                )
                if res.modified_count == 0:
                    return jsonify(
                        {"status": "ERROR", "message": "Task not found"}
                    ), 404

                doc = users_col.find_one({"_id": uoid}, {"tasks": 1})
                return jsonify(
                    {"status": "SUCCESS"}
                ), 200
        else:
            return RETURNS.SUCCESS.return_chat_message(response)
    except Exception as e:
        print(e)
        return RETURNS.ERRORS.internal_error()

    except BaseException as error:
        print(error)
        return RETURNS.ERRORS.internal_error()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
