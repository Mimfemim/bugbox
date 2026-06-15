from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from ai_analyzer import AIAnalyzer
from db import Database
from handlers.admin import format_bug, reanalyze_pending, send_csv, send_xlsx
from keyboards import status_keyboard

logger = logging.getLogger(__name__)

router = Router(name="callbacks")


def _admin_filter_factory(admin_ids: tuple[int, ...]):
    async def is_admin(callback: CallbackQuery) -> bool:
        return bool(callback.from_user and callback.from_user.id in admin_ids)

    return is_admin


def setup(admin_ids: tuple[int, ...]) -> Router:
    router.callback_query.filter(_admin_filter_factory(admin_ids))
    return router


@router.callback_query(F.data.startswith("status:"))
async def on_status_change(callback: CallbackQuery, db: Database) -> None:
    if not callback.data:
        await callback.answer("Invalid payload", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Invalid payload", show_alert=True)
        return

    try:
        bug_id = int(parts[1])
    except ValueError:
        await callback.answer("Invalid bug id", show_alert=True)
        return

    new_status = parts[2]
    ok = await db.update_status(bug_id, new_status)
    if not ok:
        await callback.answer("❌ Update failed", show_alert=True)
        return

    bug = await db.get_bug(bug_id)
    if bug and callback.message:
        try:
            await callback.message.edit_text(
                format_bug(bug),
                reply_markup=status_keyboard(
                    bug_id, has_media=bool(bug.get("telegram_file_id"))
                ),
            )
        except Exception as exc:
            logger.warning("Could not edit message: %s", exc)

    await callback.answer(f"✅ Status → {new_status}")


@router.callback_query(F.data == "panel:latest")
async def on_panel_latest(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    if not callback.message:
        return
    bugs = await db.list_latest(20)
    if not bugs:
        await callback.message.answer("هنوز هیچ باگی ثبت نشده.")
        return
    await callback.message.answer(f"📋 {len(bugs)} گزارش آخر:")
    for bug in bugs:
        await callback.message.answer(
            format_bug(bug),
            reply_markup=status_keyboard(
                bug["id"], has_media=bool(bug.get("telegram_file_id"))
            ),
        )


@router.callback_query(F.data == "panel:critical")
async def on_panel_critical(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    if not callback.message:
        return
    bugs = await db.list_by_severity("Critical", 50)
    if not bugs:
        await callback.message.answer("🎉 هیچ باگ Critical نداریم.")
        return
    await callback.message.answer(f"🚨 {len(bugs)} باگ Critical:")
    for bug in bugs:
        await callback.message.answer(
            format_bug(bug),
            reply_markup=status_keyboard(
                bug["id"], has_media=bool(bug.get("telegram_file_id"))
            ),
        )


@router.callback_query(F.data == "panel:csv")
async def on_panel_csv(callback: CallbackQuery, db: Database) -> None:
    await callback.answer("در حال آماده‌سازی CSV...")
    if callback.message:
        await send_csv(callback.message, db)


@router.callback_query(F.data == "panel:xlsx")
async def on_panel_xlsx(callback: CallbackQuery, db: Database) -> None:
    await callback.answer("در حال آماده‌سازی Excel...")
    if callback.message:
        await send_xlsx(callback.message, db)


@router.callback_query(F.data == "panel:reanalyze")
async def on_panel_reanalyze(
    callback: CallbackQuery, db: Database, analyzer: AIAnalyzer
) -> None:
    await callback.answer("♻️ شروع تحلیل دوباره...")
    if callback.message:
        await reanalyze_pending(callback.message, db, analyzer)


async def _resend_media(message, media_type: str, file_id: str, caption: str) -> None:
    senders = {
        "photo": message.answer_photo,
        "video": message.answer_video,
        "video_note": message.answer_video_note,
        "voice": message.answer_voice,
        "audio": message.answer_audio,
        "animation": message.answer_animation,
        "sticker": message.answer_sticker,
    }
    sender = senders.get(media_type)
    if sender is None:
        await message.answer_document(file_id, caption=caption)
    elif media_type in ("video_note", "sticker"):
        # these methods don't accept a caption
        await sender(file_id)
        await message.answer(caption)
    else:
        await sender(file_id, caption=caption)


@router.callback_query(F.data.startswith("media:"))
async def on_view_media(callback: CallbackQuery, db: Database) -> None:
    if not callback.data:
        await callback.answer("Invalid payload", show_alert=True)
        return
    try:
        bug_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Invalid bug id", show_alert=True)
        return

    bug = await db.get_bug(bug_id)
    if not bug or not bug.get("telegram_file_id"):
        await callback.answer("این گزارش فایلی نداره.", show_alert=True)
        return

    await callback.answer("📎 در حال ارسال فایل...")
    if not callback.message:
        return

    caption = f"📎 فایل BUG-{bug_id}"
    try:
        await _resend_media(
            callback.message,
            bug.get("media_type") or "document",
            bug["telegram_file_id"],
            caption,
        )
    except Exception as exc:
        logger.warning("Could not resend media for BUG-%s: %s", bug_id, exc)
        await callback.message.answer(
            f"❌ ارسال فایل BUG-{bug_id} ممکن نشد (شاید فایل روی تلگرام منقضی شده)."
        )
