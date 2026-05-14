import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "data" / "logs"
CONVERSATION_LOG_DIR = LOG_DIR / "conversations"

LOG_DIR.mkdir(parents=True, exist_ok=True)
CONVERSATION_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _daily_log_path():
    return LOG_DIR / f"agent_events_{datetime.now().strftime('%Y%m%d')}.jsonl"


def _conversation_log_path(conversation_id):
    safe_id = str(conversation_id or "unknown").replace("/", "_").replace("\\", "_")
    return CONVERSATION_LOG_DIR / f"{safe_id}.jsonl"


def _safe_json(value):
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return str(value)


def _clip(value, limit=2000):
    if value is None:
        return None
    safe_value = _safe_json(value)
    text = safe_value if isinstance(safe_value, str) else json.dumps(safe_value, ensure_ascii=False)
    if len(text) <= limit:
        return safe_value
    return text[:limit] + "\n...[log truncated]"


def log_event(conversation_id, event_type, **payload):
    event = {
        "time": _now_text(),
        "conversation_id": conversation_id,
        "event_type": event_type,
    }
    for key, value in payload.items():
        event[key] = _clip(value)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        CONVERSATION_LOG_DIR.mkdir(parents=True, exist_ok=True)

        line = json.dumps(event, ensure_ascii=False) + "\n"
        _daily_log_path().open("a", encoding="utf-8").write(line)
        _conversation_log_path(conversation_id).open("a", encoding="utf-8").write(line)
    except OSError:
        pass

    return event


def read_events(conversation_id=None, limit=200):
    path = _conversation_log_path(conversation_id) if conversation_id else _daily_log_path()
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    items = []
    for line in lines[-limit:]:
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items
