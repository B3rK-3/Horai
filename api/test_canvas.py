import os
from dotenv import load_dotenv
from services.canvas_api import fetch_courses, fetch_assignments_for_course

load_dotenv()
CANVAS_TOKEN = os.getenv("CANVAS_TOKEN")
CANVAS_BASE_URL = os.getenv("CANVAS_BASE_URL")

def main():
    try:
        print("Fetching all courses...")
        all_courses = fetch_courses(CANVAS_TOKEN, CANVAS_BASE_URL)

        # Filter for Fall 2025
        fall_courses = [
            c for c in all_courses
            if c.get("term", {}).get("name", "").lower() == "fall 2025"
        ]

        if not fall_courses:
            print("No Fall 2025 courses found.")
            return

        print(f"Found {len(fall_courses)} Fall 2025 courses:")
        for course in fall_courses:
            name = course.get("name", "N/A")
            print(f"- {name}")

            tasks = fetch_assignments_for_course(CANVAS_TOKEN, CANVAS_BASE_URL, course["id"], weeks=2)
            print(f"  -> Found {len(tasks)} tasks")
            print(tasks)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()