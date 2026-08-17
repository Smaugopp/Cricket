import logging
from aiogram import Router
from aiogram.types import ErrorEvent

router = Router()
logger = logging.getLogger("cricket")

@router.error()
async def global_error(event: ErrorEvent, bot, settings):
    exc = event.exception
    logger.error("Unhandled Telegram update error", exc_info=(type(exc), exc, exc.__traceback__))
    try:
        await bot.send_message(
            settings.owner_id,
            "⚠️ <b>Cricket Bot Error</b>\n\n"
            f"<code>{type(event.exception).__name__}: {event.exception}</code>",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Could not notify owner about error")
    return True
