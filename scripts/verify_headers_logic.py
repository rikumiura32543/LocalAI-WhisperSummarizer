from app.services.ollama_service import OllamaService

def main():
    service = OllamaService()
    prompt = service._build_summary_prompt("test content", "meeting")
    
    expected_headers = [
        "議論内容", # "Agenda" in Japanese prompt might vary, checking logic
        "決定事項",
        "アクション", # "ToDo / Next Actions"
        "次回"
    ]
    # Check strict JSON keys in prompt
    json_keys = [
        '"summary"',
        '"details"',
        '"agenda"',
        '"decisions"',
        '"todo"',
        '"next_actions"',
        '"next_meeting"'
    ]
    
    print("Checking Summary Prompt Structure...")
    missing = []
    
    for key in json_keys:
        if key not in prompt:
            missing.append(key)
            
    if missing:
        print(f"FAIL: Missing expected JSON keys in prompt: {missing}")
        print("Prompt content:")
        print(prompt)
    else:
        print("PASS: Prompt contains all expected JSON keys for meeting headers.")

if __name__ == "__main__":
    main()
