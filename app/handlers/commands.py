from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("commands"))
async def commands(message: Message):
    await message.answer(
        "🏏 <b>CRICKET ARENA — COMMAND CENTER</b>\n\n"
        "🎮 <b>PLAY</b>\n"
        "/play [OVERS] [BALLS] /join /solo [OVERS] [BALLS] /custom OVERS [BALLS] /score /status /cancel\n"
        "🎯 Bowler chooses first in DM • 🏏 Batter chooses second in group\n\n"
        "👥 <b>TEAMS</b>\n"
        "/teams /team create /team my /team roster /team add /team remove\n"
        "/team captain /team vice /team xi /team matchxi /team role /team leave /team disband\n\n"
        "🏆 <b>COMPETITIONS</b>\n"
        "/tournament /league\n\n"
        "👤 <b>CAREER</b>\n"
        "/profile /stats /history /achievements /daily /leaderboard\n\n"
        "ℹ️ <b>UTILITY</b>\n"
        "/id /rules /ping\n\n"
        "🛡 <b>STAFF</b>\n"
        "/admin /sudo /broadcast /maintenance",
        parse_mode="HTML"
    )

@router.message(Command("ping"))
async def ping(message: Message):
    await message.answer("🏏 <b>Cricket Arena</b> is online.", parse_mode="HTML")

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
