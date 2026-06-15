from __future__ import annotations

import csv
import io
import logging
import os
import tempfile
from datetime import datetime, timezone

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message
from openpyxl import Workbook

from ai_analyzer import AIAnalyzer
from db import Database
from keyboards import panel_keyboard, status_keyboard

logger = logging.getLogger(__name__)

router = Router(name="admin")


def _admin_filter_factory(super_admin_ids: tuple[int, ...], db: Database):
    async def is_admin(message: Message) -> bool:
        user = message.from_user
        if user is None:
            return False
        if user.id in super_admin_ids:
            return True
        return await db.is_admin(user.id)

    return is_admin


def setup(super_admin_ids: tuple[int, ...], db: Database) -> Router:
    router.message.filter(_admin_filter_factory(super_admin_ids, db))
    return router


def format_bug(bug: dict) -> str:
    lines = [
        f"#BUG-{bug['id']}\n",
        f"Title:\n{bug.get('ai_title') or '-'}\n",
        f"Reporter:\n{bug.get('reporter_name') or 'ناشناس'}\n",
        f"Category:\n{bug.get('category') or '-'}\n",
        f"Severity:\n{bug.get('severity') or '-'}\n",
        f"Status:\n{bug.get('status') or '-'}",
    ]
    if bug.get("telegram_file_id"):
        lines.append(f"\n📎 Media: {bug.get('media_type') or 'file'}")
    if bug.get("ai_status") == "PENDING":
        lines.append("\n⏳ AI: بررسی‌نشده")
    return "\n".join(lines)


def _rows_for_export(bugs: list[dict]) -> list[list]:
    rows: list[list] = []
    for b in bugs:
        rows.append(
            [
                b["id"],
                b.get("created_at") or "",
                b.get("reporter_name") or "",
                b.get("ai_title") or "",
                b.get("category") or "",
                b.get("severity") or "",
                b.get("priority") or "",
                b.get("suggested_owner") or "",
                b.get("status") or "",
                b.get("ai_summary") or "",
            ]
        )
    return rows


EXPORT_HEADERS = [
    "ID",
    "Created At",
    "Reporter",
    "Title",
    "Category",
    "Severity",
    "Priority",
    "Owner",
    "Status",
    "Summary",
]


async def send_csv(message: Message, db: Database) -> None:
    bugs = await db.list_all()
    if not bugs:
        await message.answer("⚠️ هیچ گزارشی برای خروجی گرفتن نیست.")
        return

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(EXPORT_HEADERS)
    for row in _rows_for_export(bugs):
        writer.writerow(row)
    data = buf.getvalue().encode("utf-8-sig")
    name = f"bugs-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    await message.answer_document(BufferedInputFile(data, filename=name))


async def send_xlsx(message: Message, db: Database) -> None:
    bugs = await db.list_all()
    if not bugs:
        await message.answer("⚠️ هیچ گزارشی برای خروجی گرفتن نیست.")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Bugs"
    ws.append(EXPORT_HEADERS)
    for row in _rows_for_export(bugs):
        ws.append(row)

    for col_cells in ws.columns:
        values = [c.value for c in col_cells if c.value is not None]
        max_len = max((len(str(v)) for v in values), default=10)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 2, 60)

    buf = io.BytesIO()
    wb.save(buf)
    name = f"bugs-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.xlsx"
    await message.answer_document(BufferedInputFile(buf.getvalue(), filename=name))


