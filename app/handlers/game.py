import asyncio
import os
import time

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile

from app.game.models import Player, Match, Phase
from app.game.engine import CricketEngine, BOWLING_TYPES
from app.game.ai import CricketAI
from app.utils import mention

router = Router()
_MATCH_LOCKS = {}


def _match_lock(chat_id):
    return _MATCH_LOCKS.setdefault(chat_id, asyncio.Lock())


def _drop_match_lock(chat_id):
    _MATCH_LOCKS.pop(chat_id, None)


def p(message):
    return Player(message.from_user.id, message.from_user.full_name)


def name(match, uid):
    for x in match.players():
        if x and x.uid == uid:
            return x.name
    return "Player"


def score_text(match):
    i = match.innings
    if not i:
        return "0/0 • 0.0 overs"
    return f"{i.runs}/{i.wickets} • {i.over(match.balls_per_over)} overs"


def parse_format(parts, default_overs=2, default_balls=6):
    """Parse optional [OVERS] [BALLS_PER_OVER] consistently across modes."""
    nums = []
    for raw in reversed(parts):
        if raw.isdigit():
            nums.append(int(raw))
            if len(nums) == 2:
                break
        else:
            break
    nums.reverse()

    overs, balls = default_overs, default_balls
    if len(nums) == 1:
        overs = nums[0]
    elif len(nums) == 2:
        overs, balls = nums

    if not 1 <= overs <= 20:
        raise ValueError("Overs must be between 1 and 20.")
    if balls not in {3, 4, 5, 6}:
        raise ValueError("Balls per over must be 3, 4, 5 or 6.")
    return overs, balls


def bowling_menu():
    return (
        "🎯 <b>BOWLING TURN</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Choose your delivery privately:\n\n"
        "1️⃣ 🌪️ Swing\n"
        "2️⃣ 🎯 Yorker\n"
        "3️⃣ ⬆️ Bouncer\n"
        "4️⃣ 🐢 Slower Ball\n"
        "5️⃣ ↩️ Inswing\n"
        "6️⃣ ↪️ Outswing\n\n"
        "🔒 Your delivery stays private."
    )


def _team_label(match, uid):
    if match.mode != "team":
        return ""
    side = match.team_for_uid(uid)
    return match.team_a_name if side == "a" else match.team_b_name if side == "b" else ""


async def send_bowler_dm(bot, match):
    i = match.innings
    if not i:
        return False
    try:
        team_line = f"\n🏏 Team: <b>{_team_label(match, i.bowler.uid)}</b>\n" if match.mode == "team" else ""
        await bot.send_message(i.bowler.uid, bowling_menu() + team_line, parse_mode="HTML")
        return True
    except Exception:
        return False


async def send_batting_prompt(bot, match):
    """Public batting UI. GIF is deliberately sent to the group, never DM."""
    i = match.innings
    if not i:
        return False

    if match.mode == "classic":
        caption = (
            "━━━━━━━━━━━━━━━━━━\n"
            "🏏 <b>YOUR BATTING TURN</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>{i.batter.name}</b>\n"
            f"📊 Score: <b>{score_text(match)}</b>\n\n"
            "Send your shot number <b>1–6</b> in the group.\n"
            "🔐 The bowler's delivery remains hidden."
        )
    else:
        caption = (
            "━━━━━━━━━━━━━━━━━━\n"
            "🏏 <b>YOUR BATTING TURN</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"🏏 Striker: <b>{i.batter.name}</b>\n"
            f"👤 Non-striker: <b>{i.non_striker.name if i.non_striker else '—'}</b>\n"
            f"🎯 Bowler: <b>{i.bowler.name}</b>\n"
            f"📊 Score: <b>{score_text(match)}</b>\n\n"
            "Send your shot number <b>1–6</b> in the group."
        )

    gif = "assets/cricket_live.gif"
    try:
        if os.path.exists(gif):
            await bot.send_animation(
                match.chat_id,
                FSInputFile(gif),
                caption=caption,
                parse_mode="HTML",
            )
        else:
            await bot.send_message(match.chat_id, caption, parse_mode="HTML")
        return True
    except Exception:
        await bot.send_message(match.chat_id, caption, parse_mode="HTML")
        return False


