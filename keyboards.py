from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


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
    bug_id: int, has_media: bool = False, is_super: bool = False
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
        rows.append(
            [
                InlineKeyboardButton(
                    text="📎 مشاهده فایل", callback_data=f"media:{bug_id}"
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
