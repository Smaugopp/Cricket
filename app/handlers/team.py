from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

def is_group(message):
    return message.chat.type in {"group", "supergroup"}

HELP = (
    "🏏 <b>TEAM COMMANDS</b>\n\n"
    "/team create NAME — create a squad\n"
    "/team my — your squad\n"
    "/team list — teams in this group\n"
    "/team info NAME — squad info\n"
    "/team roster NAME — full roster\n"
    "/team add USER_ID — captain adds player\n"
    "/team remove USER_ID — captain removes player\n"
    "/team captain USER_ID — transfer captaincy\n"
    "/team vice USER_ID — set vice-captain\n"
    "/team leave — leave squad\n"
    "/team disband — captain-only\n/team xi — view Playing XI\n/team xi set ID1 ID2 ... ID11 — captain sets XI\n/team xi clear — captain clears XI\n/team role USER_ID batter|bowler|all_rounder|keeper\n"
)

@router.message(Command("teams"))
async def teams_list(message: Message, teams):
    if not is_group(message):
        await message.answer("👥 Team management works inside groups.")
        return
    rows = await teams.list(message.chat.id)
    if not rows:
        await message.answer("🏏 No teams yet. Use /team create NAME")
        return
    await message.answer(
        "🏏 <b>GROUP TEAMS</b>\n\n" +
        "\n".join(f"• <b>{t['name']}</b> — {len(t.get('players', []))} players" for t in rows),
        parse_mode="HTML"
    )

