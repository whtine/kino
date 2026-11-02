# Kino — VK Chat Moderation Bot

VK bot for chat moderation with role-based permissions (levels 0-4), Supabase database, deployed on a Render Web Service.

## Features

- **Activation system**: bot joins chat → inactive by default; a VK chat administrator activates it via `/activate` (or `*`), and receives role 4.
- **Role system**: levels 0-4 only: participant, movie moderator, administrator, department deputy, and department head.
- **Moderation**: kick, mute, warn, clear, ban, timeout, logs.
- **Nicknames**: local (per chat) and global (per group).
- **Global commands**: /zov, /gzov, /antitag, /pin, /unpin, /gban, /gunban, /gsnick, /grnick.
- **Statistics**: message tracking, /top.
- **Logs**: punishment history.

## Tech Stack

- Python 3.11+
- vkbottle 4.10 (async VK API, Long Poll)
- Supabase (PostgreSQL) with service_role key
- Render Web Service (free tier) with a small HTTP health endpoint alongside VK Long Poll

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

Use the Supabase server-side secret key (`sb_secret_...`) or legacy `service_role` JWT for `SUPABASE_KEY`. The Supabase Python SDK is pinned to a version that supports both key formats. A `sb_publishable_...` key is intended for client-side use and is not suitable for this bot's database access; the app rejects that key format at startup. Never put a real secret in source code or commit it. For Render, set the same values in the service's Environment settings.

`GROUP_ID` is the VK community ID used by Long Poll, not a chat ID. No chat ID is configured in an environment variable; the bot can be activated independently in every conversation it joins.
At startup, the bot enables the Long Poll `message_event` update used by inline buttons. If the group token cannot change Long Poll settings, the startup log will say so; enable **Message event** in the community's Long Poll event settings.

3. Run the migrations in Supabase SQL Editor in order. Existing installations should apply any migrations they have not run yet:

```
db/migrations/001_init.sql
db/migrations/002_feature_updates.sql
db/migrations/003_ban_expirations.sql
db/migrations/004_role_cap_4.sql
```

4. Start the bot:

```bash
python main.py
```

## Deployment

- Create a **Web Service** on Render from the GitHub repository and select the free plan.
- Build command: `pip install -r requirements.txt`; start command: `python main.py`.
- Set `VK_TOKEN`, `GROUP_ID`, `SUPABASE_URL`, and `SUPABASE_KEY` in the Render Environment settings.
- The app listens on Render's `PORT` at `0.0.0.0` and provides `/healthz` for Render health checks. `/` and `/ping` also return HTTP 200.
- To reduce free-tier idle spin-down, add an external HTTP monitor (for example, UptimeRobot) for `https://<your-render-service>.onrender.com/healthz` with a 5-minute interval. Create the monitor only after the first successful deploy and substitute your service's actual `onrender.com` URL.
- A ping monitor can wake the service and reduce idle spin-down, but cannot guarantee uninterrupted free service: Render's free instances have monthly usage limits and may still restart or be suspended.
- Apply the Supabase migrations and use a server-side Supabase key. Keep all secrets in Render's environment settings, not Git.

## Commands

See `bot/utils/permissions.py` (`COMMAND_PERMISSIONS`) for the full command → role mapping.
Mute durations accept Russian units (for example, `/mute 123 30м флуд` or `/mute 123 30 минут флуд`) and are limited to 15–450 minutes. Muted users' messages, including slash commands, are removed until expiry. Local and department bans may last up to 350 days; an omitted duration means permanent.
`/rep` allows one vote for each other user per chat. Cross-chat operations only target conversations explicitly linked to the same department with `/bind`; `/sban`, `/sunban`, `/ssnick`, `/srnick`, `/skick`, and `/szov` act on the bound chats. `/async timeout on|off` applies silence mode to those chats. Department aliases are `/otdel`, `/delotdel`, and `/myotdel`.
In an inactive chat, only `/start` and `/activate` (or `*`) are accepted. `/start` displays the activation button; inviting new members triggers a welcome message with `/info`.
`/help` displays commands with descriptions; inline role buttons show only commands assigned to the selected level. `/getban` (level 2+) lists active bans in the current chat and, when it belongs to a group, that group's bans across synchronized chats.
`/info` lists the chat's official links. Role 4 can add links with `/info add Label https://example.com` and remove them with `/info remove N`.
