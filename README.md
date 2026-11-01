# Kino — VK Chat Moderation Bot

VK bot for chat moderation with role-based permissions (levels 0-6), Supabase database, deployed on Render Background Worker.

## Features

- **Activation system**: bot joins chat → inactive by default; a VK chat administrator activates it via `/activate` (or `*`), and receives role 6 for setup.
- **Role system** (0-6): user, junior moderator, moderator, senior moderator, administrator, senior administrator, special rights.
- **Moderation**: kick, mute, warn, clear, ban, timeout, logs.
- **Nicknames**: local (per chat) and global (per group).
- **Global commands**: /zov, /gzov, /antitag, /pin, /unpin, /gban, /gunban, /gsnick, /grnick.
- **Statistics**: message tracking, /top.
- **Logs**: punishment history.

## Tech Stack

- Python 3.11+
- vkbottle 4.10 (async VK API, Long Poll)
- Supabase (PostgreSQL) with service_role key
- Render Background Worker (free tier)

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set the required values as Windows user environment variables from PowerShell:

```powershell
[Environment]::SetEnvironmentVariable("VK_TOKEN", "your_vk_group_token", "User")
[Environment]::SetEnvironmentVariable("GROUP_ID", "your_vk_community_id", "User")
[Environment]::SetEnvironmentVariable("SUPABASE_URL", "https://your-project.supabase.co", "User")
[Environment]::SetEnvironmentVariable("SUPABASE_KEY", "your_server_side_secret_key", "User")
```

Open a new terminal after setting these values, then run `python main.py`. The app reads configuration directly from OS environment variables with `os.getenv`; it does not load `.env` files. `.env.example` is only a list of variable names and placeholders.

Use the Supabase server-side secret/service-role key for `SUPABASE_KEY`. A `sb_publishable_...` key is intended for client-side use and is not suitable for this bot's database access; the app rejects that key format at startup. Never put a real secret in source code or commit it. For Render, set the same values in the service's Environment settings.

`GROUP_ID` is the VK community ID used by Long Poll, not a chat ID. No chat ID is configured in an environment variable; the bot can be activated independently in every conversation it joins.

3. Run the migrations in Supabase SQL Editor in order. If `001_init.sql` has already been applied, run only `002_feature_updates.sql`:

```
db/migrations/001_init.sql
db/migrations/002_feature_updates.sql
```

4. Start the bot:

```bash
python main.py
```

## Deployment

- GitHub repository with code.
- Render.yaml for Background Worker.
- Environment variables: VK_TOKEN, GROUP_ID, SUPABASE_URL, SUPABASE_KEY.
- Supabase project with schema from migrations/001_init.sql.
- New VK community token (old one compromised).

## Commands

See `bot/utils/permissions.py` (`COMMAND_PERMISSIONS`) for the full command → role mapping.
Mute durations use `с`, `м`, `ч`, or `д` (for example, `/mute 123 30м флуд`).
`/rep` allows one vote for each other user per chat. `/async timeout on|off` applies silence mode to active chats in the bound group.
