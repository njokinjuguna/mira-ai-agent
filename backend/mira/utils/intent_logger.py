import os
import json
from datetime import datetime

# Get the real project root
PROJECT_ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, "..", "..")))

# Define LOG_PATH to point inside MiraAIAgent/logs/
LOG_PATH = os.path.join(PROJECT_ROOT, "logs", "intent_logs.jsonl")


# Ensure logs/ folder exists
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

def log_intent_entry(query: str, intent: str, source: str = "classifier",lang: str = None):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "intent": intent,
        "source": source
    }
    if lang:
        entry["language"] = lang

    with open(LOG_PATH, "a", encoding="utf-8") as f:  # Append mode
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

