from __future__ import annotations

import json
import logging
from typing import Any, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES: list[str] = [
    "Gameplay",
    "Cards",
    "Prediction",
    "UI",
    "UX",
    "Performance",
    "Login",
    "Payment",
    "Content",
    "Backend",
    "Other",
]

ALLOWED_SEVERITY: list[str] = ["Critical", "High", "Medium", "Low"]
ALLOWED_PRIORITY: list[str] = ["P0", "P1", "P2", "P3"]
ALLOWED_OWNER: list[str] = [
    "Frontend",
    "Backend",
    "Game Design",
    "Content",
    "QA",
    "Unknown",
]
ALLOWED_REPRO: list[str] = ["Always", "Sometimes", "Once", "Unknown"]

DEFAULT_ANALYSIS: dict[str, Any] = {
    "title": "Untitled bug report",
    "summary": "",
    "category": "Other",
    "severity": "Medium",
    "priority": "P2",
    "device": "Unknown",
    "reproducibility": "Unknown",
    "suggested_owner": "Unknown",
    "status": "NEW",
}

SYSTEM_PROMPT = f"""You are a bug triage assistant for an internal QA team.
You receive a raw bug report — possibly text, a caption, a forwarded message,
or just a note that media was attached. Your job is to triage it.

Return ONLY a JSON object matching this schema. No prose, no markdown, no extra keys.

{{
  "title": "short, descriptive title under 80 characters",
  "summary": "1-3 sentence neutral summary of the issue",
  "category": one of {ALLOWED_CATEGORIES},
  "severity": one of {ALLOWED_SEVERITY},
  "priority": one of {ALLOWED_PRIORITY},
  "device": "device or platform if mentioned, otherwise 'Unknown'",
  "reproducibility": one of {ALLOWED_REPRO},
  "suggested_owner": one of {ALLOWED_OWNER},
  "status": "NEW"
}}

Guidance:
- The report may be in Persian, English, or mixed. Title and summary should be in the same language as the report.
- If the report is empty or media-only, still produce best-guess JSON. Title can be 'Media-only report'.
- Critical = crash, data loss, blocker. Low = cosmetic.
- Default priority P2; use P0 for Critical, P3 for trivial polish.
- Map UI vs UX: UI = visual/layout bugs, UX = flow/clarity issues.
- Backend issues (API errors, server 5xx) go to category Backend, owner Backend.
"""


class AIAnalyzer:
    def __init__(
        self, api_key: str, model: str = "gpt-4o-mini", base_url: str = ""
    ) -> None:
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            # Works with any OpenAI-compatible gateway (OpenRouter, Together, etc.)
            client_kwargs["base_url"] = base_url
            client_kwargs["default_headers"] = {
                "HTTP-Referer": "https://github.com/bug-inbox-bot",
                "X-Title": "Bug Inbox Bot",
            }
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = model

    async def analyze(
        self, text: str, media_type: Optional[str]
    ) -> tuple[dict[str, Any], bool]:
        """Returns (analysis, ai_ok). ai_ok is False when the model call
        failed and a safe fallback was produced instead."""
        user_content = self._build_user_prompt(text, media_type)
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            raw = response.choices[0].message.content or "{}"
            data = json.loads(raw)
            return self._sanitize(data), True
        except Exception as exc:
            logger.exception("AI analysis failed: %s", exc)
            fallback = dict(DEFAULT_ANALYSIS)
            if text.strip():
                fallback["title"] = text.strip().splitlines()[0][:80] or fallback["title"]
                fallback["summary"] = text.strip()[:500]
            elif media_type:
                fallback["title"] = f"Media-only report ({media_type})"
            return fallback, False

    @staticmethod
    def _build_user_prompt(text: str, media_type: Optional[str]) -> str:
        parts: list[str] = []
        if media_type:
            parts.append(f"Attached media: {media_type}")
        if text.strip():
            parts.append(f"Report content:\n{text.strip()}")
        else:
            parts.append("Report content: <empty — media-only submission>")
        return "\n\n".join(parts)

    @staticmethod
    def _sanitize(data: dict[str, Any]) -> dict[str, Any]:
        out = dict(DEFAULT_ANALYSIS)
        for key in out.keys():
            value = data.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            out[key] = value

        if out["category"] not in ALLOWED_CATEGORIES:
            out["category"] = "Other"
        if out["severity"] not in ALLOWED_SEVERITY:
            out["severity"] = "Medium"
        if out["priority"] not in ALLOWED_PRIORITY:
            out["priority"] = "P2"
        if out["suggested_owner"] not in ALLOWED_OWNER:
            out["suggested_owner"] = "Unknown"
        if out["reproducibility"] not in ALLOWED_REPRO:
            out["reproducibility"] = "Unknown"

        out["status"] = "NEW"
        out["title"] = str(out["title"])[:200]
        out["summary"] = str(out["summary"])[:2000]
        out["device"] = str(out["device"])[:120]
        return out
