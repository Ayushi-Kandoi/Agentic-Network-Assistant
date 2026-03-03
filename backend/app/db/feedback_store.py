import json
from pathlib import Path
from datetime import datetime

FEEDBACK_FILE = Path("feedback_data.json")

def save_feedback(feedback: dict):
    record = {
        **feedback,
        "timestamp": datetime.utcnow().isoformat()
    }

    if FEEDBACK_FILE.exists():
        data = json.loads(FEEDBACK_FILE.read_text())
    else:
        data = []

    data.append(record)

    FEEDBACK_FILE.write_text(json.dumps(data, indent=2))