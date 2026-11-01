"""Message formatters for bot responses."""

from datetime import timedelta
from typing import Optional

from bot.utils.permissions import get_role_name


def format_duration(minutes: Optional[int] | timedelta) -> str:
    """Format mute/ban duration into human readable text."""
    if isinstance(minutes, timedelta):
        total = max(0, int(minutes.total_seconds()))
        if total < 60:
            return f"{total} сек."
        minutes = total // 60
    if not minutes or minutes <= 0:
        return "0"
    if minutes < 60:
        return f"{minutes} мин"
    hours = minutes // 60
    rest = minutes % 60
    if rest == 0:
        return f"{hours} ч"
    return f"{hours} ч {rest} мин"


def format_warns(warns: Optional[int]) -> str:
    """Format warns counter."""
    return str(int(warns or 0))


def format_mute_status(is_muted: Optional[bool], muted_until: Optional[str]) -> str:
    """Format mute status text."""
    if not is_muted:
        return "нет"
    return f"до {muted_until}" if muted_until else "да"


def format_staff(members: list) -> str:
    """Format staff list for reply text."""
    lines = []
    for member in members or []:
        user_id = member.get("user_id")
        role = member.get("role", 0)
        nickname = member.get("nickname")
        lines.append(f"• {user_id} — {nickname or 'без ника'} (уровень {role})")
    return "\n".join(lines) if lines else "В чате нет модераторов"


def format_top(stats: list, users: list) -> str:
    """Format top users by messages."""
    if not stats:
        return "Пока нет статистики"
    lines = []
    for row in stats[:10]:
        user_id = row.get("user_id")
        count = row.get("count", 0)
        lines.append(f"• {user_id} — {count} сообщений")
    return "\n".join(lines)


def format_punishments(punishments: list) -> str:
    """Format punishment history entries."""
    lines = []
    for p in punishments or []:
        lines.append(f"- {p.get('type')} | {p.get('target_id')} | {p.get('reason') or ''} | {p.get('created_at')}")
    return "\n".join(lines) if lines else "История пуста"


def format_ban(ban: Optional[dict]) -> str:
    """Format ban record."""
    if not ban:
        return "Пользователь не забанен"
    return f"Забанен: {ban.get('user_id')} (причина: {ban.get('reason') or 'нет'})"


def format_user_mention(user_id: int, name: Optional[str] = None) -> str:
    return f"[id{user_id}|{name or f'ID {user_id}'}]"


def format_user_link(user_id: int) -> str:
    return f"https://vk.com/id{user_id}"


def format_stats_entry(entry: dict, position: int, user_name: Optional[str] = None) -> str:
    mention = user_name or format_user_mention(entry["user_id"])
    return f"{position}. {mention} — {entry.get('count', 0)} сообщ."


def format_user_info(
    user_id: int,
    chat_id: int,
    member_data: dict,
    stats_data: Optional[dict] = None,
    name: Optional[str] = None,
) -> str:
    lines = [
        f"👤 {format_user_mention(user_id, name)}",
        f"🆔 ID: {user_id}",
        f"Оригинальная ссылка пользователя: {format_user_link(user_id)}",
        f"🎭 Роль: {get_role_name(member_data.get('role', 0))} "
        f"({member_data.get('role', 0)})",
    ]
    if member_data.get("nickname"):
        lines.append(f"🏷 Ник: {member_data['nickname']}")
    if member_data.get("warns"):
        lines.append(f"⚠️ Предупреждений: {member_data['warns']}")
    if member_data.get("is_muted"):
        lines.append(f"🔇 Мут до: {member_data.get('muted_until') or 'снят вручную'}")
    if stats_data:
        lines.append(f"💬 Сообщений: {stats_data.get('count', 0)}")
        if stats_data.get("last_message_at"):
            lines.append(f"🕐 Последнее сообщение: {stats_data['last_message_at']}")
    return "\n".join(lines)


def format_punishment(punishment: dict) -> str:
    reason = f" | Причина: {punishment['reason']}" if punishment.get("reason") else ""
    moderator = punishment.get("moderator_id")
    created = punishment.get("created_at", "")
    target = punishment.get("target_id")
    return (
        f"• {punishment.get('type', '?')} "
        f"{format_user_mention(target) if target else ''}{reason} | "
        f"Модератор: {format_user_mention(moderator) if moderator else '?'} | {created}"
    )


def format_warn(warning: dict) -> str:
    return format_punishment(warning)


def format_mute(mute: dict) -> str:
    result = format_punishment(mute)
    if mute.get("duration"):
        result += f" | Длительность: {mute['duration']}"
    return result


def format_chat_info(chat_data: dict, member_count: int = 0) -> str:
    settings = chat_data.get("settings") or {}
    return (
        f"💬 Беседа: {chat_data.get('title') or 'Без названия'}\n"
        f"🆔 Chat ID: {chat_data['chat_id']}\n"
        f"✅ Статус: {'Активна' if chat_data.get('is_active') else 'Неактивна'}\n"
        f"👥 Участников: {member_count}\n"
        f"🏷 Антитег: {'включён' if settings.get('antitag') else 'выключен'}\n"
        f"🔕 Тишина: {'включена' if settings.get('timeout') else 'выключена'}"
    )


def format_help_text(user_role: int, selected_level: Optional[int] = None) -> str:
    from bot.utils.permissions import COMMAND_DESCRIPTIONS, COMMAND_PERMISSIONS

    max_level = max(0, min(6, int(user_role)))
    level = max_level if selected_level is None else max(
        0, min(max_level, int(selected_level))
    )
    role_name = get_role_name(level)
    lines = [
        f"📋 Команды для уровня {level} — {role_name}",
        "Команды, доступные этому уровню:",
    ]
    for name, required in sorted(COMMAND_PERMISSIONS.items()):
        if required <= level:
            description = COMMAND_DESCRIPTIONS.get(name, "Описание пока не добавлено.")
            lines.append(f"/{name} — {description}")
    return "\n".join(lines)


def format_help_level_text(user_role: int, selected_level: int) -> str:
    return format_help_text(user_role, selected_level)


def format_staff_list(members: list[dict]) -> str:
    if not members:
        return "👮 Администрация отсутствует."
    lines = ["👮 Администрация беседы:"]
    for member in members:
        user_id = member["user_id"]
        lines.append(
            f"• {format_user_mention(user_id, member.get('nickname'))} "
            f"— уровень {member.get('role', 0)}"
        )
    return "\n".join(lines)


def format_nick_list(members: list[dict]) -> str:
    nicknames = [member for member in members if member.get("nickname")]
    if not nicknames:
        return "📋 Никнеймы не установлены."
    return "\n".join(
        f"• {format_user_mention(row['user_id'], row['nickname'])}"
        for row in nicknames
    )


def format_global_nick_list(nicknames: list[dict]) -> str:
    if not nicknames:
        return "🌐 Глобальные никнеймы не установлены."
    return "\n".join(
        f"• {format_user_mention(row['user_id'], row['nickname'])}"
        for row in nicknames
    )
