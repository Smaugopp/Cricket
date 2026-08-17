from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bson import ObjectId

router = Router()

@router.message(Command("tournament"))
async def tournament(message: Message, tournaments):
    parts = (message.text or "").split(maxsplit=3)
    action = parts[1].lower() if len(parts) > 1 else "list"

    if action == "list":
        rows = await tournaments.c.find(
            {"status": "open", "chat_id": message.chat.id}
        ).sort("created_at", -1).limit(10).to_list(length=10)
        if not rows:
            await message.answer("🏆 No open tournaments in this chat.")
            return
        await message.answer(
            "🏆 <b>OPEN TOURNAMENTS</b>\n\n" +
            "\n".join(
                f"• <code>{r['_id']}</code> — {r['name']} ({r['overs']} overs) • {len(r.get('participants', []))}/16"
                for r in rows
            ), parse_mode="HTML")
        return

    if action == "create":
        name = parts[2] if len(parts) > 2 else "Cricket Cup"
        overs = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 2
        doc, err = await tournaments.create(message.chat.id, name, message.from_user.id, overs)
        await message.answer(
            f"🏆 <b>{doc['name']}</b> created.\n\n"
            f"ID: <code>{doc['_id']}</code>\n"
            f"Join: <code>/tournament join {doc['_id']}</code>",
            parse_mode="HTML") if doc else await message.answer("❌ "+err)
        return

    if len(parts) < 3:
        await message.answer(
            "/tournament list\n/tournament create NAME 2\n/tournament join ID\n"
            "/tournament start ID\n/tournament fixtures ID\n/tournament result ID MATCH_NUMBER HOME|AWAY\n"
        )
        return

    try:
        tid = ObjectId(parts[2])
    except Exception:
        await message.answer("❌ Invalid tournament ID."); return

    t = await tournaments.get(tid)
    if not t or t.get("chat_id") != message.chat.id:
        await message.answer("❌ Tournament not found in this chat."); return

    if action == "join":
        ok, text = await tournaments.join(t, message.from_user.id, message.from_user.full_name)
        await message.answer(("✅ " if ok else "❌ ")+text); return

    if action == "start":
        if t["owner"] != message.from_user.id:
            await message.answer("❌ Tournament owner only."); return
        ok, text = await tournaments.start(t)
        await message.answer(("🔥 " if ok else "❌ ")+text); return

    if action == "fixtures":
        current = await tournaments.current_round(t)
        if not current:
            await message.answer("🏆 Bracket not started."); return
        lines=[f"🏆 <b>ROUND {t.get('round', 1)}</b>",""]
        for idx,m in enumerate(current,1):
            home=m["home"]["name"] if m.get("home") else "BYE"
            away=m["away"]["name"] if m.get("away") else "BYE"
            status="✅" if m.get("played") else "🕒"
            lines.append(f"{idx}. {status} {home} vs {away}")
        if t.get("status") == "finished":
            lines += ["", f"👑 Champion: <b>{t['champion']['name']}</b>"]
        await message.answer("\n".join(lines), parse_mode="HTML"); return

    if action == "result":
        raw=(message.text or "").split()
        if len(raw) < 5 or not raw[3].isdigit():
            await message.answer("Usage: /tournament result ID MATCH_NUMBER HOME|AWAY"); return
        ok,text=await tournaments.record(t,int(raw[3])-1,raw[4].lower())
        await message.answer(("🏏 " if ok else "❌ ")+text); return

    await message.answer("Use /tournament fixtures ID for the current bracket.")