async def _build_backup(db: Database) -> tuple[bytes, str]:
    """Snapshot the live DB into a temp file and return its bytes + filename."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    fname = f"bugs-backup-{ts}.db"
    tmp_path = os.path.join(tempfile.gettempdir(), fname)
    await db.backup_to(tmp_path)
    try:
        with open(tmp_path, "rb") as fh:
            data = fh.read()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    return data, fname


async def send_backup(bot: Bot, db: Database, chat_id: int) -> None:
    data, fname = await _build_backup(db)
    await bot.send_document(
        chat_id,
        BufferedInputFile(data, filename=fname),
        caption=f"🗄 بکاپ دیتابیس\n{fname}",
    )


async def broadcast_backup(bot: Bot, db: Database, chat_ids: tuple[int, ...]) -> None:
    """Build one snapshot and send it to every super admin (used by the
    daily auto-backup loop)."""
    if not chat_ids:
        return
    data, fname = await _build_backup(db)
    for cid in chat_ids:
        try:
            await bot.send_document(
                cid,
                BufferedInputFile(data, filename=fname),
                caption=f"🗄 بکاپ خودکار روزانه\n{fname}",
            )
        except Exception as exc:
            logger.warning("Daily backup send to %s failed: %s", cid, exc)


async def reanalyze_pending(message: Message, db: Database, analyzer: AIAnalyzer) -> None:
    pending = await db.list_pending(200)
    if not pending:
        await message.answer("✅ همه‌ی گزارش‌ها تحلیل شدن. چیزی برای بررسی نیست.")
        return

    status_msg = await message.answer(
        f"♻️ در حال تحلیل {len(pending)} گزارش بررسی‌نشده..."
    )
    ok_count = 0
    fail_count = 0
    for bug in pending:
        analysis, ai_ok = await analyzer.analyze(
            bug.get("raw_text") or "", bug.get("media_type")
        )
        if ai_ok:
            await db.update_analysis(bug["id"], analysis, "ANALYZED")
            ok_count += 1
        else:
            fail_count += 1

    result = f"✅ {ok_count} گزارش با موفقیت تحلیل شد."
    if fail_count:
        result += (
            f"\n⚠️ {fail_count} گزارش هنوز ناموفق بود "
            "(احتمالاً اعتبار OpenAI هنوز مشکل داره)."
        )
    try:
        await status_msg.edit_text(result)
    except Exception:
        await message.answer(result)


@router.message(Command("panel"))
async def cmd_panel(message: Message, db: Database) -> None:
    s = await db.stats()
    text = (
        "📊 Bug Dashboard\n\n"
        f"Total Bugs: {s['total']}\n"
        f"Open: {s['open']}\n"
        f"Pending AI: {s['pending']}\n\n"
        f"Critical: {s['Critical']}\n"
        f"High: {s['High']}\n"
        f"Medium: {s['Medium']}\n"
        f"Low: {s['Low']}"
    )
    await message.answer(text, reply_markup=panel_keyboard())


@router.message(Command("reanalyze"))
async def cmd_reanalyze(message: Message, db: Database, analyzer: AIAnalyzer) -> None:
    await reanalyze_pending(message, db, analyzer)


@router.message(Command("bugs"))
async def cmd_bugs(message: Message, db: Database) -> None:
    bugs = await db.list_latest(20)
    if not bugs:
        await message.answer("هنوز هیچ باگی ثبت نشده.")
        return

    await message.answer(f"📋 {len(bugs)} گزارش آخر:")
    for bug in bugs:
        await message.answer(
            format_bug(bug),
            reply_markup=status_keyboard(
                bug["id"], has_media=bool(bug.get("telegram_file_id"))
            ),
        )


@router.message(Command("export_csv"))
async def cmd_export_csv(message: Message, db: Database) -> None:
    await send_csv(message, db)


@router.message(Command("export_excel"))
async def cmd_export_excel(message: Message, db: Database) -> None:
    await send_xlsx(message, db)


# ----- Super-admin-only commands ------------------------------------------------


def _is_super(message: Message, super_admin_ids: tuple[int, ...]) -> bool:
    return bool(message.from_user and message.from_user.id in super_admin_ids)


@router.message(Command("add_admin"))
async def cmd_add_admin(
    message: Message, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
    if not _is_super(message, super_admin_ids):
        await message.answer("⛔️ فقط سوپرادمین می‌تونه ادمین اضافه کنه.")
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            "استفاده:\n`/add_admin <آیدی عددی> [نام دلخواه]`\n\n"
            "ادمین جدید آیدی عددیش رو با دستور /myid می‌تونه ببینه."
        )
        return
    try:
        new_id = int(parts[1])
    except ValueError:
        await message.answer("❌ آیدی باید یک عدد باشه.")
        return

    if new_id in super_admin_ids:
        await message.answer("این کاربر سوپرادمینه و از قبل دسترسی کامل داره.")
        return

    name = " ".join(parts[2:]).strip()
    await db.add_admin(new_id, name=name, added_by=message.from_user.id)
    suffix = f" ({name})" if name else ""
    await message.answer(
        f"✅ ادمین جدید اضافه شد: `{new_id}`{suffix}\n"
        "حالا می‌تونه /panel و /bugs و خروجی‌ها رو ببینه."
    )


@router.message(Command("remove_admin"))
async def cmd_remove_admin(
    message: Message, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
    if not _is_super(message, super_admin_ids):
        await message.answer("⛔️ فقط سوپرادمین می‌تونه ادمین حذف کنه.")
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("استفاده:\n`/remove_admin <آیدی عددی>`")
        return
    try:
        rid = int(parts[1])
    except ValueError:
        await message.answer("❌ آیدی باید یک عدد باشه.")
        return

    ok = await db.remove_admin(rid)
    await message.answer(
        f"✅ ادمین `{rid}` حذف شد." if ok else "این آیدی توی لیست ادمین‌ها نبود."
    )


@router.message(Command("admins"))
async def cmd_admins(
    message: Message, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
    if not _is_super(message, super_admin_ids):
        await message.answer("⛔️ فقط سوپرادمین به این دستور دسترسی داره.")
        return

    lines = ["👑 سوپرادمین‌ها:"]
    for sid in super_admin_ids:
        lines.append(f"• `{sid}`")

    admins = await db.list_admins()
    lines.append("\n👤 ادمین‌ها:")
    if admins:
        for a in admins:
            nm = f" ({a['name']})" if a.get("name") else ""
            lines.append(f"• `{a['user_id']}`{nm}")
    else:
        lines.append("(هنوز ادمینی اضافه نشده — با /add_admin اضافه کن)")

    await message.answer("\n".join(lines))


@router.message(Command("backup"))
async def cmd_backup(
    message: Message, db: Database, super_admin_ids: tuple[int, ...] = ()
) -> None:
    if not _is_super(message, super_admin_ids):
        await message.answer("⛔️ فقط سوپرادمین می‌تونه بکاپ بگیره.")
        return
    if message.bot is None:
        return
    try:
        await message.answer("🗄 در حال ساخت بکاپ...")
        await send_backup(message.bot, db, message.chat.id)
    except Exception as exc:
        logger.exception("Manual backup failed: %s", exc)
        await message.answer("❌ ساخت بکاپ ناموفق بود.")
