from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()


def home_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🏏 PLAY", callback_data="home:play")
    kb.button(text="🤖 SOLO", callback_data="home:solo")
    kb.button(text="⚙️ CUSTOM", callback_data="home:custom")
    kb.button(text="👥 TEAMS", callback_data="home:teams")
    kb.button(text="🏆 TOURNAMENTS", callback_data="home:tournaments")
    kb.button(text="🏅 LEADERBOARD", callback_data="home:leaderboard")
    kb.button(text="👤 PROFILE", callback_data="home:profile")
    kb.button(text="📊 STATS", callback_data="home:stats")
    kb.button(text="🎁 DAILY REWARD", callback_data="home:daily")
    kb.button(text="💬 SUPPORT", url="https://t.me/arcchatz")
    kb.button(text="📢 UPDATES", url="https://t.me/arcupdates")
    kb.adjust(2, 2, 2, 2, 2, 2)
    return kb.as_markup()


async def send_home(message: Message, settings):
    name = message.from_user.first_name or "Player"
    caption = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🏏 <b>CRICKET ARENA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Welcome, <b>{name}</b> 👋\n\n"
        "⚡ <b>Fast • Private • Competitive</b>\n"
        "Play ball-by-ball cricket directly inside Telegram.\n\n"
        "🏏 1v1 Matches   🤖 Solo\n"
        "👥 Team Cricket   🏆 Competitions\n"
        "📊 Career Stats   🏅 Leaderboards\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 {settings.support_group}   •   📢 {settings.updates_channel}"
    )

    banner = "assets/start_banner.jpg"
    try:
        await message.answer_photo(
            FSInputFile(banner),
            caption=caption,
            reply_markup=home_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        await message.answer(caption, reply_markup=home_keyboard(), parse_mode="HTML")


@router.message(Command("start"))
async def start(message: Message, settings, admin):
    await admin.register_chat(
        message.chat.id,
        message.chat.type,
        getattr(message.chat, "title", None),
    )
    await send_home(message, settings)


@router.callback_query(F.data == "home:play")
async def home_play(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "🏏 <b>QUICK MATCH</b>\n\n"
        "<code>/play</code> — 2 overs × 6 balls\n"
        "<code>/play 1 3</code> — 1 over × 3 balls\n"
        "<code>/play 5 6</code> — 5 overs × 6 balls\n\n"
        "Create it in a group, then the opponent uses <code>/join</code>.",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "home:solo")
async def home_solo(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "🤖 <b>SOLO CRICKET</b>\n\n"
        "<code>/solo</code> — 2 overs × 6 balls\n"
        "<code>/solo 1 3</code> — 1 over × 3 balls\n"
        "<code>/solo 5 6</code> — 5 overs × 6 balls",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "home:custom")
async def home_custom(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "⚙️ <b>CUSTOM FORMAT</b>\n\n"
        "Use <code>/custom OVERS BALLS</code>\n\n"
        "Examples:\n"
        "• <code>/custom 1 3</code>\n"
        "• <code>/custom 2 6</code>\n"
        "• <code>/custom 10 6</code>\n\n"
        "Balls per over: 3, 4, 5 or 6.",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "home:tournaments")
async def home_tournaments(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "🏆 <b>COMPETITIONS</b>\n\n"
        "<code>/tournament list</code>\n"
        "<code>/league help</code>",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "home:profile")
async def home_profile(call: CallbackQuery, users):
    await call.answer()
    doc = await users.get(call.from_user.id)
    if not doc:
        await users.ensure(call.from_user)
        doc = await users.get(call.from_user.id)
    level = 1 + doc.get("xp", 0) // 500
    await call.message.answer(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>PLAYER PROFILE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏏 <b>{call.from_user.full_name}</b>\n"
        f"⭐ Level: <b>{level}</b>\n"
        f"🏆 Rating: <b>{doc.get('rating', 1000)}</b>\n"
        f"✨ XP: <b>{doc.get('xp', 0)}</b>\n"
        f"🪙 Coins: <b>{doc.get('coins', 0)}</b>\n\n"
        f"Matches: {doc.get('matches', 0)}\n"
        f"Wins: {doc.get('wins', 0)}  •  Losses: {doc.get('losses', 0)}\n"
        f"Runs: {doc.get('runs', 0)}  •  Wickets: {doc.get('wickets', 0)}\n"
        f"Fours: {doc.get('fours', 0)}  •  Sixes: {doc.get('sixes', 0)}",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "home:stats")
async def home_stats(call: CallbackQuery, users):
    await call.answer()
    doc = await users.get(call.from_user.id)
    if not doc:
        await users.ensure(call.from_user)
        doc = await users.get(call.from_user.id)
    await call.message.answer(
        "📊 <b>CAREER STATS</b>\n\n"
        f"🏏 Matches: <b>{doc.get('matches', 0)}</b>\n"
        f"🏆 Wins: <b>{doc.get('wins', 0)}</b>\n"
        f"❌ Losses: <b>{doc.get('losses', 0)}</b>\n"
        f"🏏 Runs: <b>{doc.get('runs', 0)}</b>\n"
        f"🎯 Wickets: <b>{doc.get('wickets', 0)}</b>\n"
        f"🔥 Fours: <b>{doc.get('fours', 0)}</b>\n"
        f"💥 Sixes: <b>{doc.get('sixes', 0)}</b>\n"
        f"⭐ Rating: <b>{doc.get('rating', 1000)}</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "home:leaderboard")
async def home_leaderboard(call: CallbackQuery, users):
    await call.answer()
    rows = await users.leaderboard("rating")
    lines = ["━━━━━━━━━━━━━━━━━━━━", "🏅 <b>TOP PLAYERS</b>", "━━━━━━━━━━━━━━━━━━━━", ""]
    medals = ["🥇", "🥈", "🥉"]
    for idx, row in enumerate(rows, 1):
        prefix = medals[idx - 1] if idx <= 3 else f"<b>{idx:02}</b>"
        lines.append(f"{prefix}  {row.get('name', 'Player')}  •  <b>{row.get('rating', 1000)}</b>")
    await call.message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "home:daily")
async def home_daily(call: CallbackQuery, users):
    await call.answer()
    await users.ensure(call.from_user)
    ok, reward = await users.daily(call.from_user.id)
    await call.message.answer(
        f"🎁 <b>DAILY REWARD</b>\n\nYou received <b>{reward} coins</b> + XP."
        if ok else
        "⏳ <b>ALREADY CLAIMED</b>\n\nCome back tomorrow for your next reward.",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "home:teams")
async def home_teams(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👥 <b>TEAM ARENA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<code>/team create NAME</code>\n"
        "<code>/team my</code>\n"
        "<code>/teams</code>\n"
        "<code>/team add USER_ID</code>\n"
        "<code>/team remove USER_ID</code>\n"
        "<code>/team captain USER_ID</code>\n"
        "<code>/team matchxi ID1 ID2 ID3 ID4 [ID5]</code>\n\n"
        "Team matches: <code>/teamplay TEAM 2 6</code>",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🏏 <b>HOW TO PLAY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>Bowler goes first.</b>\n"
        "1. Bowler chooses a private delivery (1–6).\n"
        "2. Striker receives the public batting card.\n"
        "3. Striker sends 1–6 in the group.\n"
        "4. Same number = wicket; otherwise the batting number is runs.\n\n"
        "⚙️ Format: <code>/play OVERS BALLS</code>\n"
        "Balls: 3 / 4 / 5 / 6\n\n"
        "👥 Team: <code>/teamplay TEAM OVERS BALLS</code>",
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cancel(message: Message, matches, db):
    match = matches.remove(message.chat.id)
    if match:
        await db.live_matches.delete_one({"chat_id": message.chat.id})
        await message.answer("🛑 <b>Match cancelled.</b>\nLive state cleared.", parse_mode="HTML")
    else:
        await message.answer("❌ No active match.")
