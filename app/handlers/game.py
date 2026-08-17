import time
import asyncio

from aiogram import Router
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
    for team in (match.team_a, match.team_b):
        for x in team:
            if x.uid == uid:
                return x.name
    return "Player"


def score_text(match):
    i = match.innings
    if not i:
        return "0/0 • 0.0 overs"
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
        "🔒 Your number stays private; only the result is posted in the group."
    )


def batting_controller(match):
    i = match.innings
    if not i:
        return None
    if match.team_mode and i.batting_captain:
        return i.batting_captain
    return i.batter


def bowling_controller(match):
    i = match.innings
    if not i:
        return None
    if match.team_mode and i.bowling_captain:
        return i.bowling_captain
    return i.bowler


async def send_bowler_dm(bot, match):
    controller = bowling_controller(match)
    if not controller:
        return False
    try:
        await bot.send_message(controller.uid, bowling_menu())
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


def _team_players(doc):
    names = doc.get("player_names", {})
    xi = doc.get("playing_xi", [])
    return [
        Player(uid, names.get(str(uid), str(uid)))
        for uid in xi
    ]


def _team_captain(doc):
    names = doc.get("player_names", {})
    uid = doc["captain"]
    return Player(uid, names.get(str(uid), str(uid)))


def _team_ready(doc):
    return bool(doc and len(doc.get("playing_xi", [])) == 11)


def _winner_label(match, winner):
    if winner == 0:
        return "Tie"
    if match.team_mode:
        if match.team_a_captain and winner == match.team_a_captain.uid:
            return match.team_a_name or match.team_a_captain.name
        if match.team_b_captain and winner == match.team_b_captain.uid:
            return match.team_b_name or match.team_b_captain.name
    return name(match, winner)


