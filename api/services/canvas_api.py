import requests
from datetime import datetime, timedelta

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

def fetch_assignments_for_course(token: str, base_url: str, course_id: int, weeks: int = 2):
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
            "isFlexible": True,
            "source": "canvas",
            "status": "todo",
            "priority": "med",
        }
        tasks.append(task)

    return tasks