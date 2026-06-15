from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from ai_analyzer import AIAnalyzer
from db import ANONYMOUS_NAME, Database
from handlers.admin import (
    admins_text,
    format_bug,
    reanalyze_pending,
    send_backup,
    send_csv,
    send_panel,
    send_xlsx,
)
from keyboards import delete_confirm_keyboard, status_keyboard

logger = logging.getLogger(__name__)

router = Router(name="callbacks")


def _is_super(callback: CallbackQuery, super_admin_ids: tuple[int, ...]) -> bool:
    return bool(callback.from_user and callback.from_user.id in super_admin_ids)


def _admin_filter_factory(super_admin_ids: tuple[int, ...], db: Database):
    async def is_admin(callback: CallbackQuery) -> bool:
        user = callback.from_user
        if user is None:
            return False
        if user.id in super_admin_ids:
            return True
        return await db.is_admin(user.id)

    return is_admin


def setup(super_admin_ids: tuple[int, ...], db: Database) -> Router:
    router.callback_query.filter(_admin_filter_factory(super_admin_ids, db))
    return router


@router.callback_query(F.data.startswith("status:"))
async def on_status_change(
    callback: CallbackQuery, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
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
                    bug_id,
                    has_media=bool(bug.get("telegram_file_id")),
                    is_super=_is_super(callback, super_admin_ids),
                ),
            )
        except Exception as exc:
            logger.warning("Could not edit message: %s", exc)

    await callback.answer(f"✅ Status → {new_status}")


