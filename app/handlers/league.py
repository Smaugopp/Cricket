from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router=Router()

@router.message(Command("league"))
async def league_cmd(message: Message, leagues, teams):
    if message.chat.type not in {"group","supergroup"}:
        await message.answer("🏆 Leagues are group-based."); return
    p=(message.text or "").split(maxsplit=3)
    action=p[1].lower() if len(p)>1 else "help"

    if action=="help":
        await message.answer(
            "🏆 <b>LEAGUE SYSTEM</b>\n\n"
            "/league create NAME\n"
            "/league info NAME\n"
            "/league join NAME TEAM_NAME\n"
            "/league start NAME\n"
            "/league table NAME\n"
            "/league fixtures NAME\n"
            "/league result NAME FIXTURE_INDEX HOME|AWAY|TIE\n",
            parse_mode="HTML"); return

    if action=="create":
        name=p[2] if len(p)>2 else "Cricket League"
        doc,err=await leagues.create(message.chat.id,name,message.from_user.id)
        await message.answer(
            f"🏆 <b>{doc['name']}</b> created." if doc else "❌ "+err,
            parse_mode="HTML"); return

    if len(p)<3:
        await message.answer("Usage: /league help"); return
    league=await leagues.get(message.chat.id,p[2])
    if not league:
        await message.answer("❌ League not found."); return

    if action=="info":
        await message.answer(
            f"🏆 <b>{league['name']}</b>\n\n"
            f"Status: <b>{league['status']}</b>\n"
            f"Teams: <b>{len(league.get('teams',[]))}</b>/16\n"
            f"Fixtures: <b>{len(league.get('fixtures',[]))}</b>",
            parse_mode="HTML"); return

    if action=="join":
        if len(p)<4:
            await message.answer("Usage: /league join NAME TEAM_NAME"); return
        team=await teams.get(message.chat.id,p[3])
        if not team:
            await message.answer("❌ Team not found."); return
        if team["captain"]!=message.from_user.id:
            await message.answer("❌ Team captain only."); return
        ok,text=await leagues.add_team(league,str(team["_id"]),team["name"])
        await message.answer(("✅ " if ok else "❌ ")+text); return

    if action=="start":
        if league["owner"]!=message.from_user.id:
            await message.answer("❌ League owner only."); return
        ok,text=await leagues.start(league)
        await message.answer(("🔥 " if ok else "❌ ")+text); return

    if action=="table":
        rows=await leagues.table(league)
        lines=["🏆 <b>LEAGUE TABLE</b>","", "TEAM                 P  W  L  T  PTS"]
        for r in rows:
            lines.append(f"{r['team'][:18]:18} {r['played']:2} {r['won']:2} {r['lost']:2} {r['tied']:2} {r['points']:3}")
        await message.answer("<pre>"+"\n".join(lines)+"</pre>",parse_mode="HTML"); return

    if action=="fixtures":
        lines=["📅 <b>FIXTURES</b>",""]
        names=league.get("team_names",{})
        for idx,f in enumerate(league.get("fixtures",[]),1):
            status="✅" if f.get("played") else "🕒"
            lines.append(f"{idx}. {status} {names.get(str(f['home']),f['home'])} vs {names.get(str(f['away']),f['away'])}")
        await message.answer("\n".join(lines) or "No fixtures.",parse_mode="HTML"); return

    if action=="result":
        if league["owner"]!=message.from_user.id:
            await message.answer("❌ League owner only."); return
        parts=(message.text or "").split()
        if len(parts)<5 or not parts[3].isdigit():
            await message.answer("Usage: /league result NAME FIXTURE_INDEX HOME|AWAY|TIE"); return
        idx=int(parts[3])-1; res=parts[4].lower()
        f=league.get("fixtures",[])[idx] if 0<=idx<len(league.get("fixtures",[])) else None
        if not f: await message.answer("❌ Fixture not found."); return
        winner=0 if res=="tie" else (f["home"] if res=="home" else f["away"] if res=="away" else None)
        if winner is None: await message.answer("Use HOME, AWAY or TIE."); return
        ok,text=await leagues.record_fixture(league,idx,winner)
        await message.answer(("✅ " if ok else "❌ ")+text)
        return

    await message.answer("Use /league help.")
