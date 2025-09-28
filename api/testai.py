from services.ai_service import ask_gemini, parse_ai_response

def main():
    # Step 1: Provide all tasks at once
    user_message = """
    I have these tasks:
    - Math Exam on 2025-10-01 from 10:00 to 12:00 (fixed, not movable)
    - CS Class every Monday and Wednesday from 9:00 to 10:30 (fixed, not movable)
    - Write English Essay, due 2025-10-02 at 23:59 (flexible, takes ~2 hours)
    - Study Math for 3 hours
    - Clean room, 1 hour, flexible
    - Gym workout, 1.5 hours, flexible
    Please optimize my week schedule.
    """

    response = ask_gemini(user_message)
    print("=== Gemini Response ===")
    print(response)

    try:
        parsed = parse_ai_response(response)
        print("=== Parsed AI Response ===")
        print(parsed)
    except Exception as e:
        print("Error parsing response:", e)

if __name__ == "__main__":
    main()
