from app.services.ollama_service import OllamaService

def main():
    service = OllamaService()
    
    # Mock data structure matching the new requirements
    data = {
        "summary": "This is a summary.",
        "details": {
            "summary": "Detailed summary.",
            "agenda": ["Topic A", "Topic B"],
            "decisions": ["Decision 1"],
            "todo": ["Task 1"],
            "next_actions": ["Action 1"],
            "next_meeting": "Next Week"
        }
    }
    
    # Test formatting
    formatted = service._format_summary(data, "meeting")
    
    print("Checking Markdown Formatting...")
    print(f"Generated Markdown:\n{formatted}\n")
    
    checks = [
        "# 要約",
        "## 議題・議論内容",
        "- Topic A",
        "## 決定事項",
        "- Decision 1",
        "## ToDo",
        "- [ ] Task 1",
        "## 次のアクション",
        "- Action 1",
        "## 次回会議",
        "Next Week"
    ]
    
    failed = []
    for check in checks:
        if check not in formatted:
            failed.append(check)
            
    if failed:
        print(f"FAIL: Missing markdown elements: {failed}")
    else:
        print("PASS: Markdown formatting contains all expected elements.")

if __name__ == "__main__":
    main()