async def persist_live(db, matches, match):
    await db.live_matches.replace_one(
        {"chat_id": match.chat_id},
        matches.serialize(match),
        upsert=True,
    )


async def clear_live(db, chat_id):
    await db.live_matches.delete_one({"chat_id": chat_id})


def _active_side_name(match, side):
    return match.team_a_name if side == "a" else match.team_b_name


async def _finish_match_to_chat(bot, match, users, db, matches, winner):
    i = match.innings

    if winner == 0:
        winner_name = "Tie"
        if match.mode == "classic":
            await users.record_match(match.creator.uid, tied=True)
            if match.opponent:
                await users.record_match(match.opponent.uid, tied=True)
        else:
            await users.record_match(match.team_a_captain, tied=True)
            await users.record_match(match.team_b_captain, tied=True)
    else:
        if match.mode == "team":
            winner_name = _active_side_name(
                match, "a" if winner == match.team_a_captain else "b"
            )
            loser = (
                match.team_b_captain
                if winner == match.team_a_captain
                else match.team_a_captain
            )
        else:
            if match.mode == "classic" and winner == -1:
                winner_name = "Cricket Bot AI"
                loser = match.creator.uid
            else:
                winner_name = name(match, winner)
                loser = (
                    match.opponent.uid
                    if match.opponent and winner == match.creator.uid
                    else match.creator.uid
                )

        await users.record_match(winner, won=True)
        if loser not in (None, -1):
            await users.record_match(loser, lost=True)

    await db.matches.insert_one({
        "chat_id": match.chat_id,
        "mode": match.mode,
        "players": [x.uid for x in match.players()],
        "winner": winner,
        "team_a_name": match.team_a_name,
        "team_b_name": match.team_b_name,
        "first_score": match.first_score,
        "second_score": i.runs if i else None,
        "overs": match.max_overs,
        "balls_per_over": match.balls_per_over,
        "created_at": __import__("app.utils", fromlist=["now"]).now(),
    })

    await bot.send_message(
        match.chat_id,
        "━━━━━━━━━━━━━━━━━━\n"
        "🏆 <b>MATCH COMPLETE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🏏 Innings 1: <b>{match.first_score or 0}</b>\n"
        f"🏏 Innings 2: <b>{i.runs if i else 0}/{i.wickets if i else 0}</b>\n"
        f"⚙️ Format: <b>{match.max_overs} overs × {match.balls_per_over}</b>\n\n"
        f"👑 <b>WINNER: {winner_name}</b>",
        parse_mode="HTML",
    )
    await clear_live(db, match.chat_id)
    matches.remove(match.chat_id)
    _drop_match_lock(match.chat_id)


async def _begin_next_ball(bot, db, matches, match):
    i = match.innings
    if not i:
        return

    # Solo first innings: AI is the hidden bowler. Its delivery is selected
    # before the public batting prompt, but never exposed to the player.
    if match.mode == "classic" and match.opponent and match.opponent.uid == -1 and match.innings_no == 1:
        match.pending_bat = None
        if match.pending_bowl_type is None:
            match.pending_bowl_type = CricketAI.choose()
        match.phase = Phase.BAT
        match.touch()
        await persist_live(db, matches, match)
        await send_batting_prompt(bot, match)
        return

    match.pending_bat = None
    match.pending_bowl_type = None
    match.phase = Phase.BOWL
    match.touch()
    await persist_live(db, matches, match)

    dm_ok = await send_bowler_dm(bot, match)
    if not dm_ok:
        controller = match.controller_uid_for(i.bowler)
        target = controller or i.bowler.uid
        await bot.send_message(
            match.chat_id,
            f"⚠️ <b>Bowling DM required</b>\n"
            f"{mention(target, i.bowler.name)} please open the bot in private chat "
            "and send /start.",
            parse_mode="HTML",
        )


