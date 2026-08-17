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

# One lock per active chat/match. It prevents two concurrent ball submissions
# from being processed as the same delivery.
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
        "🔒 Your number stays private; the result is posted in the group."
    )

async def send_bowler_dm(bot, match):
    try:
        await bot.send_message(match.innings.bowler.uid, bowling_menu())
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

async def _finish_match(message, match, users, db, matches, winner):
    i = match.innings
    if winner == 0:
        await users.record_match(
            match.creator.uid, tied=True,
            runs=i.runs if i and i.batter.uid == match.creator.uid else 0,
            wickets=i.wickets if i and i.bowler.uid == match.creator.uid else 0,
            balls=i.balls if i else 0, fours=i.fours if i else 0,
            sixes=i.sixes if i else 0, dots=i.dots if i else 0
        )
        await users.record_match(
            match.opponent.uid, tied=True,
            runs=i.runs if i and i.batter.uid == match.opponent.uid else 0,
            wickets=i.wickets if i and i.bowler.uid == match.opponent.uid else 0,
            balls=i.balls if i else 0, fours=i.fours if i else 0,
            sixes=i.sixes if i else 0, dots=i.dots if i else 0
        )
        winner_name = "Tie"
    else:
        winner_name = name(match, winner)
        loser = match.opponent.uid if winner == match.creator.uid else match.creator.uid
        await users.record_match(
            winner, won=True,
            runs=i.runs if i and i.batter.uid == winner else 0,
            wickets=i.wickets if i and i.bowler.uid == winner else 0,
            balls=i.balls if i else 0, fours=i.fours if i else 0,
            sixes=i.sixes if i else 0, dots=i.dots if i else 0
        )
        if loser != -1:
            await users.record_match(
                loser, lost=True,
                runs=i.runs if i and i.batter.uid == loser else 0,
                wickets=i.wickets if i and i.bowler.uid == loser else 0,
                balls=i.balls if i else 0, fours=i.fours if i else 0,
                sixes=i.sixes if i else 0, dots=i.dots if i else 0
            )

    await db.matches.insert_one({
        "chat_id": match.chat_id,
        "players": [match.creator.uid, match.opponent.uid],
        "winner": winner,
        "first_score": match.first_score,
        "second_score": i.runs if i and match.innings_no == 2 else None,
        "overs": match.max_overs,
        "balls_per_over": match.balls_per_over,
        "created_at": __import__("app.utils", fromlist=["now"]).now(),
    })

    await message.answer(
        "━━━━━━━━━━━━━━\n"
        "🏆 <b>MATCH SUMMARY</b>\n\n"
        f"🏏 First innings: <b>{match.first_score or 0}</b>\n"
        f"🏏 Second innings: <b>{i.runs if i else 0}/{i.wickets if i else 0}</b>\n\n"
        f"🏆 <b>RESULT: {winner_name}</b>",
        parse_mode="HTML"
    )
    await clear_live(db, match.chat_id)
    matches.remove(match.chat_id)
    _drop_match_lock(match.chat_id)

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
        "🏏 <b>CRICKET MATCH LOBBY</b>\n\n"
        "🎯 2 overs • 3 legal balls/over\n"
        f"👤 {mention(player.uid, player.name)}\n\n"
        "Type /join to enter.\n"
        "⏳ Waiting for opponent...",
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
        await message.answer("❌ No lobby. Use /play.")
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
    dm_ok = await send_bowler_dm(bot, match)
    await message.answer(
        "🏏 <b>MATCH STARTED!</b>\n\n"
        f"{mention(match.creator.uid, match.creator.name)} 🆚 "
        f"{mention(match.opponent.uid, match.opponent.name)}\n\n"
        "🪙 Toss complete!\n\n"
        f"🏏 Batting: <b>{i.batter.name}</b>\n"
        f"🎯 Bowling: <b>{i.bowler.name}</b>\n\n"
        "⚾ <b>BALL 1</b>\n"
        f"{i.batter.name}, send <b>1–6</b> <b>here in the group</b>.\n\n"
        + ("🎯 Bowler has been sent the private bowling menu." if dm_ok
           else "⚠️ Bowler must open the bot in DM and send /start before private bowling can begin."),
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
    await persist_live(db, matches, match)
    await message.answer(
        "🤖 <b>SOLO MODE</b>\n\n"
        "You 🆚 Cricket Bot AI\n"
        "🎯 2 overs • 3 legal balls/over\n\n"
        "⚾ BALL 1\nSend your batting number <b>1–6</b> in the group.",
        parse_mode="HTML",
    )

@router.message(Command("custom"))
async def custom(message: Message, matches, users, admin, db):
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
    await message.answer(
        f"🏏 <b>LIVE SCORE</b>\n\n"
        f"🏏 {i.batter.name}: <b>{score_text(match)}</b>\n"
        f"🎯 Bowler: {i.bowler.name}\n"
        f"⚾ Legal balls: {i.balls}/{match.max_overs * match.balls_per_over}\n"
        + (f"🎯 Target: {match.target}" if match.target else ""),
        parse_mode="HTML",
    )

async def _group_number_input(message: Message, matches, users, db, settings, bot):
    # Batting input is intentionally accepted only in a group/supergroup.
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
        if uid != i.batter.uid:
            await message.answer("⏳ Wait for the current batter.")
            return

        match.pending_bat = int(text)
        match.phase = Phase.BOWL
        match.touch()
        await persist_live(db, matches, match)

        dm_ok = await send_bowler_dm(bot, match)
        if not dm_ok:
            await message.answer(
                f"⚠️ {mention(i.bowler.uid, i.bowler.name)}, I couldn't DM you.\n"
                "Open the bot privately, send /start, then wait for the bowling prompt.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"🏏 {i.batter.name} chose <b>{text}</b>.\n"
                f"🎯 {i.bowler.name} is choosing the delivery privately.",
                parse_mode="HTML"
            )
        return

    # Solo: batting is group input, AI delivery is private logic handled here.
    if match.opponent and match.opponent.uid == -1 and i.batter.uid == uid:
        engine = CricketEngine()
        bat = int(text)
        bowl = CricketAI.choose()
        result = engine.play(match, bat, bowl, settings.owner_id)
        await persist_live(db, matches, match)
        await message.answer(
            f"{result.text}\n\n"
            f"🤖 AI delivery: <b>{result.ball_type}</b>\n"
            f"🏏 Your score: <b>{score_text(match)}</b>\n"
            f"⚾ Ball {match.innings.balls}/{match.max_overs * match.balls_per_over}",
            parse_mode="HTML"
        )
        if engine.innings_complete(match):
            engine.switch(match)
            await persist_live(db, matches, match)
            await message.answer(
                "━━━━━━━━━━━━━━\n🏁 <b>INNINGS OVER</b>\n\n"
                f"🎯 Target: <b>{match.target}</b>\n\n"
                "🤖 AI is batting.\n"
                "🎯 Send your bowling choice privately to the bot:\n\n"
                + bowling_menu(),
                parse_mode="HTML"
            )
        return

async def _dm_bowling_input(message: Message, matches, users, db, settings, bot):
    # Private DM: only the current bowler can submit a delivery number.
    if message.chat.type != "private":
        return
    text = (message.text or "").strip()
    if text not in {"1", "2", "3", "4", "5", "6"}:
        return

    match = next(
        (
            m for m in matches.all()
            if m.opponent and m.innings
            and m.innings.bowler.uid == message.from_user.id
            and m.pending_bat is not None
            and m.phase == Phase.BOWL
        ),
        None
    )
    if not match:
        await message.answer("🏏 No active bowling turn for you.")
        return

    if settings.turn_timeout > 0 and time.time() - match.turn_started_at > settings.turn_timeout:
        await message.answer("⏰ Your bowling turn timed out.")
        winner = match.innings.batter.uid
        if winner == -1:
            winner = match.innings.bowler.uid
        await bot.send_message(
            match.chat_id,
            "⏰ <b>BOWLING TIMEOUT</b> — the bowler lost the turn.",
            parse_mode="HTML"
        )
        await _finish_match_to_chat(bot, match, users, db, matches, winner)
        return

    bat = match.pending_bat
    bowl = int(text)
    match.pending_bat = None
    engine = CricketEngine()
    result = engine.play(match, bat, bowl, settings.owner_id)
    await persist_live(db, matches, match)

    # In solo mode, keep the user's bowling choice private and let the AI
    # receive the batter number internally.
    if match.opponent.uid == -1:
        await message.answer(
            f"🔒 <b>Delivery sent privately</b>\n\n"
            f"{result.ball_emoji} {result.ball_type}\n"
            "The result has been posted in the group.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"🔒 <b>Delivery sent privately</b>\n\n"
            f"{result.ball_emoji} {result.ball_type}\n"
            "The result has been posted in the group.",
            parse_mode="HTML"
        )

    await bot.send_message(
        match.chat_id,
        "━━━━━━━━━━━━━━\n"
        f"⚾ <b>BALL {match.innings.over(match.balls_per_over)}</b>\n\n"
        f"🏏 Batter: <b>{match.innings.batter.name}</b>\n"
        f"🎯 Delivery: <b>{result.ball_type}</b>\n"
        f"{result.text}\n\n"
        f"📊 Score: <b>{score_text(match)}</b>",
        parse_mode="HTML"
    )

    if engine.innings_complete(match):
        if match.innings_no == 1:
            engine.switch(match)
            await persist_live(db, matches, match)
            await bot.send_message(
                match.chat_id,
                "━━━━━━━━━━━━━━\n🏁 <b>INNINGS OVER</b>\n\n"
                f"🎯 Target: <b>{match.target}</b>\n\n"
                f"🏏 {match.innings.batter.name} is batting.\n"
                "Send your batting number <b>1–6 in the group</b>.",
                parse_mode="HTML"
            )
            if match.innings.bowler.uid != -1:
                dm_ok = await send_bowler_dm(bot, match)
                if not dm_ok:
                    await bot.send_message(
                        match.chat_id,
                        f"⚠️ {mention(match.innings.bowler.uid, match.innings.bowler.name)}, "
                        "open the bot in DM and send /start for private bowling."
                    )
            return

        winner = engine.winner(match)
        # Summary helper expects a Message-like object; send directly because
        # the actual turn happened in DM.
        await _finish_match_to_chat(bot, match, users, db, matches, winner)
        return

    match.phase = Phase.BAT
    match.touch()
    await persist_live(db, matches, match)
    await bot.send_message(
        match.chat_id,
        f"⚾ <b>NEXT BALL</b>\n"
        f"{match.innings.batter.name}, send <b>1–6 in the group</b>.",
        parse_mode="HTML"
    )

async def _finish_match_to_chat(bot, match, users, db, matches, winner):
    i = match.innings
    if winner == 0:
        winner_name = "Tie"
        await users.record_match(match.creator.uid, tied=True)
        await users.record_match(match.opponent.uid, tied=True)
    else:
        winner_name = name(match, winner)
        loser = match.opponent.uid if winner == match.creator.uid else match.creator.uid
        await users.record_match(winner, won=True)
        if loser != -1:
            await users.record_match(loser, lost=True)

    await db.matches.insert_one({
        "chat_id": match.chat_id,
        "players": [match.creator.uid, match.opponent.uid],
        "winner": winner,
        "first_score": match.first_score,
        "second_score": i.runs if i else None,
        "overs": match.max_overs,
        "balls_per_over": match.balls_per_over,
        "created_at": __import__("app.utils", fromlist=["now"]).now(),
    })
    await bot.send_message(
        match.chat_id,
        "━━━━━━━━━━━━━━\n🏆 <b>MATCH SUMMARY</b>\n\n"
        f"🏏 First innings: <b>{match.first_score or 0}</b>\n"
        f"🏏 Second innings: <b>{i.runs if i else 0}/{i.wickets if i else 0}</b>\n\n"
        f"🏆 <b>RESULT: {winner_name}</b>",
        parse_mode="HTML"
    )
    await clear_live(db, match.chat_id)
    matches.remove(match.chat_id)
    _drop_match_lock(match.chat_id)


@router.message()
async def number_input(message: Message, matches, users, db, settings, bot):
    # One catch-all dispatcher is used so aiogram never consumes a DM update
    # before the private bowling handler gets a chance to process it.
    if message.chat.type == "private":
        # A private DM may correspond to exactly one active bowling turn.
        # The match is resolved inside the handler; serialize all DM inputs.
        async with _match_lock(message.from_user.id):
            await _dm_bowling_input(message, matches, users, db, settings, bot)
    elif message.chat.type in {"group", "supergroup"}:
        # Serialize group batting input for this match/chat.
        async with _match_lock(message.chat.id):
            await _group_number_input(message, matches, users, db, settings, bot)
