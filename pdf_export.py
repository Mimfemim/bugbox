"""Minimal Persian/RTL PDF export of bug reports.

Each bug becomes one A4 page with: BUG-id + Shamsi date header, title,
reporter + category, a colored severity badge + status, the screenshot (when
the report has a photo), and an excerpt of the raw text.

Font: Vazirmatn-Regular.ttf (SIL OFL 1.1) lives under assets/.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from typing import Optional

import arabic_reshaper
from aiogram import Bot
from bidi.algorithm import get_display
from fpdf import FPDF
from PIL import Image

from persian import fa_digits, to_shamsi

logger = logging.getLogger(__name__)

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONT_PATH = os.path.join(_ASSETS_DIR, "Vazirmatn-Regular.ttf")

# RGB colours for severity + status badges.
_SEVERITY_COLORS = {
    "Critical": (220, 53, 69),
    "High": (253, 126, 20),
    "Medium": (245, 191, 35),
    "Low": (40, 167, 69),
}
_STATUS_COLORS = {
    "NEW": (13, 110, 253),
    "TRIAGED": (111, 66, 193),
    "IN_PROGRESS": (253, 126, 20),
    "FIXED": (25, 135, 84),
    "CLOSED": (108, 117, 125),
}
_NEUTRAL = (108, 117, 125)

# Keep PDFs manageable: clamp raw text and screenshot size per page.
_MAX_RAW = 800
_SCREENSHOT_W_MM = 130
_SCREENSHOT_MAX_H_MM = 90
# Visual spacing between cards on the same page.
_CARD_GAP = 5
_CARD_PAD = 3  # inner padding inside the card border


def _fa(text: str) -> str:
    """Reshape Persian glyphs and apply the bidi algorithm so fpdf2 renders
    Persian text in visually correct order."""
    return get_display(arabic_reshaper.reshape(str(text)))


async def _download_photo(bot: Bot, file_id: str) -> Optional[str]:
    """Pull a Telegram photo into a temp JPEG and return its path."""
    try:
        buf = io.BytesIO()
        await bot.download(file_id, destination=buf)
        buf.seek(0)
        img = Image.open(buf).convert("RGB")
        img.thumbnail((1200, 1200))
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img.save(tmp.name, format="JPEG", quality=82)
        tmp.close()
        return tmp.name
    except Exception as exc:
        logger.warning("Could not download photo %s: %s", file_id, exc)
        return None


def _draw_badge(
    pdf: FPDF, x: float, y: float, label: str, color: tuple[int, int, int]
) -> float:
    """Draw a coloured pill at (x, y); returns its width in mm."""
    pdf.set_font("Vazir", "", 10)
    text = _fa(label)
    width = pdf.get_string_width(text) + 6
    pdf.set_xy(x, y)
    pdf.set_fill_color(*color)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(width, 7, text, fill=True, align="C")
    pdf.set_text_color(0, 0, 0)
    return width


def _screenshot_target_size(image_path: str) -> tuple[float, float]:
    """Scaled (width_mm, height_mm) for the embedded screenshot."""
    try:
        with Image.open(image_path) as img:
            iw, ih = img.size
    except Exception:
        return _SCREENSHOT_W_MM, _SCREENSHOT_MAX_H_MM
    target_w = _SCREENSHOT_W_MM
    target_h = (target_w * ih / iw) if iw else _SCREENSHOT_MAX_H_MM
    if target_h > _SCREENSHOT_MAX_H_MM:
        target_h = _SCREENSHOT_MAX_H_MM
        target_w = (target_h * iw / ih) if ih else _SCREENSHOT_W_MM
    return target_w, target_h


def _measure_card_height(pdf: FPDF, bug: dict, image_path: Optional[str]) -> float:
    """Estimate the rendered height of a card without drawing anything.

    Uses fpdf2's dry_run multi_cell to measure wrapped text blocks, and adds
    fixed contributions for the header/badges/screenshot."""
    left = pdf.l_margin
    h = 0.0
    # Header bar
    h += 10 + 2
    # Title
    pdf.set_font("Vazir", "", 15)
    pdf.set_x(left)
    h += pdf.multi_cell(
        0, 9, _fa(bug.get("ai_title") or "—"),
        align="R", dry_run=True, output="HEIGHT",
    )
    h += 1
    # Reporter + category
    pdf.set_font("Vazir", "", 11)
    pdf.set_x(left)
    rep = bug.get("reporter_name") or "—"
    cat = bug.get("category") or "—"
    h += pdf.multi_cell(
        0, 7, _fa(f"گزارش‌دهنده: {rep}     |     دسته: {cat}"),
        align="R", dry_run=True, output="HEIGHT",
    )
    h += 1
    # Badges row
    h += 10
    # Screenshot
    if image_path:
        _, target_h = _screenshot_target_size(image_path)
        h += target_h + 4
    # Raw text
    raw = (bug.get("raw_text") or "").strip()
    if raw:
        if len(raw) > _MAX_RAW:
            raw = raw[:_MAX_RAW] + "…"
        pdf.set_font("Vazir", "", 11)
        pdf.set_x(left)
        h += pdf.multi_cell(
            0, 6, _fa("متن گزارش:"),
            align="R", dry_run=True, output="HEIGHT",
        )
        pdf.set_font("Vazir", "", 10)
        pdf.set_x(left)
        h += pdf.multi_cell(
            0, 6, _fa(raw),
            align="R", dry_run=True, output="HEIGHT",
        )
    # Inner padding
    h += _CARD_PAD * 2
    return h


def _render_card(pdf: FPDF, bug: dict, image_path: Optional[str]) -> None:
    page_w = pdf.w
    left = pdf.l_margin
    right_edge = page_w - pdf.r_margin
    start_y = pdf.get_y()

    # Header bar (per-card, at current cursor)
    pdf.set_fill_color(48, 84, 150)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Vazir", "", 13)
    pdf.set_xy(left, start_y)
    pdf.cell(right_edge - left, 10, "", fill=True)
    header_text = _fa(
        f"BUG-{fa_digits(bug['id'])}   |   {to_shamsi(bug.get('created_at'))}"
    )
    pdf.set_xy(left, start_y)
    pdf.cell(right_edge - left, 10, header_text, align="R")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(start_y + 12)

    # Title
    pdf.set_font("Vazir", "", 15)
    pdf.set_x(left)
    pdf.multi_cell(0, 9, _fa(bug.get("ai_title") or "—"), align="R")
    pdf.ln(1)

    # Reporter + category line
    pdf.set_font("Vazir", "", 11)
    reporter = bug.get("reporter_name") or "—"
    category = bug.get("category") or "—"
    pdf.set_x(left)
    pdf.multi_cell(
        0,
        7,
        _fa(f"گزارش‌دهنده: {reporter}     |     دسته: {category}"),
        align="R",
    )
    pdf.ln(1)

    # Badges (right-aligned: severity rightmost, status next to it)
    sev = bug.get("severity") or "—"
    status = bug.get("status") or "—"
    sev_color = _SEVERITY_COLORS.get(sev, _NEUTRAL)
    st_color = _STATUS_COLORS.get(status, _NEUTRAL)

    y = pdf.get_y() + 1
    pdf.set_font("Vazir", "", 10)
    sev_text = _fa(f"شدت: {sev}")
    sev_w = pdf.get_string_width(sev_text) + 6
    st_text = _fa(f"وضعیت: {status}")
    st_w = pdf.get_string_width(st_text) + 6

    sev_x = right_edge - sev_w
    st_x = sev_x - 4 - st_w
    _draw_badge(pdf, sev_x, y, f"شدت: {sev}", sev_color)
    _draw_badge(pdf, st_x, y, f"وضعیت: {status}", st_color)
    pdf.set_y(y + 10)

    # Screenshot
    if image_path:
        try:
            target_w, target_h = _screenshot_target_size(image_path)
            x_img = (page_w - target_w) / 2
            pdf.image(image_path, x=x_img, y=pdf.get_y(), w=target_w, h=target_h)
            pdf.set_y(pdf.get_y() + target_h + 4)
        except Exception as exc:
            logger.warning("Could not place screenshot for BUG-%s: %s", bug["id"], exc)

    # Raw text excerpt
    raw = (bug.get("raw_text") or "").strip()
    if raw:
        if len(raw) > _MAX_RAW:
            raw = raw[:_MAX_RAW] + "…"
        pdf.set_font("Vazir", "", 11)
        pdf.set_x(left)
        pdf.multi_cell(0, 6, _fa("متن گزارش:"), align="R")
        pdf.set_font("Vazir", "", 10)
        pdf.set_x(left)
        pdf.multi_cell(0, 6, _fa(raw), align="R")

    end_y = pdf.get_y() + _CARD_PAD
    # Subtle border around the card so adjacent cards don't blend
    pdf.set_draw_color(210, 210, 210)
    pdf.set_line_width(0.3)
    pdf.rect(left - 2, start_y - 1, right_edge - left + 4, end_y - start_y + 2)
    pdf.set_y(end_y)


def _empty_pdf_message() -> bytes:
    pdf = FPDF(format="A4")
    pdf.add_font("Vazir", "", FONT_PATH)
    pdf.set_font("Vazir", "", 14)
    pdf.add_page()
    pdf.multi_cell(0, 10, _fa("هیچ گزارشی برای خروجی گرفتن نیست."), align="R")
    return bytes(pdf.output())


async def build_bugs_pdf(bot: Optional[Bot], bugs: list[dict]) -> bytes:
    """Render the supplied bug rows into a single PDF document. Cards are
    packed sequentially on each page; a new page starts only when the next
    card wouldn't otherwise fit."""
    if not bugs:
        return _empty_pdf_message()

    pdf = FPDF(format="A4")
    # We control page breaks ourselves so a card never gets split mid-content.
    pdf.set_auto_page_break(auto=False)
    pdf.set_margin(15)
    pdf.add_font("Vazir", "", FONT_PATH)
    pdf.set_font("Vazir", "", 11)
    pdf.add_page()

    bottom_limit = pdf.h - pdf.b_margin

    tempfiles: list[str] = []
    try:
        for bug in bugs:
            image_path = None
            if bug.get("media_type") == "photo" and bug.get("telegram_file_id") and bot is not None:
                image_path = await _download_photo(bot, bug["telegram_file_id"])
                if image_path:
                    tempfiles.append(image_path)

            needed = _measure_card_height(pdf, bug, image_path) + _CARD_GAP
            available = bottom_limit - pdf.get_y()
            # Start a new page if this card wouldn't fit (but never on a
            # completely empty page — that would loop forever for huge cards).
            if needed > available and pdf.get_y() > pdf.t_margin + 1:
                pdf.add_page()

            _render_card(pdf, bug, image_path)
            pdf.ln(_CARD_GAP)
        return bytes(pdf.output())
    finally:
        for path in tempfiles:
            try:
                os.remove(path)
            except OSError:
                pass