async def _resolve_result(bot, match, users, db, matches, settings, bat, bowl):
    engine = CricketEngine()
    before_batter = match.innings.batter
    before_bowler = match.innings.bowler

    result = engine.play(match, bat, bowl, settings.owner_id)
    await persist_live(db, matches, match)

    wicket_line = f"❌ <b>{before_batter.name} OUT</b>\n" if result.wicket else ""
    next_line = ""
    if result.wicket and match.mode == "team" and match.innings.batter.uid != before_batter.uid:
        next_line = f"➡️ Next batter: <b>{match.innings.batter.name}</b>\n"

    await bot.send_message(
        match.chat_id,
        "━━━━━━━━━━━━━━━━━━\n"
        f"⚾ <b>BALL {match.innings.over(match.balls_per_over)}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🏏 Batter: <b>{before_batter.name}</b>\n"
        f"🎯 Bowler: <b>{before_bowler.name}</b>\n"
        f"🎯 Delivery: <b>{result.ball_type}</b>\n\n"
        f"{result.text}\n"
        f"{wicket_line}"
        f"{next_line}"
        f"📊 Score: <b>{score_text(match)}</b>",
        parse_mode="HTML",
    )

    if engine.innings_complete(match):
        if match.innings_no == 1:
            engine.switch(match)
            await persist_live(db, matches, match)
            await bot.send_message(
                match.chat_id,
                "━━━━━━━━━━━━━━━━━━\n"
                "🏁 <b>INNINGS BREAK</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"🎯 Target: <b>{match.target}</b>\n"
                f"🏏 Batting: <b>{match.innings.batter.name}</b>\n"
                f"🎯 Bowling: <b>{match.innings.bowler.name}</b>\n\n"
                "The new bowler will choose the delivery first.",
                parse_mode="HTML",
            )
            await _begin_next_ball(bot, db, matches, match)
            return

        await _finish_match_to_chat(
            bot, match, users, db, matches, engine.winner(match)
        )
        return

    # Engine already changed the bowler after an over.
    await _begin_next_ball(bot, db, matches, match)


@router.message(Command("play"))
async def play(message: Message, matches, users, admin, db):
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("👥 Use /play inside a group or supergroup.")
        return

    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    if matches.get(message.chat.id):
        await message.answer("🏏 A match is already active here.")
        return

    try:
        overs, balls = parse_format((message.text or "").split()[1:], 2, 6)
    except ValueError as e:
        await message.answer(f"❌ {e}\nUse: <code>/play [overs] [balls]</code>", parse_mode="HTML")
        return

    await users.ensure(message.from_user)
    match = Match(message.chat.id, p(message), max_overs=overs, balls_per_over=balls)
    matches.create(match)
    await persist_live(db, matches, match)

    await message.answer(
        "━━━━━━━━━━━━━━━━━━\n"
        "🏏 <b>1v1 CRICKET LOBBY</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"⚙️ Format: <b>{overs} overs × {balls} balls</b>\n"
        f"👤 {mention(match.creator.uid, match.creator.name)}\n\n"
        "Waiting for opponent…\n"
        "Use <code>/join</code> to enter.",
        parse_mode="HTML",
    )


@router.message(Command("join"))
async def join(message: Message, matches, users, admin, db, bot):
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("👥 Join matches from the group.")
        return
    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))

    match = matches.get(message.chat.id)
    if not match or match.mode != "classic":
        await message.answer("❌ No 1v1 lobby. Use /play.")
        return
    if match.opponent:
        await message.answer("❌ Match is full.")
        return
    if message.from_user.id == match.creator.uid:
        await message.answer("❌ You are already in the match.")
        return

    await users.ensure(message.from_user)
    match.opponent = p(message)
    CricketEngine().start(match)
    await persist_live(db, matches, match)

    i = match.innings
    await message.answer(
        "━━━━━━━━━━━━━━━━━━\n"
        "🏏 <b>1v1 MATCH READY</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{mention(match.creator.uid, match.creator.name)}  🆚  "
        f"{mention(match.opponent.uid, match.opponent.name)}\n\n"
        f"⚙️ <b>{match.max_overs} overs × {match.balls_per_over} balls</b>\n"
        f"🏏 Batting: <b>{i.batter.name}</b>\n"
        f"🎯 Bowling: <b>{i.bowler.name}</b>\n\n"
        "🎯 <b>Bowler goes first.</b>\n"
        "Your private delivery menu has been sent.",
        parse_mode="HTML",
    )
    await _begin_next_ball(bot, db, matches, match)