async def _finish_match_to_chat(bot, match, users, db, matches, winner):
    i = match.innings
    winner_name = _winner_label(match, winner)

    if winner == 0:
        for cap in (match.team_a_captain, match.team_b_captain):
            if cap:
                await users.record_match(cap.uid, tied=True)
        if not match.team_mode:
            await users.record_match(match.creator.uid, tied=True)
            if match.opponent:
                await users.record_match(match.opponent.uid, tied=True)
    else:
        if match.team_mode:
            winner_cap = (
                match.team_a_captain
                if match.team_a_captain and winner == match.team_a_captain.uid
                else match.team_b_captain
            )
            loser_cap = (
                match.team_b_captain
                if winner_cap is match.team_a_captain
                else match.team_a_captain
            )
            if winner_cap:
                await users.record_match(winner_cap.uid, won=True)
            if loser_cap:
                await users.record_match(loser_cap.uid, lost=True)
        else:
            loser = match.opponent.uid if winner == match.creator.uid else match.creator.uid
            await users.record_match(winner, won=True)
            if loser != -1:
                await users.record_match(loser, lost=True)

    await db.matches.insert_one({
        "chat_id": match.chat_id,
        "players": [match.creator.uid, match.opponent.uid] if match.opponent else [],
        "team_mode": match.team_mode,
        "team_a": match.team_a_name,
        "team_b": match.team_b_name,
        "winner": winner,
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


async def _announce_next_ball(bot, match):
    i = match.innings
    if not i:
        return
    controller = batting_controller(match)
    controller_name = controller.name if controller else i.batter.name
    await bot.send_message(
        match.chat_id,
        "━━━━━━━━━━━━━━\n"
        f"⚾ <b>NEXT BALL — {i.over(match.balls_per_over)}</b>\n\n"
        f"🏏 Striker: <b>{i.batter.name}</b>\n"
        + (f"🏏 Non-striker: <b>{i.non_striker.name}</b>\n" if i.non_striker else "")
        + f"🎯 Bowler: <b>{i.bowler.name}</b>\n\n"
        f"{mention(controller.uid, controller_name)}, send <b>1–6 in the group</b>.",
        parse_mode="HTML",
    )


async def _complete_after_delivery(bot, match, engine, users, db, matches):
    if engine.innings_complete(match):
        if match.innings_no == 1:
            engine.switch(match)
            await persist_live(db, matches, match)
            i = match.innings
            await bot.send_message(
                match.chat_id,
                "━━━━━━━━━━━━━━\n"
                "🏁 <b>INNINGS OVER</b>\n\n"
                f"🏏 First innings: <b>{match.first_score}</b>\n"
                f"🎯 Target: <b>{match.target}</b>\n\n"
                f"🏏 {i.batting_team[0].name} & {i.batting_team[1].name} are opening.\n"
                f"🎯 Bowler: <b>{i.bowler.name}</b>\n\n"
                "Send batting number <b>1–6 in the group</b>.",
                parse_mode="HTML",
            )
            dm_ok = await send_bowler_dm(bot, match)
            if not dm_ok:
                controller = bowling_controller(match)
                await bot.send_message(
                    match.chat_id,
                    f"⚠️ {mention(controller.uid, controller.name)}, "
                    "open the bot in DM and send /start for private bowling.",
                    parse_mode="HTML",
                )
            return True

        winner = engine.winner(match)
        await _finish_match_to_chat(bot, match, users, db, matches, winner)
        return True

    match.phase = Phase.BAT
    match.touch()
    await persist_live(db, matches, match)
    await _announce_next_ball(bot, match)
    return False


@router.message(Command("play"))
async def play(message: Message, matches, users, admin, db):
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("👥 Use /play inside a group or supergroup.")
        return
    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    existing = matches.get(message.chat.id)
    if existing and existing.phase != Phase.FINISHED:
        await message.answer("🏏 A match is already active here.")
        return
    await users.ensure(message.from_user)
    player = p(message)
    match = Match(message.chat.id, player, max_overs=2, balls_per_over=3)
    matches.create(match)
    await persist_live(db, matches, match)
    await message.answer(
        "🏏 <b>1v1 CRICKET LOBBY</b>\n\n"
        "🎯 2 overs • 3 legal balls/over\n"
        f"👤 {mention(player.uid, player.name)}\n\n"
        "Type /join to enter.\n"
        "⏳ Waiting for opponent...",
        parse_mode="HTML",
    )


@router.message(Command("teamplay"))
async def teamplay(message: Message, matches, users, teams, admin, db):
    """Create a team-v-team lobby using the captain's existing Playing XI."""
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("👥 Team matches work inside groups.")
        return

    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    if matches.get(message.chat.id):
        await message.answer("🏏 A match is already active here.")
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            "Usage: <code>/teamplay TEAM_NAME [OVERS]</code>\n"
            "Example: <code>/teamplay Tigers 5</code>",
            parse_mode="HTML",
        )
        return

    team_name = " ".join(parts[1:-1]) if len(parts) > 2 and parts[-1].isdigit() else " ".join(parts[1:])
    overs = int(parts[-1]) if len(parts) > 2 and parts[-1].isdigit() else 2
    if overs not in {1, 2, 5, 10, 20}:
        await message.answer("Overs must be 1, 2, 5, 10 or 20.")
        return

    team = await teams.my_team(message.chat.id, message.from_user.id)
    if not team or team.get("name_key") != teams.key(team_name):
        team = await teams.get(message.chat.id, team_name)
    if not team or team.get("captain") != message.from_user.id:
        await message.answer("❌ You must be the captain of that team.")
        return
    if not _team_ready(team):
        await message.answer(
            "❌ Playing XI is not set. Captain must set exactly 11 players:\n"
            "<code>/team xi set ID1 ID2 ... ID11</code>",
            parse_mode="HTML",
        )
        return

    await users.ensure(message.from_user)
    captain = p(message)
    xi = _team_players(team)

    match = Match(
        message.chat.id,
        captain,
        max_overs=overs,
        balls_per_over=6,
        team_mode=True,
        team_a_name=team["name"],
        team_a=xi,
        team_a_captain=_team_captain(team),
    )
    matches.create(match)
    await persist_live(db, matches, match)

    await message.answer(
        "🏏 <b>TEAM MATCH LOBBY</b>\n\n"
        f"🏏 Team A: <b>{team['name']}</b>\n"
        f"👑 Captain: {mention(captain.uid, captain.name)}\n"
        f"👥 Playing XI: <b>11</b>\n"
        f"🎯 {overs} overs • 6 legal balls/over\n\n"
        "Opponent captain: use <code>/join</code> after creating your team and XI.",
        parse_mode="HTML",
    )


@router.message(Command("join"))
async def join(message: Message, matches, users, admin, db, bot, teams):
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("👥 Join matches from the group.")
        return
    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    match = matches.get(message.chat.id)
    if not match:
        await message.answer("❌ No lobby. Use /play or /teamplay.")
        return
    if match.opponent:
        await message.answer("❌ Match is full.")
        return
    if message.from_user.id == match.creator.uid:
        await message.answer("❌ You are already in the match.")
        return

    await users.ensure(message.from_user)

    if match.team_mode:
        team = await teams.my_team(message.chat.id, message.from_user.id)
        if not team:
            await message.answer("❌ You must belong to a team.")
            return
        if team["captain"] != message.from_user.id:
            await message.answer("❌ Only the team captain can join a team match.")
            return
        if not _team_ready(team):
            await message.answer("❌ Your team has no valid Playing XI of 11.")
            return
        if team["name"] == match.team_a_name:
            await message.answer("❌ Choose a different team.")
            return

        match.opponent = p(message)
        match.team_b_name = team["name"]
        match.team_b = _team_players(team)
        match.team_b_captain = _team_captain(team)
    else:
        match.opponent = p(message)

    CricketEngine().start(match)
    await persist_live(db, matches, match)

    i = match.innings
    dm_ok = await send_bowler_dm(bot, match)
    await message.answer(
        "🏏 <b>MATCH STARTED!</b>\n\n"
        + (
            f"🏏 <b>{match.team_a_name}</b> 🆚 <b>{match.team_b_name}</b>\n\n"
            if match.team_mode
            else f"{mention(match.creator.uid, match.creator.name)} 🆚 {mention(match.opponent.uid, match.opponent.name)}\n\n"
        )
        + "🪙 Toss complete!\n\n"
        f"🏏 Striker: <b>{i.batter.name}</b>\n"
        + (f"🏏 Non-striker: <b>{i.non_striker.name}</b>\n" if i.non_striker else "")
        + f"🎯 Bowler: <b>{i.bowler.name}</b>\n\n"
        "⚾ <b>BALL 0.1</b>\n"
        "Batting captain, send <b>1–6 in the group</b>.\n\n"
        + ("🎯 Bowling captain has been sent the private menu." if dm_ok
           else "⚠️ Bowling captain must open the bot in DM and send /start."),
        parse_mode="HTML",
    )


@router.message(Command("solo"))
async def solo(message: Message, matches, users, admin, db):
    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    if matches.get(message.chat.id):
        await message.answer("🏏 A match is already active.")
        return
    await users.ensure(message.from_user)
    user = p(message)
    ai = Player(-1, "Cricket Bot AI")
    match = Match(message.chat.id, user, ai, max_overs=2, balls_per_over=3)
    matches.create(match)
    CricketEngine().start(match)
    match.innings.batter = user
    match.innings.bowler = ai
    match.innings.batting_team = [user]
    match.innings.bowling_team = [ai]
    match.innings.batting_captain = user
    match.innings.bowling_captain = ai
    await persist_live(db, matches, match)
    await message.answer(
        "🤖 <b>SOLO MODE</b>\n\n"
        "You 🆚 Cricket Bot AI\n"
        "🎯 2 overs • 3 legal balls/over\n\n"
        "⚾ BALL 0.1\nSend your batting number <b>1–6</b> in the group.",
        parse_mode="HTML",
    )


@router.message(Command("custom"))
async def custom(message: Message, matches, users, admin, db):
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("👥 Use /custom inside a group.")
        return
    await admin.register_chat(message.chat.id, message.chat.type, getattr(message.chat, "title", None))
    parts = (message.text or "").split()
    overs = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
    if overs not in {1, 2, 5, 10, 20}:
        await message.answer("Use: /custom <1|2|5|10|20>\nExample: /custom 10")
        return
    if matches.get(message.chat.id):
        await message.answer("🏏 A match is already active.")
        return
    await users.ensure(message.from_user)
    match = Match(message.chat.id, p(message), max_overs=overs, balls_per_over=6)
    matches.create(match)
    await persist_live(db, matches, match)
    await message.answer(
        f"🏏 <b>CUSTOM MATCH</b>\n\n"
        f"🎯 {overs} overs • 6 legal balls/over\n"
        f"👤 {message.from_user.full_name}\n\n"
        "Type /join to enter.",
        parse_mode="HTML",
    )


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
    extra = ""
    if match.team_mode:
        extra = (
            f"🏏 Teams: <b>{match.team_a_name}</b> 🆚 <b>{match.team_b_name}</b>\n"
            f"🏏 Striker: <b>{i.batter.name}</b>\n"
            f"🏏 Non-striker: <b>{i.non_striker.name if i.non_striker else '—'}</b>\n"
        )
    else:
        extra = f"🏏 Batter: <b>{i.batter.name}</b>\n"
    await message.answer(
        "🏏 <b>LIVE SCORE</b>\n\n"
        + extra
        + f"📊 Score: <b>{score_text(match)}</b>\n"
        f"🎯 Bowler: <b>{i.bowler.name}</b>\n"
        f"⚾ Legal balls: <b>{i.balls}/{match.max_overs * match.balls_per_over}</b>\n"
        + (f"🎯 Target: <b>{match.target}</b>" if match.target else ""),
        parse_mode="HTML",
    )


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

    if match.opponent and match.opponent.uid != -1:
        if match.pending_bat is not None:
            await message.answer("⏳ Bowler is choosing a delivery in DM.")
            return

        controller = batting_controller(match)
        if not controller or uid != controller.uid:
            await message.answer("⏳ Only the current batting captain can submit the shot.")
            return

        match.pending_bat = int(text)
        match.phase = Phase.BOWL
        match.touch()
        await persist_live(db, matches, match)

        dm_ok = await send_bowler_dm(bot, match)
        if not dm_ok:
            match.pending_bat = None
            match.phase = Phase.BAT
            await persist_live(db, matches, match)
            controller = bowling_controller(match)
            await message.answer(
                f"⚠️ {mention(controller.uid, controller.name)}, I couldn't DM you.\n"
                "Open the bot privately, send /start, then try the ball again.",
                parse_mode="HTML",
            )
        else:
            await message.answer(
                f"🏏 {i.batter.name} chose <b>{text}</b>.\n"
                f"🎯 {i.bowler.name} is choosing the delivery privately.",
                parse_mode="HTML",
            )
        return

    if match.opponent and match.opponent.uid == -1 and i.batting_captain and i.batting_captain.uid == uid:
        engine = CricketEngine()
        bat = int(text)
        bowl = CricketAI.choose()
        batter_name = i.batter.name
        bowler_name = i.bowler.name
        result = engine.play(match, bat, bowl, settings.owner_id)
        await persist_live(db, matches, match)
        await message.answer(
            f"{result.text}\n\n"
            f"🤖 AI delivery: <b>{result.ball_type}</b>\n"
            f"🏏 Batter: <b>{batter_name}</b> • Bowler: <b>{bowler_name}</b>\n"
            f"📊 Score: <b>{score_text(match)}</b>",
            parse_mode="HTML",
        )
        if engine.innings_complete(match):
            if match.innings_no == 1:
                engine.switch(match)
                await persist_live(db, matches, match)
                await message.answer(
                    "━━━━━━━━━━━━━━\n🏁 <b>INNINGS OVER</b>\n\n"
                    f"🎯 Target: <b>{match.target}</b>\n\n"
                    "🤖 AI is batting.\n🎯 Send your bowling choice privately to the bot:\n\n"
                    + bowling_menu(),
                    parse_mode="HTML",
                )
            return
        match.phase = Phase.BAT
        match.touch()
        await persist_live(db, matches, match)
        await _announce_next_ball(bot, match)
        return


async def _dm_bowling_input(message, matches, users, db, settings, bot):
    if message.chat.type != "private":
        return
    text = (message.text or "").strip()
    if text not in {"1", "2", "3", "4", "5", "6"}:
        return

    # The actual Telegram controller is either the current bowler (1v1) or
    # the bowling captain (team match).
    match = next(
        (
            m for m in matches.all()
            if m.opponent and m.innings
            and bowling_controller(m)
            and bowling_controller(m).uid == message.from_user.id
            and m.pending_bat is not None
            and m.phase == Phase.BOWL
        ),
        None,
    )
    if not match:
        await message.answer("🏏 No active bowling turn for you.")
        return

    if settings.turn_timeout > 0 and time.time() - match.turn_started_at > settings.turn_timeout:
        await message.answer("⏰ Your bowling turn timed out.")
        winner = batting_controller(match).uid
        await bot.send_message(
            match.chat_id,
            "⏰ <b>BOWLING TIMEOUT</b> — the bowling side lost the turn.",
            parse_mode="HTML",
        )
        await _finish_match_to_chat(bot, match, users, db, matches, winner)
        return

    bat = match.pending_bat
    bowl = int(text)
    match.pending_bat = None

    engine = CricketEngine()
    batter_name = match.innings.batter.name
    bowler_name = match.innings.bowler.name
    result = engine.play(match, bat, bowl, settings.owner_id)
    await persist_live(db, matches, match)

    await message.answer(
        f"🔒 <b>Delivery sent privately</b>\n\n"
        f"{result.ball_emoji} {result.ball_type}\n"
        "The result has been posted in the group.",
        parse_mode="HTML",
    )

    i = match.innings
    await bot.send_message(
        match.chat_id,
        "━━━━━━━━━━━━━━\n"
        f"⚾ <b>BALL {i.over(match.balls_per_over)}</b>\n\n"
        f"🏏 Batter: <b>{batter_name}</b>\n"
        f"🎯 Bowler: <b>{bowler_name}</b>\n"
        f"🎯 Delivery: <b>{result.ball_type}</b>\n"
        f"{result.text}\n\n"
        f"📊 Score: <b>{score_text(match)}</b>",
        parse_mode="HTML",
    )

    await _complete_after_delivery(bot, match, engine, users, db, matches)


@router.message()
async def number_input(message: Message, matches, users, db, settings, bot):
    if message.chat.type == "private":
        async with _match_lock(message.from_user.id):
            await _dm_bowling_input(message, matches, users, db, settings, bot)
    elif message.chat.type in {"group", "supergroup"}:
        async with _match_lock(message.chat.id):
            await _group_number_input(message, matches, users, db, settings, bot)
