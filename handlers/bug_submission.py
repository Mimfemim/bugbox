from __future__ import annotations

import logging
from typing import Optional

from aiogram import Router
from aiogram.types import Message

from ai_analyzer import AIAnalyzer
from db import Database

logger = logging.getLogger(__name__)

router = Router(name="bug_submission")


def _detect_media(message: Message) -> tuple[Optional[str], Optional[str]]:
    if message.photo:
        return "photo", message.photo[-1].file_id
    if message.video:
        return "video", message.video.file_id
    if message.video_note:
        return "video_note", message.video_note.file_id
    if message.voice:
        return "voice", message.voice.file_id
    if message.audio:
        return "audio", message.audio.file_id
    if message.document:
        return "document", message.document.file_id
    if message.animation:
        return "animation", message.animation.file_id
    if message.sticker:
        return "sticker", message.sticker.file_id
    return None, None


def _extract_text(message: Message) -> str:
    parts: list[str] = []
    if message.text:
        parts.append(message.text)
    if message.caption:
        parts.append(message.caption)

    if message.forward_from:
        parts.append(f"[Forwarded from user: {message.forward_from.full_name}]")
    elif message.forward_from_chat:
        chat = message.forward_from_chat
        title = chat.title or chat.username or str(chat.id)
        parts.append(f"[Forwarded from chat: {title}]")
    elif getattr(message, "forward_sender_name", None):
        parts.append(f"[Forwarded from: {message.forward_sender_name}]")

    return "\n".join(p for p in parts if p)


@router.message()
async def handle_submission(
    message: Message, db: Database, analyzer: AIAnalyzer
) -> None:
    if message.text and message.text.startswith("/"):
        return
    if message.from_user is None:
        return

    try:
        text = _extract_text(message)
        media_type, file_id = _detect_media(message)

        if not text and not media_type:
            await message.answer("⚠️ پیام خالی بود. لطفاً متن یا فایل بفرست.")
            return

        reporter_name = (
            message.from_user.full_name
            or message.from_user.username
            or f"user_{message.from_user.id}"
        )

        analysis, ai_ok = await analyzer.analyze(text, media_type)

        bug_id = await db.insert_bug(
            reporter_id=message.from_user.id,
            reporter_name=reporter_name,
            raw_text=text,
            media_type=media_type,
            telegram_file_id=file_id,
            analysis=analysis,
            ai_status="ANALYZED" if ai_ok else "PENDING",
        )

        if ai_ok:
            reply = (
                "✅ گزارش ثبت شد\n\n"
                f"کد: BUG-{bug_id}\n\n"
                f"عنوان:\n{analysis['title']}\n\n"
                f"دسته:\n{analysis['category']}\n\n"
                f"شدت:\n{analysis['severity']}"
            )
        else:
            reply = (
                "✅ گزارش ذخیره شد\n\n"
                f"کد: BUG-{bug_id}\n\n"
                "⏳ دسته‌بندی هوش مصنوعی الان در دسترس نیست.\n"
                "متن گزارش کامل ذخیره شد و بعداً از پنل ادمین تحلیل می‌شه."
            )
        await message.answer(reply)
    except Exception as exc:
        logger.exception("Failed to handle submission: %s", exc)
        try:
            await message.answer("❌ خطا در ثبت گزارش. لطفاً دوباره تلاش کن.")
        except Exception:
            logger.exception("Failed to send error reply")
