from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("commands"))
async def commands(message: Message):
    await message.answer(
        "🏏 <b>CRICKET ARENA</b>\n"
        "<i>Command Center</i>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎮 <b>MATCHES</b>\n"
        "<code>/play [OVERS] [BALLS]</code>  — 1v1\n"
        "<code>/join</code>  — join a lobby\n"
        "<code>/solo [OVERS] [BALLS]</code>  — AI match\n"
        "<code>/custom OVERS [BALLS]</code>  — custom format\n"
        "<code>/score</code>  <code>/status</code>  <code>/cancel</code>\n\n"
        "👥 <b>TEAMS</b>\n"
        "<code>/teams</code>  <code>/team</code>  <code>/teamplay</code>  <code>/teamjoin</code>\n"
        "Captain tools: roster • players • roles • captaincy\n\n"
        "🏆 <b>COMPETITIONS</b>\n"
        "<code>/tournament</code>  <code>/league</code>\n\n"
        "👤 <b>CAREER</b>\n"
        "<code>/profile</code>  <code>/mystats</code>  <code>/stats</code>\n"
        "<code>/leaderboard</code>  <code>/history</code>  <code>/achievements</code>  <code>/daily</code>\n\n"
        "ℹ️ <b>UTILITY</b>\n"
        "<code>/rules</code>  <code>/ping</code>  <code>/id</code>  <code>/help</code>\n\n"
        "🎯 <b>FLOW</b>\n"
        "Bowler chooses privately → batter chooses in the group → ball resolves publicly.",
        parse_mode="HTML"
    )

@router.message(Command("ping"))
async def ping(message: Message):
    await message.answer("🟢 <b>CRICKET ARENA</b>  •  <i>Online</i>\n⚡ Match engine ready  •  Telegram live", parse_mode="HTML")

@router.message(Command("id"))
async def chat_id(message: Message):
    await message.answer(
        f"👤 User ID: <code>{message.from_user.id}</code>\n"
        f"💬 Chat ID: <code>{message.chat.id}</code>",
        parse_mode="HTML"
    )

@router.message(Command("rules"))
async def rules(message: Message):
    await message.answer(
        "🏏 <b>CRICKET RULES</b>\n\n"
        "1. Batter sends 1–6 in the group.\n"
        "2. Bowler chooses a numbered delivery privately.\n"
        "   1 Swing • 2 Yorker • 3 Bouncer • 4 Slower • 5 Inswing • 6 Outswing.\n"
        "3. The bowling number stays private.\n"
        "4. Same batter number + delivery number = wicket.\n"
        "5. Otherwise the batter's number is the runs scored.\n"
        "6. Overs are calculated automatically from legal balls.\n"
        "7. Results and score remain public in the group.\n"
        "8. Turn timeout is controlled by TURN_TIMEOUT in .env.",
        parse_mode="HTML"
    )
