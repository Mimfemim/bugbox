from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message
from openpyxl import Workbook

from ai_analyzer import AIAnalyzer
from db import Database
from keyboards import panel_keyboard, status_keyboard

logger = logging.getLogger(__name__)

router = Router(name="admin")


def _admin_filter_factory(admin_ids: tuple[int, ...]):
    async def is_admin(message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in admin_ids)

    return is_admin


def setup(admin_ids: tuple[int, ...]) -> Router:
    router.message.filter(_admin_filter_factory(admin_ids))
    return router


def format_bug(bug: dict) -> str:
    lines = [
        f"#BUG-{bug['id']}\n",
        f"Title:\n{bug.get('ai_title') or '-'}\n",
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
