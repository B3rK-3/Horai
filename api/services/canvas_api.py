import requests
from datetime import datetime, timedelta

def fetch_canvas_tasks(token: str, base_url: str, window_weeks: int = 2, course_name_filter: str = None):
    """
    Fetch assignments from Canvas and convert to tasks.

    Args:
        token: Canvas API access token
        base_url: Canvas instance URL, e.g., https://canvas.instructure.com
        window_weeks: How many weeks ahead to fetch assignments

    Returns:
        List of task dicts matching your tasks schema.
    """
    headers = {"Authorization": f"Bearer {token}"}
    tasks = []

    # Calculate time window
    now = datetime.utcnow()
    end_window = now + timedelta(weeks=window_weeks)

    try:
        # Fetch courses
        
        courses_url = f"{base_url}/api/v1/courses"
        params = {"enrollment_state[]": ["active", "future"]}
        resp = requests.get(courses_url, headers=headers, params=params)
        resp.raise_for_status()
        courses = resp.json()

        for course in courses:
            course_name = course.get("name", "")
            if course_name_filter and course_name_filter not in course_name:
                continue
            course_id = course["id"]
            # Fetch assignments for course
            assignments_url = f"{base_url}/api/v1/courses/{course_id}/assignments"
            params = {"per_page": 100}
            resp = requests.get(assignments_url, headers=headers, params=params)
            resp.raise_for_status()
            assignments = resp.json()

            for a in assignments:
                due_str = a.get("due_at")
                if not due_str:
                    continue

                # Canvas API due_at is UTC, ISO8601 with Z
                due_dt = datetime.strptime(due_str, "%Y-%m-%dT%H:%M:%SZ")
                
                # Only include tasks that are due in the future and within the window
                if not (now <= due_dt <= end_window):
                    continue

                task = {
                    "userId": None,  # fill when inserting into DB
                    "title": a["name"],
                    "description": a.get("description", ""),
                    "startTime": None,
                    "endTime": None,
                    "dueDate": due_dt.strftime("%Y-%m-%dT%H:%M"),
                    "estimatedMinutes": 60,  # default
                    "minutesTaken": 0,
                    "isFlexible": True,
                    "source": "canvas",
                    "status": "todo",
                    "priority": "med",
                    "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M"),
                    "updatedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M")
                }
                tasks.append(task)

    except requests.HTTPError as e:
        raise ValueError(f"Canvas API error: {e.response.status_code} - {e.response.text}")
    except requests.RequestException as e:
        raise ValueError(f"Canvas request failed: {str(e)}")

    return tasks