@router.message(Command("solo"))
async def solo(message: Message, matches, users, admin, db, bot):
    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    if matches.get(message.chat.id):
        await message.answer("🏏 A match is already active here.")
        return

    try:
        overs, balls = parse_format((message.text or "").split()[1:], 2, 6)
    except ValueError as e:
        await message.answer(f"❌ {e}\nUse: <code>/solo [overs] [balls]</code>", parse_mode="HTML")
        return

    await users.ensure(message.from_user)
    user = p(message)
    ai = Player(-1, "Cricket Bot AI")
    match = Match(message.chat.id, user, ai, max_overs=overs, balls_per_over=balls)
    matches.create(match)

    # Solo first innings: AI is the bowler. The AI chooses privately/internal,
    # then the human gets the public batting prompt with the GIF.
    match.innings = CricketEngine()._new_innings([user], [ai], classic=True)
    match.phase = Phase.BAT
    match.pending_bowl_type = CricketAI.choose()
    match.touch()
    await persist_live(db, matches, match)

    await message.answer(
        "━━━━━━━━━━━━━━━━━━\n"
        "🤖 <b>SOLO MATCH</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"⚙️ Format: <b>{overs} overs × {balls} balls</b>\n"
        "You 🆚 Cricket Bot AI\n\n"
        "🎯 The AI has secretly chosen the delivery.\n"
        "Your batting card is below.",
        parse_mode="HTML",
    )
    await send_batting_prompt(bot, match)


@router.message(Command("custom"))
async def custom(message: Message, matches, users, admin, db):
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("👥 Use /custom inside a group.")
        return

    raw = (message.text or "").split()[1:]
    try:
        overs, balls = parse_format(raw, 5, 6)
    except ValueError as e:
        await message.answer(f"❌ {e}\nUse: <code>/custom [overs] [balls]</code>", parse_mode="HTML")
        return

    if matches.get(message.chat.id):
        await message.answer("🏏 A match is already active here.")
        return

    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    await users.ensure(message.from_user)
    match = Match(message.chat.id, p(message), max_overs=overs, balls_per_over=balls)
    matches.create(match)
    await persist_live(db, matches, match)

    await message.answer(
        "⚙️ <b>CUSTOM 1v1 LOBBY</b>\n\n"
        f"🎯 Format: <b>{overs} overs × {balls} balls</b>\n"
        "Use <code>/join</code> to enter.",
        parse_mode="HTML",
    )


@router.message(Command("teamplay"))
async def teamplay(message: Message, matches, teams, users, admin, db):
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("👥 Team matches work inside groups.")
        return

    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    if matches.get(message.chat.id):
        await message.answer("🏏 A match is already active here.")
        return

    tokens = (message.text or "").split()[1:]
    if not tokens:
        await message.answer(
            "Usage: <code>/teamplay TEAM_NAME [OVERS] [BALLS]</code>\n"
            "Example: <code>/teamplay Tigers 2 6</code>",
            parse_mode="HTML",
        )
        return

    # Numeric suffixes are format options; everything before them is the team name.
    fmt = []
    while tokens and tokens[-1].isdigit() and len(fmt) < 2:
        fmt.append(int(tokens.pop()))
    fmt.reverse()
    try:
        overs, balls = parse_format([str(x) for x in fmt], 2, 6)
    except ValueError as e:
        await message.answer(f"❌ {e}", parse_mode="HTML")
        return

    team_name = " ".join(tokens).strip()
    if not team_name:
        await message.answer("❌ Team name is required.")
        return

    team = await teams.get(message.chat.id, team_name)
    if not team:
        await message.answer("❌ Team not found. Create it with /team create NAME")
        return
    if team["captain"] != message.from_user.id:
        await message.answer("❌ Only the team captain can start a team match.")
        return

    roster = await teams.match_roster(team)
    if len(roster) not in {4, 5}:
        await message.answer(
            "❌ Team match needs exactly 4 or 5 players.\n"
            "Add players with /team add USER_ID."
        )
        return

    await users.ensure(message.from_user)
    team_a = [Player(x["uid"], x["name"]) for x in roster]
    captain = Player(
        team["captain"],
        team["player_names"].get(str(team["captain"]), str(team["captain"]))
    )

    match = Match(
        message.chat.id,
        captain,
        mode="team",
        max_overs=overs,
        balls_per_over=balls,
        team_a=team_a,
        team_a_name=team["name"],
        team_a_captain=team["captain"],
    )
    matches.create(match)
    await persist_live(db, matches, match)

    await message.answer(
        "━━━━━━━━━━━━━━━━━━\n"
        "👥 <b>TEAM MATCH LOBBY</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🟦 <b>{team['name']}</b>  •  {len(team_a)} players\n"
        f"⚙️ Format: <b>{overs} overs × {balls} balls</b>\n\n"
        "Opposing captain:\n"
        "<code>/teamjoin YOUR_TEAM_NAME</code>",
        parse_mode="HTML",
    )


