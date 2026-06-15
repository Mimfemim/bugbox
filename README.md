# Bug Inbox Bot

A friction-free Telegram bot for internal QA: testers send anything (text, screenshots, video, voice, files, forwards) and the bot auto-categorizes the report with OpenAI and stores it for triage.

No forms. No manual categorization. No web panel.

---

## Features

- Captures **any** Telegram message: text, photo, video, video note, voice, audio, document, animation, sticker, forwards.
- AI triage (OpenAI JSON mode) → title, summary, category, severity, priority, device, reproducibility, suggested owner.
- SQLite storage, auto-initialized on first run.
- Admin dashboard, latest bugs view, instant status updates via inline buttons.
- CSV and Excel (`.xlsx`) export.
- Async-only, aiogram 3.x best practices.
- Graceful fallback on OpenAI failure — bot never crashes.

---

## Installation

Requires **Python 3.11**.

```bash
git clone <this-repo> bug-inbox-bot
cd bug-inbox-bot

python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

---

## Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable          | Required | Default        | Description                                         |
| ----------------- | -------- | -------------- | --------------------------------------------------- |
| `BOT_TOKEN`       | yes      | —              | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `OPENAI_API_KEY`  | yes      | —              | OpenAI API key (or OpenRouter key, see below)        |
| `ADMIN_IDS`       | no       | (empty)        | Comma-separated Telegram user IDs of admins          |
| `OPENAI_MODEL`    | no       | `gpt-4o-mini`  | Model used for triage                                |
| `OPENAI_BASE_URL` | no       | (OpenAI)       | OpenAI-compatible endpoint (e.g. OpenRouter)          |
| `DB_PATH`         | no       | `bugs.db`      | SQLite database path                                 |

To find your own Telegram user ID, message [@userinfobot](https://t.me/userinfobot) or send `/myid` to this bot.

### Using OpenRouter (or another OpenAI-compatible gateway)

The bot talks to OpenAI through the official SDK, so any OpenAI-compatible gateway works by overriding the base URL:

```env
OPENAI_API_KEY=sk-or-v1-...                 # your OpenRouter key
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=openai/gpt-4o-mini             # note the provider prefix
```

Model names on OpenRouter need the `provider/` prefix (e.g. `openai/gpt-4o-mini`, `anthropic/claude-3.5-sonnet`). Pick any model that supports JSON output. Leave `OPENAI_BASE_URL` unset to use OpenAI directly.

To find your own Telegram user ID, message [@userinfobot](https://t.me/userinfobot).

---

## Local run

```bash
python bot.py
```

The bot uses **long-polling** — no webhook setup, no public URL needed.
The SQLite file is created automatically on first run.

---

## Railway deployment

1. Push this repo to GitHub.
2. Create a new Railway project from the repo.
3. Under **Variables**, add `BOT_TOKEN`, `OPENAI_API_KEY`, and `ADMIN_IDS`.
4. Railway picks up `runtime.txt` (`python-3.11.9`) automatically.
5. Set the start command to:

   ```
   python bot.py
   ```

6. Deploy.

> **Note**: SQLite on Railway is ephemeral by default — for persistence across redeploys, attach a Railway Volume and mount it (set `DB_PATH=/data/bugs.db` and mount the volume at `/data`).

---

## Usage

### Tester flow

Just send (or forward) any message to the bot. The bot replies with:

```
✅ گزارش ثبت شد

کد: BUG-123

عنوان:
مشکل نمایش کارت مربی

دسته:
Cards

