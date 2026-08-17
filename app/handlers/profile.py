from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

def avg(doc, a, b):
    return round(doc.get(a, 0) / b, 2) if b else 0


@router.message(Command("stats"))
async def bot_stats(message: Message, settings, db, users):
    if message.from_user.id != settings.owner_id:
        doc = await users.get(message.from_user.id)
        if not doc:
            await users.ensure(message.from_user)
            doc = await users.get(message.from_user.id)
        await message.answer(
            "📊 <b>YOUR STATS</b>\n\n"
            f"🏏 Matches: <b>{doc.get('matches', 0)}</b>\n"
            f"🏆 Wins: <b>{doc.get('wins', 0)}</b>\n"
            f"💔 Losses: <b>{doc.get('losses', 0)}</b>\n"
            f"🏏 Runs: <b>{doc.get('runs', 0)}</b>\n"
            f"🎯 Wickets: <b>{doc.get('wickets', 0)}</b>\n"
            f"💥 Sixes: <b>{doc.get('sixes', 0)}</b>",
            parse_mode="HTML",
        )
        return

    users_count = await db.users.count_documents({})
    group_count = await db.chats.count_documents({"chat_type": {"$in": ["group", "supergroup"]}})
    private_count = await db.chats.count_documents({"chat_type": "private"})
    live_count = await db.live_matches.count_documents({})
    teams_count = await db.teams.count_documents({})
    matches_count = await db.matches.count_documents({})
    await message.answer(
        "📡 <b>CRICKET ARENA • OWNER DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Users:</b> {users_count:,}\n"
        f"👥 <b>Groups:</b> {group_count:,}\n"
        f"💬 <b>Private chats:</b> {private_count:,}\n"
        f"🏏 <b>Total matches:</b> {matches_count:,}\n"
        f"🔴 <b>Live matches:</b> {live_count:,}\n"
        f"👥 <b>Teams:</b> {teams_count:,}\n",
        parse_mode="HTML",
    )

@router.message(Command("profile"))
@router.message(Command("mystats"))
async def profile(message: Message, users):
    doc = await users.get(message.from_user.id)
    if not doc:
        await users.ensure(message.from_user)
        doc = await users.get(message.from_user.id)

    level = 1 + doc.get("xp", 0) // 500

    await message.answer(
        f"🏏 <b>{message.from_user.full_name}</b>\n\n"
        f"⭐ Level: <b>{level}</b>\n"
        f"🏆 Rating: <b>{doc.get('rating',1000)}</b>\n"
        f"✨ XP: <b>{doc.get('xp',0)}</b>\n"
        f"🪙 Coins: <b>{doc.get('coins',0)}</b>\n\n"
        f"Matches: {doc.get('matches',0)}\n"
        f"Wins: {doc.get('wins',0)}\n"
        f"Losses: {doc.get('losses',0)}\n"
        f"Ties: {doc.get('ties',0)}\n"
        f"Runs: {doc.get('runs',0)}\n"
        f"Wickets: {doc.get('wickets',0)}\n"
        f"Fours: {doc.get('fours',0)}\n"
        f"Sixes: {doc.get('sixes',0)}\n"
        f"Win Streak: {doc.get('streak',0)}\n"
        f"Best Streak: {doc.get('best_streak',0)}",
        parse_mode="HTML",
    )

@router.message(Command("daily"))
async def daily(message: Message, users):
    await users.ensure(message.from_user)
    ok, reward = await users.daily(message.from_user.id)
    await message.answer(
        f"🎁 Daily reward claimed: <b>{reward} coins</b>!"
        if ok else
        "⏳ You already claimed today's reward.",
        parse_mode="HTML"
    )

@router.message(Command("achievements"))
async def achievements(message: Message, users):
    doc = await users.get(message.from_user.id)
    keys = doc.get("achievements", []) if doc else []
    names = {
        "first_win": "🏆 First Win",
        "ten_wins": "🔥 10 Wins",
        "century": "💯 Century",
        "hat_trick": "🎩 Hat-trick",
        "six_machine": "💥 Six Machine",
    }
    text = "\n".join(names.get(x, x) for x in keys) or "No achievements yet."
    await message.answer("🏅 <b>ACHIEVEMENTS</b>\n\n" + text, parse_mode="HTML")

@router.message(Command("leaderboard"))
async def leaderboard(message: Message, users):
    field = "rating"
    parts = (message.text or "").split()
    aliases = {"rating":"rating","wins":"wins","runs":"runs","wickets":"wickets","xp":"xp","sixes":"sixes"}
    if len(parts) > 1 and parts[1].lower() in aliases:
        field = aliases[parts[1].lower()]
    rows = await users.leaderboard(field, limit=10)
    if not rows:
        await message.answer("🏆 <b>LEADERBOARD</b>\n\nNo players yet.", parse_mode="HTML")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        "🏆 <b>CRICKET ARENA LEADERBOARD</b>",
        f"<i>Top 10 by {field.title()}</i>",
        "",
    ]
    for idx, row in enumerate(rows, 1):
        icon = medals[idx - 1] if idx <= 3 else f"{idx}."
        lines.append(f"{icon} <b>{row.get('name', 'Player')}</b> — {row.get(field, 0)}")
    await message.answer("\n".join(lines), parse_mode="HTML")

@router.message(Command("history"))
async def history(message: Message, db):
    rows = await db.matches.find(
        {"players": message.from_user.id}
    ).sort("created_at", -1).limit(10).to_list(length=10)
    if not rows:
        await message.answer("📜 No match history yet.")
        return
    text = ["📜 <b>RECENT MATCHES</b>", ""]
    for r in rows:
        text.append(f"🏏 Winner: {r.get('winner')} • Score: {r.get('first_score',0)}")
    await message.answer("\n".join(text), parse_mode="HTML")