@router.message(Command("teamjoin"))
async def teamjoin(message: Message, matches, teams, users, admin, db, bot):
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("👥 Team matches work inside groups.")
        return

    match = matches.get(message.chat.id)
    if not match or match.mode != "team" or match.phase != Phase.LOBBY:
        await message.answer("❌ No team-match lobby is waiting.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /teamjoin YOUR_TEAM_NAME")
        return

    team = await teams.get(message.chat.id, parts[1])
    if not team:
        await message.answer("❌ Opposing team not found.")
        return
    if team["captain"] == match.team_a_captain:
        await message.answer("❌ The same team cannot play itself.")
        return
    if team["captain"] != message.from_user.id:
        await message.answer("❌ Only your team captain can join this lobby.")
        return

    roster = await teams.match_roster(team)
    if len(roster) not in {4, 5}:
        await message.answer("❌ Your team must have exactly 4 or 5 match players.")
        return

    match.team_b = [Player(x["uid"], x["name"]) for x in roster]
    match.team_b_name = team["name"]
    match.team_b_captain = team["captain"]
    match.opponent = Player(
        team["captain"],
        team["player_names"].get(str(team["captain"]), str(team["captain"]))
    )

    import random
    batting_side = "a" if random.choice([True, False]) else "b"
    CricketEngine().start_team(match, batting_side)
    await persist_live(db, matches, match)

    i = match.innings
    await message.answer(
        "━━━━━━━━━━━━━━━━━━\n"
        "🏏 <b>TEAM MATCH STARTED</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🟦 <b>{match.team_a_name}</b>  •  {len(match.team_a)}\n"
        f"🟥 <b>{match.team_b_name}</b>  •  {len(match.team_b)}\n\n"
        f"🪙 Toss → <b>{_active_side_name(match, batting_side)}</b> bats first.\n\n"
        f"🏏 Striker: <b>{i.batter.name}</b>\n"
        f"👤 Non-striker: <b>{i.non_striker.name}</b>\n"
        f"🎯 Bowler: <b>{i.bowler.name}</b>\n\n"
        "🎯 <b>Bowler goes first.</b>",
        parse_mode="HTML",
    )
    await _begin_next_ball(bot, db, matches, match)


@router.message(Command("score"))
@router.message(Command("status"))
async def status(message: Message, matches):
    match = matches.get(message.chat.id)
    if not match:
        await message.answer("🏏 No active match.")
        return

    if not match.innings:
        await message.answer("🏏 Match lobby is waiting for the second side.")
        return

    i = match.innings
    lines = [
        "━━━━━━━━━━━━━━━━━━",
        "📊 <b>LIVE SCORE</b>",
        "━━━━━━━━━━━━━━━━━━",
        "",
        f"🏏 <b>{i.runs}/{i.wickets}</b>  •  {i.over(match.balls_per_over)} overs",
        f"⚙️ {match.max_overs} overs × {match.balls_per_over} balls",
        f"🎯 Bowler: <b>{i.bowler.name}</b>",
    ]
    if match.mode == "classic":
        lines.append(f"🏏 Batter: <b>{i.batter.name}</b>")
    else:
        lines.extend([
            f"🏏 Striker: <b>{i.batter.name}</b>",
            f"👤 Non-striker: <b>{i.non_striker.name if i.non_striker else '—'}</b>",
        ])
    if match.target:
        lines.append(f"🎯 Target: <b>{match.target}</b>")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def _resolve_and_continue(bot, match, users, db, matches, settings, bat, bowl):
    await _resolve_result(bot, match, users, db, matches, settings, bat, bowl)


