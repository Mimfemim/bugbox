"""Persian (Farsi) display helpers: Jalali/Shamsi dates, Persian digits,
and Persian labels for media types. Used by bug cards and exports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jdatetime

# Iran Standard Time (UTC+03:30). created_at is stored as UTC ISO, so we shift
# to Tehran local time before converting to the Jalali calendar.
TEHRAN = timezone(timedelta(hours=3, minutes=30))

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

_MEDIA_LABELS = {
    "photo": "عکس",
    "video": "ویدیو",
    "video_note": "ویدیو پیام",
    "voice": "پیام صوتی",
    "audio": "صوت",
    "document": "فایل",
    "animation": "گیف",
    "sticker": "استیکر",
}


def fa_digits(value: object) -> str:
    """Convert Latin digits in a value to Persian digits."""
    return str(value).translate(_FA_DIGITS)


def to_shamsi(iso_str: Optional[str], with_time: bool = True) -> str:
    """Convert a stored UTC ISO timestamp to a simple Persian Shamsi string
    (Tehran local time), e.g. '۱۴۰۵/۰۳/۲۶ ۱۸:۰۰'. Returns '—' if empty and
    the original string unchanged if it can't be parsed."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
    except ValueError:
        return iso_str
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(TEHRAN)
    j = jdatetime.datetime.fromgregorian(datetime=local)
    fmt = "%Y/%m/%d %H:%M" if with_time else "%Y/%m/%d"
    return fa_digits(j.strftime(fmt))


def media_label(media_type: Optional[str]) -> str:
    """Persian label for a stored media type (falls back to a generic 'فایل')."""
    if not media_type:
        return "—"
    return _MEDIA_LABELS.get(media_type, "فایل")
