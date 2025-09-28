from services.ai_service import ask_gemini, parse_ai_response

def main():
    user_message = "Add a tasks to Study Math tomorrow at 3pm for 1.5 hours"
    response = ask_gemini(user_message)
    print("=== Gemini Response ===")
    print(response)
    parsed = parse_ai_response(response)
    print("=== Parsed AI Response ===")
    print(parsed)
    

if __name__ == "__main__":
    main()