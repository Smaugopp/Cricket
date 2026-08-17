import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from app.config import get_settings
from app.db import Database
from app.game.manager import MatchManager
from app.services.users import UserService
from app.services.admin import AdminService
from app.services.teams import TeamService
from app.services.leagues import LeagueService
from app.services.tournaments import TournamentService
from app.handlers.core import router as core_router
from app.handlers.game import router as game_router
from app.handlers.team import router as team_router
from app.handlers.profile import router as profile_router
from app.handlers.admin import router as admin_router
from app.handlers.tournament import router as tournament_router
from app.handlers.league import router as league_router
from app.handlers.commands import router as commands_router
from app.handlers.errors import router as errors_router

async def run():
    logging.basicConfig(level=logging.INFO)
    settings=get_settings()
    db=Database(settings.mongo_uri,settings.mongo_db)
    await db.ping(); await db.indexes()
    bot=Bot(settings.bot_token,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp=Dispatcher()
    matches=MatchManager()
    # Restore active matches saved before a VPS/container restart.
    for live in await db.live_matches.find({}).to_list(length=10000):
        try:
            matches.create(MatchManager.deserialize(live))
        except Exception:
            logging.exception("Could not restore live match %s", live.get("chat_id"))
            await db.live_matches.delete_one({"chat_id": live.get("chat_id")})
    users=UserService(db)
    admin=AdminService(db,settings.owner_id)
    teams=TeamService(db)
    leagues=LeagueService(db)
    tournaments=TournamentService(db)
    dp["settings"]=settings; dp["db"]=db; dp["matches"]=matches; dp["users"]=users
    dp["admin"]=admin; dp["teams"]=teams; dp["leagues"]=leagues; dp["tournaments"]=tournaments
    dp.include_router(errors_router); dp.include_router(core_router); dp.include_router(game_router); dp.include_router(team_router)
    dp.include_router(profile_router); dp.include_router(admin_router); dp.include_router(tournament_router); dp.include_router(league_router); dp.include_router(commands_router)
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands([
        BotCommand(command="start", description="Open Cricket Arena"),
        BotCommand(command="commands", description="All commands"),
        BotCommand(command="play", description="Create a multiplayer match"),
        BotCommand(command="join", description="Join the current 1v1 match"),
        BotCommand(command="teamplay", description="Start a team match"),
        BotCommand(command="teamjoin", description="Join a team-match lobby"),
        BotCommand(command="cancel", description="Cancel active match"),
        BotCommand(command="solo", description="Play against AI"),
        BotCommand(command="score", description="Live score"),
        BotCommand(command="profile", description="Career profile"),
        BotCommand(command="teams", description="Group teams"),
        BotCommand(command="tournament", description="Knockout tournaments"),
        BotCommand(command="league", description="League competitions"),
        BotCommand(command="leaderboard", description="Player leaderboard"),
        BotCommand(command="daily", description="Daily reward"),
        BotCommand(command="help", description="How to play"),
    ])
    logging.info("Cricket bot started | owner=%s | group support enabled",settings.owner_id)

    async def watchdog():
        while True:
            try:
                await asyncio.sleep(15)
                for match in matches.expired():
                    matches.remove(match.chat_id)
                    await db.live_matches.delete_one({"chat_id": match.chat_id})
            except asyncio.CancelledError:
                return
            except Exception:
                logging.exception("watchdog error")

    task=asyncio.create_task(watchdog())
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()
        await bot.session.close()
        await db.close()