@router.callback_query(F.data.startswith("admin:"))
async def on_admin_menu(
    callback: CallbackQuery, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
    if not callback.data or not callback.from_user:
        await callback.answer("Invalid payload", show_alert=True)
        return
    if callback.from_user.id not in super_admin_ids:
        await callback.answer("فقط سوپرادمین.", show_alert=True)
        return

    action = callback.data.split(":", 1)[1]
    msg = callback.message

    if action == "panel":
        await callback.answer()
        if msg:
            await send_panel(msg, db)
    elif action == "list":
        await callback.answer()
        if msg:
            await msg.answer(await admins_text(db, super_admin_ids))
    elif action == "add_help":
        await callback.answer()
        if msg:
            await msg.answer(
                "➕ افزودن ادمین:\n`/add_admin <آیدی عددی> [نام]`\n\n"
                "ادمین جدید آیدی عددیش رو با دستور /myid می‌بینه."
            )
    elif action == "remove_help":
        await callback.answer()
        if msg:
            await msg.answer("➖ حذف ادمین:\n`/remove_admin <آیدی عددی>`")
    elif action == "backup":
        await callback.answer("🗄 در حال ساخت بکاپ...")
        if msg and msg.bot:
            try:
                await send_backup(msg.bot, db, msg.chat.id)
            except Exception as exc:
                logger.exception("Backup via menu failed: %s", exc)
                await msg.answer("❌ ساخت بکاپ ناموفق بود.")
    else:
        await callback.answer("Unknown action", show_alert=True)


@router.callback_query(F.data.startswith("ident:"))
async def on_identity_choice(
    callback: CallbackQuery, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
    if not callback.data or not callback.from_user:
        await callback.answer("Invalid payload", show_alert=True)
        return
    if callback.from_user.id not in super_admin_ids:
        await callback.answer("فقط سوپرادمین.", show_alert=True)
        return

    parts = callback.data.split(":")  # ident:<bug_id>:named|anon
    if len(parts) != 3:
        await callback.answer("Invalid payload", show_alert=True)
        return
    try:
        bug_id = int(parts[1])
    except ValueError:
        await callback.answer("Invalid bug id", show_alert=True)
        return

    choice = parts[2]
    if choice == "named":
        name = (
            callback.from_user.full_name
            or callback.from_user.username
            or f"user_{callback.from_user.id}"
        )
        await db.update_reporter(bug_id, callback.from_user.id, name)
        note = f"👤 BUG-{bug_id} با نام «{name}» ثبت شد."
    else:
        await db.update_reporter(bug_id, None, ANONYMOUS_NAME)
        note = f"🕶 BUG-{bug_id} ناشناس ثبت شد."

    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as exc:
            logger.warning("Could not clear identity keyboard: %s", exc)
    await callback.answer(note)


@router.callback_query(F.data == "panel:latest")
async def on_panel_latest(
    callback: CallbackQuery, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
    await callback.answer()
    if not callback.message:
        return
    bugs = await db.list_latest(20)
    if not bugs:
        await callback.message.answer("هنوز هیچ باگی ثبت نشده.")
        return
    is_super = _is_super(callback, super_admin_ids)
    await callback.message.answer(f"📋 {len(bugs)} گزارش آخر:")
    for bug in bugs:
        await callback.message.answer(
            format_bug(bug),
            reply_markup=status_keyboard(
                bug["id"],
                has_media=bool(bug.get("telegram_file_id")),
                is_super=is_super,
            ),
        )


@router.callback_query(F.data == "panel:critical")
async def on_panel_critical(
    callback: CallbackQuery, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
    await callback.answer()
    if not callback.message:
        return
    bugs = await db.list_by_severity("Critical", 50)
    if not bugs:
        await callback.message.answer("🎉 هیچ باگ Critical نداریم.")
        return
    is_super = _is_super(callback, super_admin_ids)
    await callback.message.answer(f"🚨 {len(bugs)} باگ Critical:")
    for bug in bugs:
        await callback.message.answer(
            format_bug(bug),
            reply_markup=status_keyboard(
                bug["id"],
                has_media=bool(bug.get("telegram_file_id")),
                is_super=is_super,
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


def _parse_bug_id(callback: CallbackQuery) -> int | None:
    try:
        return int((callback.data or "").split(":")[1])
    except (ValueError, IndexError):
        return None


@router.callback_query(F.data.startswith("del:"))
async def on_delete_request(
    callback: CallbackQuery, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
    if not _is_super(callback, super_admin_ids):
        await callback.answer("فقط سوپرادمین می‌تونه حذف کنه.", show_alert=True)
        return
    bug_id = _parse_bug_id(callback)
    if bug_id is None:
        await callback.answer("Invalid bug id", show_alert=True)
        return
    if not await db.get_bug(bug_id):
        await callback.answer("این گزارش وجود نداره.", show_alert=True)
        return
    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=delete_confirm_keyboard(bug_id)
            )
        except Exception as exc:
            logger.warning("Could not show delete confirm: %s", exc)
    await callback.answer("مطمئنی؟ برای حذف تأیید کن.")


@router.callback_query(F.data.startswith("delyes:"))
async def on_delete_confirm(
    callback: CallbackQuery, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
    if not _is_super(callback, super_admin_ids):
        await callback.answer("فقط سوپرادمین می‌تونه حذف کنه.", show_alert=True)
        return
    bug_id = _parse_bug_id(callback)
    if bug_id is None:
        await callback.answer("Invalid bug id", show_alert=True)
        return
    ok = await db.delete_bug(bug_id)
    if callback.message:
        try:
            await callback.message.edit_text(
                f"🗑 BUG-{bug_id} حذف شد." if ok else f"BUG-{bug_id} پیدا نشد.",
                reply_markup=None,
            )
        except Exception as exc:
            logger.warning("Could not edit after delete: %s", exc)
    await callback.answer("🗑 حذف شد." if ok else "پیدا نشد.")


@router.callback_query(F.data.startswith("delno:"))
async def on_delete_cancel(
    callback: CallbackQuery, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
    if not _is_super(callback, super_admin_ids):
        await callback.answer("فقط سوپرادمین.", show_alert=True)
        return
    bug_id = _parse_bug_id(callback)
    if bug_id is None:
        await callback.answer("Invalid bug id", show_alert=True)
        return
    bug = await db.get_bug(bug_id)
    if callback.message and bug:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=status_keyboard(
                    bug_id,
                    has_media=bool(bug.get("telegram_file_id")),
                    is_super=True,
                )
            )
        except Exception as exc:
            logger.warning("Could not restore keyboard after cancel: %s", exc)
    await callback.answer("لغو شد.")
