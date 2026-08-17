from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

def home_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🏏 PLAY CRICKET", callback_data="home:play")
    kb.button(text="🤖 SOLO", callback_data="home:solo")
    kb.button(text="⚙️ CUSTOM MATCH", callback_data="home:custom")
    kb.button(text="🏆 TOURNAMENTS", callback_data="home:tournaments")
    kb.button(text="👥 TEAMS", callback_data="home:teams")
    kb.button(text="👤 PROFILE", callback_data="home:profile")
    kb.button(text="📊 STATS", callback_data="home:stats")
    kb.button(text="🏅 LEADERBOARD", callback_data="home:leaderboard")
    kb.button(text="🎁 REWARDS", callback_data="home:daily")
    kb.button(text="💬 SUPPORT", url="https://t.me/arcchatz")
    kb.button(text="📢 UPDATES", url="https://t.me/arcupdates")
    kb.adjust(2, 1, 2, 2, 2, 2)
    return kb.as_markup()

async def send_home(message: Message, settings):
    name = message.from_user.first_name or "Player"
    caption = (
        f"🏏 <b>CRICKET ARENA</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 Welcome, <b>{name}</b>!\n\n"
        f"🎮 <b>Ready to play?</b>\n"
        f"Real-time Telegram cricket • Ball by ball\n\n"
        f"🔥 Quick matches  •  🤖 Solo  •  🏆 Tournaments\n"
        f"⭐ Ratings  •  📊 Career stats  •  🎁 Rewards\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💬 {settings.support_group}   •   📢 {settings.updates_channel}"
    )

    try:
        banner = FSInputFile("assets/start_banner.jpg")
        await message.answer_photo(
            banner,
            caption=caption,
            reply_markup=home_keyboard(),
        )
    except Exception:
        await message.answer(caption, reply_markup=home_keyboard(), parse_mode="HTML")

@router.message(Command("start"))
async def start(message: Message, settings, admin, users):
    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    await users.ensure(message.from_user)
    await send_home(message, settings)

@router.callback_query(F.data == "home:play")
async def home_play(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "🏏 <b>PLAY CRICKET</b>\n\n"
        "Create a match with /play\n"
        "Then let another player use /join.\n\n"
        "Or use /solo for AI.",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "home:solo")
async def home_solo(call: CallbackQuery, bot):
    await call.answer()
    await call.message.answer("🤖 Starting solo mode…")
    # User then invokes /solo; keeps game creation in one handler.
    await call.message.answer("Use <b>/solo</b> to start.", parse_mode="HTML")

@router.callback_query(F.data == "home:custom")
async def home_custom(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "⚙️ <b>CUSTOM MATCH</b>\n\n"
        "Choose your format:\n\n"
        "/custom 1 6\n"
        "/custom 2 6\n"
        "/custom 5 6\n"
        "/custom 10 6\n"
        "/custom 20 6\n\n"
        "Balls/over: 3, 4, 5 or 6",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "home:tournaments")
async def home_tournaments(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "🏆 <b>TOURNAMENTS</b>\n\n"
        "/tournament list\n"
        "/tournament create Cricket Cup 2",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "home:profile")
async def home_profile(call: CallbackQuery, users):
    await call.answer()
    doc = await users.get(call.from_user.id) or await users.ensure(call.from_user)
    if not doc:
        doc = await users.get(call.from_user.id)
    await call.message.answer(
        f"👤 <b>{call.from_user.full_name}</b>\n\n"
        f"⭐ Level: <b>{1 + doc.get('xp', 0) // 500}</b>\n"
        f"🏆 Rating: <b>{doc.get('rating', 1000)}</b>\n"
        f"✨ XP: <b>{doc.get('xp', 0)}</b>\n"
        f"🪙 Coins: <b>{doc.get('coins', 0)}</b>\n\n"
        f"Matches: {doc.get('matches', 0)}\n"
        f"Wins: {doc.get('wins', 0)} • Losses: {doc.get('losses', 0)}",
        parse_mode="HTML",
    )

@router.callback_query(F.data == "home:stats")
async def home_stats(call: CallbackQuery, users):
    await call.answer()
    doc = await users.get(call.from_user.id) or {}
    await call.message.answer(
        "📊 <b>CAREER STATS</b>\n\n"
        f"🏏 Matches: <b>{doc.get('matches', 0)}</b>\n"
        f"🏆 Wins: <b>{doc.get('wins', 0)}</b>\n"
        f"💔 Losses: <b>{doc.get('losses', 0)}</b>\n"
        f"🏏 Runs: <b>{doc.get('runs', 0)}</b>\n"
        f"🎯 Wickets: <b>{doc.get('wickets', 0)}</b>\n"
        f"💥 Sixes: <b>{doc.get('sixes', 0)}</b>",
        parse_mode="HTML",
    )

@router.callback_query(F.data == "home:leaderboard")
async def home_leaderboard(call: CallbackQuery, users):
    await call.answer()
    rows = await users.leaderboard("rating")
    lines = ["🏆 <b>LEADERBOARD — RATING</b>", ""]
    for idx, row in enumerate(rows, 1):
        lines.append(f"{idx}. {row.get('name', 'Player')} — <b>{row.get('rating', 0)}</b>")
    await call.message.answer("\n".join(lines), parse_mode="HTML")

@router.callback_query(F.data == "home:daily")
async def home_daily(call: CallbackQuery, users):
    await call.answer()
    await users.ensure(call.from_user)
    ok, reward = await users.daily(call.from_user.id)
    await call.message.answer(
        f"🎁 Daily reward claimed: <b>{reward} coins</b>!" if ok
        else "⏳ You already claimed today's reward.",
        parse_mode="HTML",
    )

@router.callback_query(F.data == "home:teams")
async def home_teams(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "👥 <b>TEAMS</b>\n\n"
        "Team management works inside groups.\n\n"
        "/team create NAME\n/team my\n/team roster NAME\n"
        "/team add USER_ID\n/team remove USER_ID\n/team captain USER_ID\n"
        "/team vice USER_ID\n/team leave\n/team disband",
        parse_mode="HTML"
    )

@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "🏏 <b>HOW TO PLAY</b>\n\n"
        "Create/join a match. When it is your turn, send a number from 1 to 6.\n"
        "The bowler chooses first in private DM, then the batter chooses in the group.\n\n"
        "Same number = wicket.\n"
        "Different number = batter scores their number.\n\n"
        "Commands: /play /join /solo /custom /profile /stats /leaderboard /team /league /tournament",
        parse_mode="HTML",
    )

@router.message(Command("cancel"))
async def cancel(message: Message, matches):
    match = matches.remove(message.chat.id)
    await message.answer("🛑 Match cancelled." if match else "❌ No active match.")
