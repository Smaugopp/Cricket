import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    bot_token: str
    mongo_uri: str
    mongo_db: str
    owner_id: int
    support_group: str
    updates_channel: str
    turn_timeout: int

def get_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    mongo_uri = os.getenv("MONGO_URI", "").strip()

    if not token:
        raise RuntimeError("BOT_TOKEN is missing in .env")
    if not mongo_uri or "PUT_YOUR_MONGODB_ATLAS_URI_HERE" in mongo_uri:
        raise RuntimeError("MONGO_URI is missing in .env")

    return Settings(
        bot_token=token,
        mongo_uri=mongo_uri,
        mongo_db=os.getenv("MONGO_DB", "cricket_bot"),
        owner_id=int(os.getenv("OWNER_ID", "723206473")),
        support_group=os.getenv("SUPPORT_GROUP", "@arcchatz"),
        updates_channel=os.getenv("UPDATES_CHANNEL", "@arcupdates"),
        turn_timeout=int(os.getenv("TURN_TIMEOUT", "90")),
    )
