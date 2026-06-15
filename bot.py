from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from ai_analyzer import AIAnalyzer
from config import load_config
from db import Database
from handlers import admin, bug_submission, callbacks, start

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("bot")


async def main() -> None:
    config = load_config()

    if not config.admin_ids:
        logger.warning(
            "ADMIN_IDS is empty — admin commands (/panel, /bugs, /export_*) "
            "will not respond to anyone."
        )

    db = Database(config.db_path)
    await db.init()

    analyzer = AIAnalyzer(
        api_key=config.openai_api_key,
        model=config.openai_model,
        base_url=config.openai_base_url,
    )
    if config.openai_base_url:
        logger.info(
            "Using custom OpenAI-compatible endpoint: %s (model=%s)",
            config.openai_base_url,
            config.openai_model,
        )

    bot = Bot(token=config.bot_token)
    dp = Dispatcher()

    dp["db"] = db
    dp["analyzer"] = analyzer

    admin_router = admin.setup(config.admin_ids)
    callbacks_router = callbacks.setup(config.admin_ids)

    dp.include_router(start.router)
    dp.include_router(admin_router)
    dp.include_router(callbacks_router)
    dp.include_router(bug_submission.router)

    try:
        me = await bot.get_me()
        logger.info("Starting bot as @%s (id=%s)", me.username, me.id)
        await dp.start_polling(
            bot, allowed_updates=dp.resolve_used_update_types()
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
