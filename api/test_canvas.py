import os
import requests
from dotenv import load_dotenv

load_dotenv()
CANVAS_TOKEN = os.getenv("CANVAS_TOKEN")
CANVAS_BASE_URL = os.getenv("CANVAS_BASE_URL")

def main():
    try:
        print("Fetching courses from Canvas...")
        headers = {"Authorization": f"Bearer {CANVAS_TOKEN}"}
        
        all_courses = []
        courses_url = f"{CANVAS_BASE_URL}/api/v1/courses"
        # Ask for term info and set a higher per_page limit for efficiency
        params = {"include[]": "term", "per_page": 100}

        while courses_url:
            resp = requests.get(courses_url, headers=headers, params=params)
            resp.raise_for_status()
            all_courses.extend(resp.json())
            
            # After the first request, params are included in the 'next' URL, so we clear them
            params = None

            if 'next' in resp.links:
                courses_url = resp.links['next']['url']
            else:
                courses_url = None

        if not all_courses:
            print("No courses found.")
            return

        print(f"\nFound a total of {len(all_courses)} courses:")
        for course in all_courses:
            course_name = course.get('name', 'N/A')
            term_name = course.get('term', {}).get('name', 'N/A')
            print(f"- Name: {course_name} (Term: {term_name})")

    except Exception as e:
        print(f"Error fetching Canvas courses: {e}")

if __name__ == "__main__":
    main()