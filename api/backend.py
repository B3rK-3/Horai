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
# from bson import

# import geminiChat  # NOTE: THIS IS THE PYTHON FILE THAT HANDLES GEMINI COMMUNICATION

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

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


def now_iso():
    # ISO8601 to seconds, with timezone Z
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


# ---------- Util ----------
def hashStr(text: str):
    """SHA-256 (consider bcrypt/argon2 for production)"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        "startTime": start_iso,
        "endTime": end_iso,
        "dueDate": end_iso,
        "estimatedMinutes": mins(start_iso, end_iso),
        "minutesTaken": 0,
        "isFlexible": False,
        "status": "todo",
        "priority": "med",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }


def upsert_google_events_embedded(user_oid, events):
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

    events = []
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

    events.extend(resp.get("items", []))

    return events


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

        # TODO: call canvas function to get events

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
            tasks.append({
                "id": str(t["_id"]),
                "title": t.get("title"),
                "desc": t.get("description"),
                "startTime": t.get("startTime"),
                "endTime": t.get("endTime"),
                "dueDate": t.get("dueDate"),
                "priority": t.get("priority", "med"),
            })

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
        upsert_google_events_embedded(oid, googleTasks)

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

        response = geminiChat.getConvoResponse(
            conversation
        )  # should give the chatbot the tasks

    except BaseException as error:
        print(error)
        return RETURNS.ERRORS.internal_error()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
