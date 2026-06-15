from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from ai_analyzer import AIAnalyzer
from config import load_config
from db import Database
from handlers import admin, bug_submission, callbacks, start
from handlers.admin import broadcast_backup

BACKUP_INTERVAL_SECONDS = 24 * 60 * 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("bot")


async def _daily_backup_loop(
    bot: Bot, db: Database, super_admin_ids: tuple[int, ...]
) -> None:
    """Send a fresh DB snapshot to every super admin once a day."""
    while True:
        await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
        try:
            await broadcast_backup(bot, db, super_admin_ids)
            logger.info("Daily backup sent to %d super admin(s).", len(super_admin_ids))
        except Exception:
            logger.exception("Daily backup loop iteration failed")


async def main() -> None:
    config = load_config()

    if not config.super_admin_ids:
        logger.warning(
            "SUPER_ADMIN_IDS (and legacy ADMIN_IDS) are empty — admin commands "
            "(/panel, /bugs, /add_admin, /backup, ...) will not respond to anyone."
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
    dp["super_admin_ids"] = config.super_admin_ids

    admin_router = admin.setup(config.super_admin_ids, db)
    callbacks_router = callbacks.setup(config.super_admin_ids, db)

    dp.include_router(start.router)
    dp.include_router(admin_router)
    dp.include_router(callbacks_router)
    dp.include_router(bug_submission.router)

    backup_task = asyncio.create_task(
        _daily_backup_loop(bot, db, config.super_admin_ids)
    )

    try:
        me = await bot.get_me()
        logger.info("Starting bot as @%s (id=%s)", me.username, me.id)
        await dp.start_polling(
            bot, allowed_updates=dp.resolve_used_update_types()
        )
    finally:
        backup_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
