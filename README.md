# Bug Inbox Bot

A friction-free Telegram bot for internal QA: testers send anything (text, screenshots, video, voice, files, forwards) and the bot auto-categorizes the report with OpenAI and stores it for triage.

No forms. No manual categorization. No web panel.

---

## Features

- Captures **any** Telegram message: text, photo, video, video note, voice, audio, document, animation, sticker, forwards.
- AI triage (OpenAI JSON mode) → title, summary, category, severity, priority, device, reproducibility, suggested owner.
- **Anonymous reporting**: tester reports are stored without name/ID; only the super admin can attach an identity to a report.
- **Two-tier roles**: super admins (env) can add/remove regular admins at runtime — no redeploy needed.
- **Backups**: on-demand `/backup` plus an automatic daily snapshot delivered to every super admin via Telegram.
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

| Variable           | Required | Default        | Description                                         |
| ------------------ | -------- | -------------- | --------------------------------------------------- |
| `BOT_TOKEN`        | yes      | —              | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `OPENAI_API_KEY`   | yes      | —              | OpenAI API key (or OpenRouter key, see below)        |
| `SUPER_ADMIN_IDS`  | no       | (empty)        | Comma-separated Telegram user IDs of **super admins** |
| `ADMIN_IDS`        | no       | (empty)        | Legacy fallback for `SUPER_ADMIN_IDS` (used only if it is unset) |
| `OPENAI_MODEL`     | no       | `gpt-4o-mini`  | Model used for triage                                |
| `OPENAI_BASE_URL`  | no       | (OpenAI)       | OpenAI-compatible endpoint (e.g. OpenRouter)          |
| `DB_PATH`          | no       | `bugs.db`      | SQLite database path                                 |

Regular admins are **not** set via env — a super admin adds them at runtime with `/add_admin` (stored in the database). See [Roles & anonymity](#roles--anonymity).

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
3. Under **Variables**, add `BOT_TOKEN`, `OPENAI_API_KEY`, `SUPER_ADMIN_IDS`, and (for OpenRouter) `OPENAI_BASE_URL` + `OPENAI_MODEL`.
4. Railway picks up `runtime.txt` (`python-3.11.9`) and the `Procfile` (`worker: python bot.py`) automatically.
5. **Attach a Volume** for database persistence (next note).
6. Deploy.

> **Persistence (important)**: SQLite on Railway is ephemeral by default — without a Volume, every redeploy wipes your data. Attach a Railway Volume, mount it at `/data`, and set `DB_PATH=/data/bugs.db`. The bot creates the DB file there automatically on first run. (Volumes are added from the project **Canvas** — right-click the service → *Attach Volume*, or press `Cmd/Ctrl+K` → *Volume* — **not** from the Settings tab.)

> **Build failing with `No GitHub artifact attestations found for python@3.11.9`?** This is a Railpack/`mise` quirk, not a code issue. Add the variable `MISE_PYTHON_GITHUB_ATTESTATIONS=false` and redeploy.

> **`TelegramConflictError: terminated by other getUpdates request`?** Long-polling allows only one poller per bot token. Make sure the bot isn't also running locally (or anywhere else) at the same time.

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

Super admins and any admin added via `/add_admin` can use these:

| Command          | Description                                           |
| ---------------- | ----------------------------------------------------- |
| `/panel`         | Stats dashboard (incl. Pending AI) + inline buttons   |
| `/bugs`          | Latest 20 bugs with status buttons on each            |
| `/export_csv`    | Download all bugs as CSV                              |
| `/export_excel`  | Download all bugs as XLSX                             |
| `/reanalyze`     | Re-run AI on all reports that weren't analyzed yet     |

**Super-admin-only** commands:

| Command                     | Description                                                  |
| --------------------------- | ------------------------------------------------------------ |
| `/admin`                    | Inline menu with every admin action (super admin only)       |
| `/add_admin <id> [name]`    | Grant a Telegram user ID admin access (report viewing)       |
| `/remove_admin <id>`        | Revoke an admin                                              |
| `/admins`                   | List all super admins and admins                            |
| `/backup`                   | Get a consistent snapshot of the database as a Telegram file |

Anyone (not just admins) can use `/myid` to see their own numeric Telegram ID — useful for `/add_admin`.

### Roles & anonymity

There are two roles:

- **Super admin** — set via `SUPER_ADMIN_IDS` (env). Full control: manages admins, takes backups, and is the only role whose own reports can carry an identity.
- **Admin** — added at runtime by a super admin with `/add_admin <id>` (stored in the `admins` table). Can view/triage/export reports, but cannot manage admins or take backups.

**Anonymity rule:** every report from anyone other than a super admin is stored **without a name or sender ID** (reporter shows as `ناشناس`). This keeps tester reports private.

When a **super admin** submits a report, the bot asks — per report — whether to file it **with their name** (`👤 با نام من`) or keep it **anonymous** (`🕶 ناشناس بماند`). The report is saved immediately (anonymous by default); the buttons just attach or strip the identity afterwards.

### Backups

The database is a single SQLite file (on Railway, on a mounted Volume — see deployment). Two backup paths:

- **On demand:** a super admin sends `/backup` and receives the database as a Telegram document.
- **Automatic:** every 24 hours the bot sends a fresh snapshot to every super admin.

Backups use SQLite's online backup API, so they are consistent even while the bot is writing. Because the file lands in your Telegram chat, it doubles as off-site storage.

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

A second table tracks runtime-added admins:

```sql
CREATE TABLE admins (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    added_by INTEGER,
    added_at TEXT
);
```

> An existing database from an older version is migrated automatically on startup (the `ai_status` column is added with `ALTER TABLE`, and the `admins` table is created with `CREATE TABLE IF NOT EXISTS`).

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
├── Procfile
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