async def _group_number_input(message, matches, users, db, settings, bot):
    if message.chat.type not in {"group", "supergroup"}:
        return

    text = (message.text or "").strip()
    if text not in {"1", "2", "3", "4", "5", "6"}:
        return

    match = matches.get(message.chat.id)
    if not match or not match.innings or match.phase in {Phase.FINISHED, Phase.LOBBY}:
        return

    i = match.innings
    uid = message.from_user.id

    # Solo first innings: use the AI delivery that was selected BEFORE
    # the batting prompt was shown.
    if match.mode == "classic" and match.opponent and match.opponent.uid == -1 and match.innings_no == 1:
        if match.phase != Phase.BAT or uid != i.batter.uid:
            return
        if match.pending_bowl_type is None:
            match.pending_bowl_type = CricketAI.choose()
        bat = int(text)
        bowl = match.pending_bowl_type
        match.pending_bowl_type = None
        match.phase = Phase.BOWL
        match.touch()
        await persist_live(db, matches, match)
        await _resolve_and_continue(bot, match, users, db, matches, settings, bat, bowl)
        return

    if match.phase != Phase.BAT:
        await message.answer("⏳ <b>Bowler first.</b> Wait for the private delivery.", parse_mode="HTML")
        return

    if uid != i.batter.uid:
        await message.answer("⏳ This is not your batting turn.", parse_mode="HTML")
        return

    if match.pending_bowl_type is None:
        await message.answer("⏳ The bowler has not chosen a delivery yet.", parse_mode="HTML")
        return

    bat = int(text)
    bowl = match.pending_bowl_type
    match.pending_bowl_type = None
    match.phase = Phase.BOWL
    match.touch()
    await persist_live(db, matches, match)

    await _resolve_and_continue(bot, match, users, db, matches, settings, bat, bowl)


async def _dm_bowling_input(message, matches, users, db, settings, bot):
    if message.chat.type != "private":
        return

    text = (message.text or "").strip()
    if text not in {"1", "2", "3", "4", "5", "6"}:
        return

    uid = message.from_user.id
    match = next(
        (
            m for m in matches.all()
            if m.innings
            and m.phase == Phase.BOWL
            and m.innings.bowler.uid == uid
        ),
        None,
    )
    if not match:
        await message.answer("🏏 No active bowling turn for you.")
        return

    if settings.turn_timeout > 0 and time.time() - match.turn_started_at > settings.turn_timeout:
        await message.answer("⏰ Your bowling turn timed out.")
        winner = match.innings.batter.uid
        await _finish_match_to_chat(bot, match, users, db, matches, winner)
        return

    bowl = int(text)

    # Solo second innings: human bowls, AI bats.
    if match.mode == "classic" and match.opponent and match.opponent.uid == -1 and match.innings_no == 2:
        match.phase = Phase.BOWL
        match.touch()
        await persist_live(db, matches, match)
        await _resolve_and_continue(
            bot, match, users, db, matches, settings, CricketAI.choose(), bowl
        )
        return

    if match.pending_bowl_type is not None or match.phase != Phase.BOWL:
        await message.answer("⏳ This delivery has already been submitted.")
        return

    match.pending_bowl_type = bowl
    match.phase = Phase.BAT
    match.touch()
    await persist_live(db, matches, match)

    await send_batting_prompt(bot, match)
    await message.answer(
        f"🔒 <b>Delivery locked:</b> {BOWLING_TYPES[bowl][1]} {BOWLING_TYPES[bowl][0]}\n"
        "The striker has been asked for the shot.",
        parse_mode="HTML",
    )


@router.message()
async def number_input(message: Message, matches, users, db, settings, bot):
    # This catch-all deliberately ignores commands and non-numeric messages.
    # It cannot swallow /team, /leaderboard, /solo, etc.
    if not (message.text or "").strip().isdigit():
        return
    if message.chat.type == "private":
        async with _match_lock(message.from_user.id):
            await _dm_bowling_input(message, matches, users, db, settings, bot)
    elif message.chat.type in {"group", "supergroup"}:
        async with _match_lock(message.chat.id):
            await _group_number_input(message, matches, users, db, settings, bot)
