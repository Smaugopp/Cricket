from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("commands"))
async def commands(message: Message):
    await message.answer(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🏏 <b>CRICKET ARENA</b>\n"
        "COMMAND CENTER\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎮 <b>MATCHES</b>\n"
        "/play [overs] [balls]\n"
        "/join\n"
        "/solo [overs] [balls]\n"
        "/custom [overs] [balls]\n"
        "/score  /status  /cancel\n\n"
        "👥 <b>TEAMS</b>\n"
        "/teams\n"
        "/team create NAME\n"
        "/team my /team roster NAME\n"
        "/team add USER_ID /team remove USER_ID\n"
        "/team captain USER_ID /team vice USER_ID\n"
        "/team matchxi ID1 ID2 ID3 ID4 [ID5]\n"
        "/teamplay TEAM [overs] [balls]\n"
        "/teamjoin TEAM\n\n"
        "🏆 <b>CAREER</b>\n"
        "/profile /stats /history /achievements\n"
        "/leaderboard [rating|wins|runs|wickets|xp|sixes]\n"
        "/daily\n\n"
        "🏆 <b>COMPETITIONS</b>\n"
        "/tournament /league\n\n"
        "ℹ️ <b>UTILITY</b>\n"
        "/help /rules /ping /id",
        parse_mode="HTML",
    )


@router.message(Command("ping"))
async def ping(message: Message):
    await message.answer("🏏 <b>CRICKET ARENA</b> • ONLINE", parse_mode="HTML")


@router.message(Command("id"))
async def chat_id(message: Message):
    await message.answer(
        f"👤 User ID: <code>{message.from_user.id}</code>\n"
        f"💬 Chat ID: <code>{message.chat.id}</code>",
        parse_mode="HTML",
    )


@router.message(Command("rules"))
async def rules(message: Message):
    await message.answer(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🏏 <b>CRICKET RULES</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>1. BOWLER FIRST</b>\n"
        "The bowler privately chooses a delivery from 1–6.\n\n"
        "🏏 <b>2. BATTER SECOND</b>\n"
        "The striker then sends a shot number 1–6 in the group.\n\n"
        "🎯 <b>3. RESULT</b>\n"
        "Same number = wicket.\n"
        "Different number = batter's number is scored as runs.\n\n"
        "👥 <b>4. TEAM CRICKET</b>\n"
        "Wicket brings the next batter; the same bowler continues.\n"
        "At the end of an over, the bowler rotates automatically.\n\n"
        "⚙️ <b>5. FORMAT</b>\n"
        "3–6 legal balls per over are supported.",
        parse_mode="HTML",
    )