شدت:
High
```

### Admin commands

Only user IDs listed in `ADMIN_IDS` can use these.

| Command          | Description                                           |
| ---------------- | ----------------------------------------------------- |
| `/panel`         | Stats dashboard (incl. Pending AI) + inline buttons   |
| `/bugs`          | Latest 20 bugs with status buttons on each            |
| `/export_csv`    | Download all bugs as CSV                              |
| `/export_excel`  | Download all bugs as XLSX                             |
| `/reanalyze`     | Re-run AI on all reports that weren't analyzed yet     |

Anyone (not just admins) can use `/myid` to see their own numeric Telegram ID — useful for filling in `ADMIN_IDS`.

### AI status & graceful degradation

Every report is **saved in full immediately**, with the original message text kept verbatim in `raw_text`. The AI categorization is layered on top:

- If OpenAI succeeds → `ai_status = ANALYZED`, all AI fields filled.
- If OpenAI fails (no quota, network, invalid key) → the report is still saved with `ai_status = PENDING` and a safe fallback (title from the first line of the text, category `Other`).

When your OpenAI quota is restored, open `/panel` and press **♻️ Re-analyze Pending** (or send `/reanalyze`). The bot re-runs AI on every `PENDING` report and fills in the missing fields. Re-analysis **never** overwrites the workflow status (NEW/TRIAGED/…) you've already set.

### Viewing attached media

Reports that include media (photo, video, voice, document, …) show a **📎 مشاهده فایل** button on their bug card in `/bugs`. Pressing it makes the bot re-send the original file to the admin.

No file storage is involved: the bot keeps only Telegram's `telegram_file_id` (a permanent reference to the file on Telegram's own servers) and re-sends by that ID on demand. This means **zero disk usage, no S3, and no Railway volume needed for media** — Telegram hosts the files for free. (If you ever need the raw bytes outside Telegram — e.g. for a web dashboard — you'd download them with `bot.download(file_id)` and store them yourself, but that's not required for this bot.)

### Status workflow

Each bug card has four inline buttons: **Triaged**, **In Progress**, **Fixed**, **Closed**.

Allowed statuses: `NEW`, `TRIAGED`, `IN_PROGRESS`, `FIXED`, `CLOSED`.

---

## Database

Auto-created at startup (`bugs.db` by default).

```sql
CREATE TABLE bugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER,
    reporter_name TEXT,
    raw_text TEXT,
    media_type TEXT,
    telegram_file_id TEXT,
    ai_title TEXT,
    ai_summary TEXT,
    category TEXT,
    severity TEXT,
    priority TEXT,
    device TEXT,
    reproducibility TEXT,
    suggested_owner TEXT,
    status TEXT,
    ai_status TEXT DEFAULT 'PENDING',  -- ANALYZED once AI triage succeeds
    created_at TEXT,
    updated_at TEXT
);
```

> An existing database from an older version is migrated automatically on startup (the `ai_status` column is added with `ALTER TABLE`).

### AI taxonomy

| Field              | Allowed values                                                                                  |
| ------------------ | ----------------------------------------------------------------------------------------------- |
| `category`         | Gameplay, Cards, Prediction, UI, UX, Performance, Login, Payment, Content, Backend, Other       |
| `severity`         | Critical, High, Medium, Low                                                                     |
| `priority`         | P0, P1, P2, P3                                                                                  |
| `suggested_owner`  | Frontend, Backend, Game Design, Content, QA, Unknown                                            |
| `reproducibility`  | Always, Sometimes, Once, Unknown                                                                |

---

## Export format

CSV and Excel exports share the same columns:

```
ID | Created At | Reporter | Title | Category | Severity | Priority | Owner | Status | Summary
```

CSV is UTF-8 with BOM so Excel opens Persian text correctly.

---

## Project layout

```
project/
├── bot.py
├── config.py
├── db.py
├── ai_analyzer.py
├── keyboards.py
├── handlers/
│   ├── __init__.py
│   ├── start.py
│   ├── bug_submission.py
│   ├── admin.py
│   └── callbacks.py
├── exports/
├── requirements.txt
├── runtime.txt
└── README.md
```

---

## Reliability

- All handlers are async.
- The bot wraps the submission flow in try/except and logs exceptions — it never crashes on bad input.
- If OpenAI fails or returns invalid JSON, the bot stores a safe-default report (title from raw text, category `Other`, severity `Medium`).
- Empty messages and media without captions are handled gracefully.
- Invalid statuses are rejected by `Database.update_status`.

---

## License

MIT (or your choice).