@router.message(Command("team"))
async def team_cmd(message: Message, teams, users):
    if not is_group(message):
        await message.answer("👥 Team management works inside groups.")
        return
    await users.ensure(message.from_user)
    parts = (message.text or "").split(maxsplit=2)
    action = parts[1].lower() if len(parts) > 1 else "help"

    if action == "help":
        await message.answer(HELP, parse_mode="HTML"); return

    if action == "create":
        if len(parts) < 3:
            await message.answer("Usage: /team create Team Name"); return
        if await teams.my_team(message.chat.id, message.from_user.id):
            await message.answer("❌ You are already in a team in this group."); return
        doc, err = await teams.create(message.chat.id, parts[2], message.from_user.id, message.from_user.full_name)
        if not doc:
            await message.answer("❌ " + err); return
        await message.answer(
            f"👑 <b>{doc['name']}</b> created.\nYou are the captain.\n\n"
            "Add players with <code>/team add USER_ID</code>.",
            parse_mode="HTML"
        ); return

    if action == "list":
        rows = await teams.list(message.chat.id)
        await message.answer(
            "🏏 <b>TEAMS</b>\n\n" +
            ("\n".join(f"• <b>{t['name']}</b> — {len(t.get('players', []))}" for t in rows) or "No teams."),
            parse_mode="HTML"
        ); return

    if action in {"my", "info", "roster"}:
        team = await teams.my_team(message.chat.id, message.from_user.id) if action == "my" else None
        if team is None:
            if len(parts) < 3:
                await message.answer(f"Usage: /team {action} TEAM_NAME"); return
            team = await teams.get(message.chat.id, parts[2])
        if not team:
            await message.answer("❌ Team not found."); return
        names = team.get("player_names", {})
        lines = [
            f"🏏 <b>{team['name']}</b>", "",
            f"👑 Captain: {names.get(str(team['captain']), team['captain'])}",
            f"⭐ Vice-captain: {names.get(str(team['vice_captain']), team['vice_captain']) if team.get('vice_captain') else '—'}",
            f"👥 Squad: <b>{len(team.get('players', []))}</b>", ""
        ]
        for n, uid in enumerate(team.get("players", []), 1):
            role = " 👑" if uid == team["captain"] else (" ⭐" if uid == team.get("vice_captain") else "")
            lines.append(f"{n}. {names.get(str(uid), str(uid))}{role}")
        await message.answer("\n".join(lines), parse_mode="HTML"); return

    if action in {"add", "remove", "captain", "vice"}:
        team = await teams.my_team(message.chat.id, message.from_user.id)
        if not team or team["captain"] != message.from_user.id:
            await message.answer("❌ Captain only."); return
        target = message.reply_to_message.from_user if message.reply_to_message else None
        if target:
            uid = target.id
            target_name = target.full_name
        elif len(parts) >= 3 and parts[2].isdigit():
            uid = int(parts[2])
            target_name = None
        else:
            await message.answer(
                f"Reply to the player's message or use: /team {action} USER_ID"
            )
            return
        if action == "add":
            user = await users.get(uid)
            if not user:
                await message.answer("❌ Player must use /start with the bot first."); return
            ok, text = await teams.add_player(
                team, uid, target_name or user.get("name", str(uid))
            )
        elif action == "remove":
            ok, text = await teams.remove_player(team, uid)
        elif action == "captain":
            ok, text = await teams.transfer_captain(team, uid)
        else:
            ok, text = await teams.set_vice_captain(team, uid)
        await message.answer(("✅ " if ok else "❌ ") + text); return

    if action == "leave":
        team = await teams.my_team(message.chat.id, message.from_user.id)
        if not team:
            await message.answer("❌ You are not in a team."); return
        ok, text = await teams.leave(team, message.from_user.id)
        await message.answer(("✅ " if ok else "❌ ") + text); return

    if action == "disband":
        team = await teams.my_team(message.chat.id, message.from_user.id)
        if not team or team["captain"] != message.from_user.id:
            await message.answer("❌ Captain only."); return
        await teams.disband(team)
        await message.answer(f"🗑 <b>{team['name']}</b> disbanded.", parse_mode="HTML"); return


    if action == "xi":
        # Backward-compatible alias: this bot uses a 4/5-player match lineup.
        team = await teams.my_team(message.chat.id, message.from_user.id)
        if not team:
            await message.answer("❌ You are not in a team.")
            return
        sub = parts[2].lower() if len(parts) > 2 else "view"
        if sub == "view":
            roster = await teams.match_roster(team)
            if not roster:
                await message.answer(
                    "📋 Match players are not set. Captain: "
                    "/team players ID1 ID2 ID3 ID4 [ID5]"
                )
                return
            await message.answer(
                "🏏 <b>MATCH PLAYERS</b>\n\n" +
                "\n".join(
                    f"{n}. {x['name']}" for n, x in enumerate(roster, 1)
                ),
                parse_mode="HTML",
            )
            return
        if team["captain"] != message.from_user.id:
            await message.answer("❌ Captain only.")
            return
        if sub == "clear":
            await teams.clear_match_xi(team)
            await message.answer("✅ Match players cleared.")
            return
        ids = parts[3:] if len(parts) > 3 and parts[2].lower() == "set" else parts[2:]
        if len(ids) not in {4, 5} or not all(x.isdigit() for x in ids):
            await message.answer("Usage: /team xi set ID1 ID2 ID3 ID4 [ID5]")
            return
        ok, text = await teams.set_match_xi(team, [int(x) for x in ids])
        await message.answer(("✅ " if ok else "❌ ") + text)
        return

    if action in {"matchxi", "players"}:
        team = await teams.my_team(message.chat.id, message.from_user.id)
        if not team:
            await message.answer("❌ You are not in a team.")
            return

        sub_parts = parts[2].split() if len(parts) > 2 else []
        if sub_parts and sub_parts[0].lower() == "clear":
            if team["captain"] != message.from_user.id:
                await message.answer("❌ Captain only.")
                return
            await teams.clear_match_xi(team)
            await message.answer("✅ Match XI cleared.")
            return

        if team["captain"] != message.from_user.id:
            await message.answer("❌ Captain only.")
            return

        ids = sub_parts
        if len(ids) not in {4, 5} or not all(x.isdigit() for x in ids):
            await message.answer(
                "Usage: /team players ID1 ID2 ID3 ID4 [ID5]\n"
                "/team matchxi ID1 ID2 ID3 ID4 [ID5]  — alias"
            )
            return

        ok, text = await teams.set_match_xi(team, [int(x) for x in ids])
        await message.answer(("✅ " if ok else "❌ ") + text)
        return

    if action == "role":
        team = await teams.my_team(message.chat.id, message.from_user.id)
        if not team or team["captain"] != message.from_user.id:
            await message.answer("❌ Captain only."); return
        if len(parts) < 3:
            await message.answer("Usage: /team role USER_ID batter|bowler|all_rounder|keeper"); return
        vals = parts[2].split()
        if len(vals) == 2 and vals[0].isdigit():
            uid, role = int(vals[0]), vals[1].lower()
        elif len(parts) >= 3 and parts[2].isdigit() and len(parts) >= 4:
            uid, role = int(parts[2]), parts[3].lower()
        else:
            await message.answer("Usage: /team role USER_ID batter|bowler|all_rounder|keeper"); return
        ok, text = await teams.set_role(team, uid, role)
        await message.answer(("✅ " if ok else "❌ ") + text); return

    await message.answer(HELP, parse_mode="HTML")
