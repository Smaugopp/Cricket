from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

def avg(doc, a, b):
    return round(doc.get(a, 0) / b, 2) if b else 0

@router.message(Command("profile"))
@router.message(Command("stats"))
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
    rows = await users.leaderboard(field)
    lines = [f"🏆 <b>LEADERBOARD — {field.upper()}</b>", ""]
    for idx, row in enumerate(rows, 1):
        lines.append(f"{idx}. {row.get('name','Player')} — <b>{row.get(field,0)}</b>")
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
