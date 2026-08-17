import asyncio
import time

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

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
    return f"{i.runs}/{i.wickets} • {i.over(match.balls_per_over)} overs"


def bowling_menu():
    return (
        "🎯 <b>YOUR BOWLING TURN</b>\n\n"
        "Choose a delivery and send its number <b>in this DM</b>:\n\n"
        "1️⃣ 🌪️ Swing\n"
        "2️⃣ 🎯 Yorker\n"
        "3️⃣ ⬆️ Bouncer\n"
        "4️⃣ 🐢 Slower Ball\n"
        "5️⃣ ↩️ Inswing\n"
        "6️⃣ ↪️ Outswing\n\n"
        "🔒 Your choice stays private."
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
        team_line = (
            f"\n🏏 Team: <b>{_team_label(match, i.bowler.uid)}</b>\n"
            if match.mode == "team" else ""
        )
        await bot.send_message(
            i.bowler.uid,
            bowling_menu() + team_line
        )
        return True
    except Exception:
        return False


async def persist_live(db, matches, match):
    await db.live_matches.replace_one(
        {"chat_id": match.chat_id},
        matches.serialize(match),
        upsert=True,
    )


async def clear_live(db, chat_id):
    await db.live_matches.delete_one({"chat_id": chat_id})


def _active_side_name(match, team):
    if team == "a":
        return match.team_a_name or "Team A"
    return match.team_b_name or "Team B"


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
            winner_name = (
                _active_side_name(match, "a")
                if winner == match.team_a_captain
                else _active_side_name(match, "b")
            )
            loser = (
                match.team_b_captain
                if winner == match.team_a_captain
                else match.team_a_captain
            )
        else:
            winner_name = name(match, winner)
            loser = (
                match.opponent.uid
                if match.opponent and winner == match.creator.uid
                else match.creator.uid
            )

        await users.record_match(winner, won=True)
        if loser is not None and loser != -1:
            await users.record_match(loser, lost=True)

    await db.matches.insert_one({
        "chat_id": match.chat_id,
        "mode": match.mode,
        "players": [p.uid for p in match.players()],
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
        "━━━━━━━━━━━━━━\n"
        "🏆 <b>MATCH SUMMARY</b>\n\n"
        f"🏏 First innings: <b>{match.first_score or 0}</b>\n"
        f"🏏 Second innings: <b>{i.runs if i else 0}/{i.wickets if i else 0}</b>\n\n"
        f"🏆 <b>RESULT: {winner_name}</b>",
        parse_mode="HTML",
    )
    await clear_live(db, match.chat_id)
    matches.remove(match.chat_id)
    _drop_match_lock(match.chat_id)


async def _begin_next_ball(bot, db, matches, match):
    """Every normal delivery starts with the bowler, not the batter."""
    i = match.innings
    match.pending_bat = None
    match.pending_bowl_type = None
    match.phase = Phase.BOWL
    match.touch()
    await persist_live(db, matches, match)

    dm_ok = await send_bowler_dm(bot, match)
    if not dm_ok:
        controller = match.controller_uid_for(i.bowler)
        await bot.send_message(
            match.chat_id,
            f"⚠️ {mention(controller, i.bowler.name)}, "
            "the current bowler must open the bot in DM and send /start."
            if controller else
            "⚠️ Current bowler must open the bot in DM and send /start.",
            parse_mode="HTML",
        )


@router.message(Command("play"))
async def play(message: Message, matches, users, admin, db):
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("👥 Use /play inside a group or supergroup.")
        return
    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    if matches.get(message.chat.id):
        await message.answer("🏏 A match is already active here.")
        return

    await users.ensure(message.from_user)
    parts = (message.text or "").split()
    overs = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 2
    balls = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 6
    if overs not in {1, 2, 5, 10, 20}:
        await message.answer("Use: /play <1|2|5|10|20> [3|4|5|6]")
        return
    if balls not in {3, 4, 5, 6}:
        await message.answer("Balls/over must be 3, 4, 5 or 6.")
        return
    match = Match(message.chat.id, p(message), max_overs=overs, balls_per_over=balls)
    matches.create(match)
    await persist_live(db, matches, match)

    await message.answer(
        "🏏 <b>1v1 CRICKET LOBBY</b>\n\n"
        f"🎯 {overs} overs • {balls} legal balls/over\n"
        f"👤 {mention(match.creator.uid, match.creator.name)}\n\n"
        "Type /join to enter.",
        parse_mode="HTML",
    )


@router.message(Command("join"))
async def join(message: Message, matches, users, admin, db, bot):
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("👥 Join matches from the group.")
        return
    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    match = matches.get(message.chat.id)
    if not match:
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
        "🏏 <b>1v1 MATCH STARTED!</b>\n\n"
        f"{mention(match.creator.uid, match.creator.name)} 🆚 "
        f"{mention(match.opponent.uid, match.opponent.name)}\n\n"
        "🪙 Toss complete.\n"
        f"🏏 Batting: <b>{i.batter.name}</b>\n"
        f"🎯 Bowling: <b>{i.bowler.name}</b>\n\n"
        "🎯 <b>Bowler goes FIRST.</b>\n"
        "A private bowling prompt has been sent.",
        parse_mode="HTML",
    )
    await _begin_next_ball(bot, db, matches, match)


@router.message(Command("solo"))
async def solo(message: Message, matches, users, admin, db):
    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    if matches.get(message.chat.id):
        await message.answer("🏏 A match is already active.")
        return

    await users.ensure(message.from_user)
    user = p(message)
    ai = Player(-1, "Cricket Bot AI")
    args = (message.text or "").split()
    overs = int(args[1]) if len(args) > 1 and args[1].isdigit() else 2
    balls = int(args[2]) if len(args) > 2 and args[2].isdigit() else 6
    if overs not in {1, 2, 5, 10, 20}:
        await message.answer("Use: /solo <1|2|5|10|20> [3|4|5|6]")
        return
    if balls not in {3, 4, 5, 6}:
        await message.answer("Balls/over must be 3, 4, 5 or 6.")
        return
    match = Match(message.chat.id, user, ai, max_overs=overs, balls_per_over=balls)
    matches.create(match)
    CricketEngine().start(match)
    match.innings.batter = user
    match.innings.non_striker = None
    match.innings.batting_team = [user]
    match.innings.bowling_team = [ai]
    match.phase = Phase.BAT
    match.pending_bowl_type = CricketAI.choose()
    await persist_live(db, matches, match)

    await message.answer(
        "🤖 <b>SOLO MODE</b>\n\n"
        "You 🆚 Cricket Bot AI\n"
        f"🎯 {overs} overs × {balls} balls\n\n"
        "🏏 <b>YOUR BATTING TURN</b>\n"
        "The AI has already chosen its delivery.\n"
        "Send your shot number <b>1–6 in the group</b>.",
        parse_mode="HTML",
    )


@router.message(Command("custom"))
async def custom(message: Message, matches, users, admin, db):
    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    parts = (message.text or "").split()
    overs = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
    balls = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 6
    if overs not in {1, 2, 5, 10, 20}:
        await message.answer("Use: /custom <1|2|5|10|20> [3|4|5|6]")
        return
    if balls not in {3, 4, 5, 6}:
        await message.answer("Balls/over must be 3, 4, 5 or 6.")
        return
    if matches.get(message.chat.id):
        await message.answer("🏏 A match is already active.")
        return
    await users.ensure(message.from_user)
    match = Match(message.chat.id, p(message), max_overs=overs, balls_per_over=balls)
    matches.create(match)
    await persist_live(db, matches, match)
    await message.answer(
        f"🏏 <b>CUSTOM 1v1 MATCH</b>\n\n"
        f"🎯 {overs} overs • {balls} legal balls/over\n"
        f"👤 {message.from_user.full_name}\n\n"
        "Type /join to enter.",
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

    args = (message.text or "").split()[1:]
    if not args:
        await message.answer(
            "Usage: <code>/teamplay TEAM NAME [OVERS] [BALLS]</code>\n"
            "Example: <code>/teamplay Tigers 2 6</code>",
            parse_mode="HTML",
        )
        return

    balls = 6
    if args[-1].isdigit() and int(args[-1]) in {3, 4, 5, 6}:
        balls = int(args.pop())
    overs = 2
    if args and args[-1].isdigit():
        overs = int(args.pop())
    team_name = " ".join(args).strip()

    if overs not in {1, 2, 5, 10, 20}:
        await message.answer("Overs must be 1, 2, 5, 10 or 20.")
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
            "Captain: add 4–5 players or set a 4/5-player match roster."
        )
        return

    await users.ensure(message.from_user)
    team_a = [Player(x["uid"], x["name"]) for x in roster]
    captain = Player(team["captain"], team["player_names"].get(str(team["captain"]), str(team["captain"])))

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
        "🏟️ <b>TEAM MATCH LOBBY</b>\n\n"
        f"🟦 <b>{team['name']}</b> • {len(team_a)} players\n"
        f"🎯 <b>{overs} overs × {balls} balls</b>\n\n"
        "Opposing captain: <code>/teamjoin YOUR TEAM NAME</code>",
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

    team_b = [Player(x["uid"], x["name"]) for x in roster]
    match.team_b = team_b
    match.team_b_name = team["name"]
    match.team_b_captain = team["captain"]
    match.opponent = Player(
        team["captain"],
        team["player_names"].get(str(team["captain"]), str(team["captain"]))
    )

    # Toss: choose batting side randomly.
    batting_side = "a" if __import__("random").choice([True, False]) else "b"
    engine = CricketEngine()
    engine.start_team(match, batting_side)
    await persist_live(db, matches, match)

    i = match.innings
    await message.answer(
        "🏏 <b>TEAM MATCH STARTED!</b>\n\n"
        f"🟦 <b>{match.team_a_name}</b> — {len(match.team_a)} players\n"
        f"🟥 <b>{match.team_b_name}</b> — {len(match.team_b)} players\n\n"
        f"🪙 Toss complete → <b>{_active_side_name(match, batting_side)}</b> bats first.\n\n"
        f"🏏 Striker: <b>{i.batter.name}</b>\n"
        f"🏏 Non-striker: <b>{i.non_striker.name if i.non_striker else '—'}</b>\n"
        f"🎯 Bowler: <b>{i.bowler.name}</b>\n\n"
        "🎯 <b>Bowler goes FIRST.</b>\n"
        "The current bowler has been sent the private delivery menu.",
        parse_mode="HTML",
    )
    await _begin_next_ball(bot, db, matches, match)


@router.message(Command("status"))
@router.message(Command("score"))
async def status(message: Message, matches):
    match = matches.get(message.chat.id)
    if not match:
        await message.answer("🏏 No active match.")
        return
    if not match.innings:
        await message.answer(f"🏏 Lobby — {match.creator.name} is waiting.")
        return

    i = match.innings
    text = (
        f"🏏 <b>LIVE SCORE</b>\n\n"
        f"🏏 Batter: <b>{i.batter.name}</b>"
        + (f"\n🏏 Non-striker: <b>{i.non_striker.name}</b>" if match.mode == "team" and i.non_striker else "")
        + f"\n📊 <b>{score_text(match)}</b>\n"
        f"🎯 Bowler: <b>{i.bowler.name}</b>\n"
        f"⚾ Legal balls: {i.balls}/{match.max_overs * match.balls_per_over}"
    )
    if match.mode == "team":
        text += (
            f"\n\n🟦 {match.team_a_name}: {len(match.team_a)} players"
            f"\n🟥 {match.team_b_name}: {len(match.team_b)} players"
        )
    if match.target:
        text += f"\n🎯 Target: <b>{match.target}</b>"
    await message.answer(text, parse_mode="HTML")


async def _send_batting_prompt(bot, match):
    """Show the live cricket animation in the group, never in the bowler DM."""
    i = match.innings
    if not i:
        return
    caption = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🏏 <b>YOUR BATTING TURN</b>\n\n"
        f"👤 Batter: <b>{i.batter.name}</b>\n"
        "🔢 Choose your shot: <b>1–6</b>\n\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    try:
        from aiogram.types import FSInputFile
        gif = FSInputFile("assets/cricket_live.gif")
        await bot.send_animation(match.chat_id, gif, caption=caption, parse_mode="HTML")
    except Exception:
        await bot.send_message(match.chat_id, caption, parse_mode="HTML")

async def _resolve_result(bot, message, match, users, db, matches, settings, bat, bowl):
    engine = CricketEngine()
    before_batter = match.innings.batter
    before_bowler = match.innings.bowler

    result = engine.play(match, bat, bowl, settings.owner_id)
    await persist_live(db, matches, match)

    wicket_line = (
        f"❌ <b>{before_batter.name} OUT</b>\n"
        if result.wicket else ""
    )

    await bot.send_message(
        match.chat_id,
        "━━━━━━━━━━━━━━\n"
        f"⚾ <b>BALL {match.innings.over(match.balls_per_over)}</b>\n\n"
        f"🏏 Batter: <b>{before_batter.name}</b>\n"
        f"🎯 Bowler: <b>{before_bowler.name}</b>\n"
        f"🎯 Delivery: <b>{result.ball_type}</b>\n"
        f"{result.text}\n"
        f"{wicket_line}\n"
        f"📊 Score: <b>{score_text(match)}</b>",
        parse_mode="HTML",
    )

    if engine.innings_complete(match):
        if match.innings_no == 1:
            engine.switch(match)
            await persist_live(db, matches, match)
            await bot.send_message(
                match.chat_id,
                "━━━━━━━━━━━━━━\n"
                "🏁 <b>INNINGS OVER</b>\n\n"
                f"🎯 Target: <b>{match.target}</b>\n"
                f"🏏 {match.innings.batter.name}* is now batting.\n"
                "🎯 The new bowler will choose the delivery first.",
                parse_mode="HTML",
            )
            await _begin_next_ball(bot, db, matches, match)
            return

        winner = engine.winner(match)
        await _finish_match_to_chat(bot, match, users, db, matches, winner)
        return

    await _begin_next_ball(bot, db, matches, match)
    # _begin_next_ball handles the private delivery choice. The batting
    # animation is sent only after the bowler submits it.


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

    # SOLO: AI chooses the delivery after the user chooses the shot.
    if match.opponent and match.opponent.uid == -1:
        if match.phase != Phase.BAT or uid != i.batter.uid:
            return
        bowl = match.pending_bowl_type
        if bowl is None:
            match.pending_bowl_type = CricketAI.choose()
            bowl = match.pending_bowl_type
        match.pending_bowl_type = None
        result = CricketEngine().play(
            match, int(text), bowl, settings.owner_id
        )
        await persist_live(db, matches, match)
        await message.answer(
            f"{result.text}\n\n"
            f"🤖 AI delivery: <b>{result.ball_type}</b>\n"
            f"🏏 Your score: <b>{score_text(match)}</b>",
            parse_mode="HTML",
        )
        if CricketEngine().innings_complete(match):
            if match.innings_no == 1:
                CricketEngine().switch(match)
                await persist_live(db, matches, match)
                await message.answer(
                    "🏁 <b>INNINGS OVER</b>\n"
                    f"🎯 Target: <b>{match.target}</b>\n"
                    "🎯 Your bowling turn is now private.",
                    parse_mode="HTML",
                )
                return
            await _finish_match_to_chat(
                bot, match, users, db, matches, CricketEngine().winner(match)
            )
        else:
            match.phase = Phase.BAT
            match.touch()
            await persist_live(db, matches, match)
            await message.answer(
                f"⚾ Next ball — send <b>1–6</b> when prompted."
            )
        return

    # Multiplayer/team batting input is accepted ONLY from the current striker.
    if match.phase != Phase.BAT:
        await message.answer("⏳ Bowler is choosing the delivery first.")
        return

    if uid != i.batter.uid:
        await message.answer("⏳ You are not the current striker.")
        return

    if match.pending_bowl_type is None:
        await message.answer("⏳ Wait for the bowler to choose a delivery.")
        return

    # Consume the batting choice immediately so duplicate messages cannot
    # submit a second ball.
    bat = int(text)
    bowl = match.pending_bowl_type
    match.pending_bowl_type = None
    match.phase = Phase.BOWL
    match.touch()
    await persist_live(db, matches, match)

    await _resolve_result(
        bot, message, match, users, db, matches, settings, bat, bowl
    )


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

    # Solo second innings: the human is the bowler; AI is the batter.
    if not match:
        match = next(
            (
                m for m in matches.all()
                if m.opponent and m.opponent.uid == -1
                and m.innings and m.phase == Phase.BOWL
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

    # In solo second innings the AI supplies the batting number.
    if match.opponent and match.opponent.uid == -1:
        bat = CricketAI.choose()
    else:
        if match.phase != Phase.BOWL:
            await message.answer("⏳ This ball has already been submitted.")
            return
        # Store the private delivery and ask the striker for the shot.
        match.pending_bowl_type = bowl
        match.phase = Phase.BAT
        match.touch()
        await persist_live(db, matches, match)
        await _send_batting_prompt(bot, match)
        await message.answer(
            f"🔒 <b>Delivery locked:</b> {BOWLING_TYPES[bowl][1]} {BOWLING_TYPES[bowl][0]}\n"
            "Waiting for the striker.",
            parse_mode="HTML",
        )
        return

    # Solo second innings.
    await _resolve_result(
        bot, message, match, users, db, matches, settings, bat, bowl
    )


@router.message(F.text.regexp(r"^[1-6]$"))
async def number_input(message: Message, matches, users, db, settings, bot):
    if message.chat.type == "private":
        async with _match_lock(message.from_user.id):
            await _dm_bowling_input(message, matches, users, db, settings, bot)
    elif message.chat.type in {"group", "supergroup"}:
        async with _match_lock(message.chat.id):
            await _group_number_input(message, matches, users, db, settings, bot)
