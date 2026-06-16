from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from persian import fa_digits

PDF_SLICE_SIZE = 50
# Cap how many sliced ranges we show as buttons; "همه" always remains available.
_PDF_MAX_SLICE_BUTTONS = 9


def panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Latest Bugs", callback_data="panel:latest"),
                InlineKeyboardButton(text="Critical Bugs", callback_data="panel:critical"),
            ],
            [
                InlineKeyboardButton(text="Export CSV", callback_data="panel:csv"),
                InlineKeyboardButton(text="Export Excel", callback_data="panel:xlsx"),
            ],
            [
                InlineKeyboardButton(
                    text="📕 Export PDF (با اسکرین‌شات)", callback_data="panel:pdf"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="♻️ Re-analyze Pending", callback_data="panel:reanalyze"
                ),
            ],
        ]
    )


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Super-admin command menu shown by /admin."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 داشبورد آمار", callback_data="admin:panel")],
            [
                InlineKeyboardButton(
                    text="📋 آخرین باگ‌ها", callback_data="panel:latest"
                ),
                InlineKeyboardButton(
                    text="🚨 باگ‌های Critical", callback_data="panel:critical"
                ),
            ],
            [
                InlineKeyboardButton(text="📄 خروجی CSV", callback_data="panel:csv"),
                InlineKeyboardButton(text="📊 خروجی Excel", callback_data="panel:xlsx"),
            ],
            [
                InlineKeyboardButton(
                    text="📕 خروجی PDF (با اسکرین‌شات)", callback_data="panel:pdf"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="♻️ تحلیل دوبارهٔ Pending", callback_data="panel:reanalyze"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 لیست ادمین‌ها", callback_data="admin:list"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ افزودن ادمین", callback_data="admin:add_help"
                ),
                InlineKeyboardButton(
                    text="➖ حذف ادمین", callback_data="admin:remove_help"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗄 بکاپ دیتابیس", callback_data="admin:backup"
                )
            ],
        ]
    )


def status_keyboard(
    bug_id: int,
    has_media: bool = False,
    is_super: bool = False,
    media_type: str | None = None,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="Triaged", callback_data=f"status:{bug_id}:TRIAGED"
            ),
            InlineKeyboardButton(
                text="In Progress", callback_data=f"status:{bug_id}:IN_PROGRESS"
            ),
        ],
        [
            InlineKeyboardButton(
                text="Fixed", callback_data=f"status:{bug_id}:FIXED"
            ),
            InlineKeyboardButton(
                text="Closed", callback_data=f"status:{bug_id}:CLOSED"
            ),
        ],
    ]
    if has_media:
        # Label tells admins what they'll get — "عکس" for photos, generic
        # "فایل" for anything else.
        if media_type == "photo":
            media_label_text = "📷 مشاهده عکس"
        elif media_type == "video":
            media_label_text = "🎬 مشاهده ویدیو"
        elif media_type == "voice":
            media_label_text = "🎙 پخش پیام صوتی"
        else:
            media_label_text = "📎 مشاهده فایل"
        rows.append(
            [
                InlineKeyboardButton(
                    text=media_label_text, callback_data=f"media:{bug_id}"
                ),
            ]
        )
    if is_super:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗑 حذف گزارش", callback_data=f"del:{bug_id}"
                ),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pdf_size_keyboard(total: int) -> InlineKeyboardMarkup:
    """Inline picker shown before a PDF export when there are many bugs.

    Offers latest-N options in PDF_SLICE_SIZE-wide steps (e.g. 50, 100, 150…)
    up to _PDF_MAX_SLICE_BUTTONS rows, plus an "همه" option that always
    appears last."""
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(1, _PDF_MAX_SLICE_BUTTONS + 1):
        n = PDF_SLICE_SIZE * i
        if n >= total:
            break
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{fa_digits(n)} گزارش آخر",
                    callback_data=f"pdfexp:{n}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"📦 همهٔ گزارش‌ها ({fa_digits(total)} تا)",
                callback_data="pdfexp:all",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_confirm_keyboard(bug_id: int) -> InlineKeyboardMarkup:
    """Two-step confirmation before a super admin deletes a report."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ تأیید حذف", callback_data=f"delyes:{bug_id}"
                ),
                InlineKeyboardButton(
                    text="↩️ انصراف", callback_data=f"delno:{bug_id}"
                ),
            ]
        ]
    )
