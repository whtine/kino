# VK Bot Project Plan & Requirements

## Project Overview
VK Bot for chat moderation with role-based permissions (levels 0-6), Supabase database, deployed on a Render Web Service.

## Core Requirements

### 1. Activation System
- Bot joins chat → inactive by default
- Activation command: `*` (asterisk) or `/activate`
- Commands and moderation only work after activation; activation requires a VK chat administrator
- Chat state persisted in Supabase

### 2. Role System (0-6)
| Level | Name | Key Commands |
|-------|------|--------------|
| 0 | Пользователь | /id, /stats, /top, /chatid, /rep, /help |
| 1 | Младший модератор | /kick, /mute, /warn, /clear, /staff, /olist, /getnick, /snick, /rnick, /nlist, /check, /gnick, /getwarn |
| 2 | Модератор | /unmute, /unwarn, /mutelist, /warnlist, /addmlmoder, /delmlmoder |
| 3 | Старший модератор | /ban, /unban, /timeout, /zov, /addmoder, /logs |
| 4 | Администратор | /skick, /gban, /gunban, /gsnick, /grnick, /gzov, /addstmoder |
| 5 | Старший администратор | /chat, /antitag, /pin, /unpin, /addadmin |
| 6 | Спец. права | /mygroups, /creategroup, /delgroup, /async, /bind, /giveowner, /settings, /import, /bindlist |

### 3. Database (Supabase/PostgreSQL)
Tables:
- `chat_groups` - groups of chats for global commands
- `chats` - individual chats, activation status, settings
- `chat_group_bindings` - many-to-many chat↔group
- `chat_members` - users in chats with roles, nicknames, warns, mutes
- `global_bans` - bans per group
- `global_nicknames` - nicknames per group
- `punishments` - history log of all actions
- `message_stats` - message counts for /top

### 4. Key Features
- **Moderation**: kick, mute, warn, ban, clear messages
- **Nicknames**: local (per chat) and global (per group)
- **Roles**: assign/remove roles with commands
- **Global commands**: apply to all chats in a group
- **Statistics**: message tracking, top users
- **Logs**: punishment history, user logs
- **Timeout/silence mode**: temporary chat mute
- **Mentions (@all)**: /zov and /gzov
- **Pin/unpin messages**
- **Antitag**: prevent mentioning specific users

### 5. Technical Stack
- **Language**: Python 3.11+
- **Framework**: vkbottle 4.10 (async VK API)
- **Database**: Supabase (PostgreSQL) with service_role key
- **Deployment**: Render Web Service (free tier) with an HTTP health endpoint
- **Long Poll**: Group Long Poll (no webhook needed)
- **CI/CD**: GitHub Actions → Render auto-deploy

### 6. Deployment Requirements
- GitHub repository with code
- Render.yaml for a Web Service
- Environment variables: VK_TOKEN, GROUP_ID, SUPABASE_URL, SUPABASE_KEY
- Supabase project with schema from migrations/001_init.sql
- New VK community token (old one compromised)

### 7. File Structure
```
kino/
├── config.py
├── requirements.txt
├── render.yaml
├── .env.example
├── .github/workflows/deploy.yml
├── main.py
├── bot/
│   ├── __init__.py
│   ├── dispatcher.py
│   ├── middlewares/
│   │   ├── __init__.py
│   │   ├── activation.py
│   │   ├── role_check.py
│   │   └── stats.py
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── activation.py
│   │   ├── user.py
│   │   ├── moderation.py
│   │   ├── nicknames.py
│   │   ├── roles.py
│   │   ├── global_cmds.py
│   │   ├── groups.py
│   │   ├── settings.py
│   │   └── ownership.py
│   ├── keyboards.py
│   └── utils/
│       ├── __init__.py
│       ├── vk_api.py
│       ├── formatters.py
│       └── permissions.py
└── db/
    ├── __init__.py
    ├── supabase.py
    ├── repositories/
    │   ├── __init__.py
    │   ├── chats.py
    │   ├── members.py
    │   ├── punishments.py
    │   ├── stats.py
    │   ├── groups.py
    │   └── global_bans.py
    └── migrations/
        └── 001_init.sql
```

### 8. Next Steps to Complete
1. ✅ Config, requirements, DB schema, Supabase client
2. ✅ Repositories (chats, members, punishments, stats, groups, global_bans)
3. ✅ Utils: formatters.py, vk_api.py
4. ✅ Middlewares: activation, role_check, stats
5. ✅ Command handlers (consolidated in `bot/handlers/commands.py` with activation in `activation.py`)
6. ✅ Keyboards
7. ✅ Dispatcher (bot setup)
8. ✅ Main.py (Long Poll loop)
9. ✅ Deployment files (render.yaml, .github/workflows/deploy.yml, .env.example)
10. ✅ README.md with setup instructions

### 9. User Action Items
- Create GitHub repo and push code
- Create Supabase project, run 001_init.sql in SQL Editor
- Get new VK community token with messages/manage permissions
- Get Supabase service_role key (not publishable!)
- Create Render Web Service, connect GitHub repo, and configure an external health monitor if desired
- Set environment variables in Render dashboard
- Bot will auto-deploy on push to main