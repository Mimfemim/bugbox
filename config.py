import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    openai_api_key: str
    super_admin_ids: tuple[int, ...]
    db_path: str
    openai_model: str
    openai_base_url: str


def _parse_admin_ids(raw: str) -> tuple[int, ...]:
    ids: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.append(int(chunk))
        except ValueError:
            continue
    return tuple(ids)


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()

    # Super admins come from SUPER_ADMIN_IDS; fall back to the legacy ADMIN_IDS
    # so existing deployments keep working without an env change.
    super_admin_raw = os.getenv("SUPER_ADMIN_IDS", "").strip()
    legacy_admin_raw = os.getenv("ADMIN_IDS", "").strip()
    super_admin_ids = _parse_admin_ids(super_admin_raw) or _parse_admin_ids(
        legacy_admin_raw
    )

    if not bot_token:
        raise RuntimeError("BOT_TOKEN env variable is required")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY env variable is required")

    return Config(
        bot_token=bot_token,
        openai_api_key=openai_api_key,
        super_admin_ids=super_admin_ids,
        db_path=os.getenv("DB_PATH", "bugs.db"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "").strip(),
    )
