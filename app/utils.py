from datetime import datetime, timezone
from html import escape

def now():
    return datetime.now(timezone.utc)

def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{escape(name)}</a>'

def safe_name(name: str) -> str:
    return escape(name or "Player")

def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i+size]
