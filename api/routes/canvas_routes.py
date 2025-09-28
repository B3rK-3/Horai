from flask import Blueprint, request, jsonify
from services.canvas_api import fetch_canvas_tasks
from bson import ObjectId

canvas_bp = Blueprint("canvas", __name__)

@canvas_bp.route("/canvas/import", methods=["POST"])
def import_canvas():
    data = request.json
    token = data.get("token")
    base_url = data.get("baseUrl")
    window_weeks = data.get("windowWeeks", 2)

    if not token or not base_url:
        return jsonify({"error": "Missing token or baseUrl"}), 400

    try:
        tasks = fetch_canvas_tasks(token, base_url, window_weeks)
        # Example: attach userId here if you have current_user_id from JWT
        # for t in tasks: t["userId"] = ObjectId(current_user_id)
        return jsonify(tasks)
    except ValueError as e:
        return jsonify({"error": str(e)}), 500