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


def status_keyboard(bug_id: int, has_media: bool = False) -> InlineKeyboardMarkup:
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
    return InlineKeyboardMarkup(inline_keyboard=rows)
