import asyncio
import json
import logging
import re
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlsplit

from vkbottle.bot import Blueprint, Message, MessageEvent

from bot.utils.formatters import (
    format_ban_list,
    format_duration,
    format_help_level_text,
    format_help_text,
    format_punishment,
    format_stats_entry,
    format_user_info,
    format_user_mention,
)
from bot.utils.permissions import MAX_HELP_ROLE, get_required_role, get_role_name
from bot.keyboards import (
    get_help_keyboard,
    get_nick_list_keyboard,
    get_punishment_keyboard,
)
from bot.utils.vk_api import vk_api
from config import config
from db.repositories.chats import ChatsRepository
from db.repositories.global_bans import GlobalBansRepository
from db.repositories.groups import GroupsRepository
from db.repositories.members import MembersRepository
from db.repositories.punishments import PunishmentsRepository
from db.repositories.stats import StatsRepository

logger = logging.getLogger(__name__)
bp = Blueprint("commands")

chats = ChatsRepository()
members = MembersRepository()
punishments = PunishmentsRepository()
stats = StatsRepository()
groups = GroupsRepository()
global_data = GlobalBansRepository()

TARGET_PATTERN = re.compile(r"^(?:\[id|@id)(\d+)(?:\||\])?")
_SEEN_MESSAGE_TTL_SECONDS = 120
_MAX_SEEN_MESSAGES = 4096
_seen_messages: OrderedDict[tuple[int, int], float] = OrderedDict()
_CLEAR_RESULT_DELETE_DELAY_SECONDS = 5 * 60
_NICK_LIST_PAGE_SIZE = 10
_COMMAND_ALIASES = {
    "sban": "gban",
    "sunban": "gunban",
    "ssnick": "gsnick",
    "srnick": "grnick",
    "szov": "gzov",
    "otdel": "creategroup",
    "delotdel": "delgroup",
    "myotdel": "mygroups",
}


def _parts(text: str) -> tuple[str, list[str]]:
    pieces = text.strip().split()
    command = pieces[0].split("@", 1)[0][1:].lower()
    return command, pieces[1:]


def _help_level_from_payload(message: Message) -> Optional[int]:
    payload = getattr(message, "payload", None)
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict) or payload.get("cmd") != "help_level":
        return None
    level = payload.get("level")
    if (
        isinstance(level, bool)
        or not isinstance(level, int)
        or not 0 <= level <= MAX_HELP_ROLE
    ):
        return None
    return level


def _is_duplicate_message(message: Message) -> bool:
    message_id = getattr(message, "conversation_message_id", 0)
    peer_id = getattr(message, "peer_id", 0)
    if not message_id or not peer_id:
        return False

    now = time.monotonic()
    while _seen_messages:
        _, seen_at = next(iter(_seen_messages.items()))
        if now - seen_at <= _SEEN_MESSAGE_TTL_SECONDS:
            break
        _seen_messages.popitem(last=False)

    key = (peer_id, message_id)
    if key in _seen_messages:
        return True

    _seen_messages[key] = now
    if len(_seen_messages) > _MAX_SEEN_MESSAGES:
        _seen_messages.popitem(last=False)
    return False


def _target_from_args(message: Message, args: list[str]) -> tuple[Optional[int], list[str]]:
    if message.reply_message and message.reply_message.from_id > 0:
        return message.reply_message.from_id, args
    if args:
        token = args[0]
        mention = TARGET_PATTERN.match(token)
        if mention:
            return int(mention.group(1)), args[1:]
        token = token.lstrip("@").strip()
        if token.isdigit() and int(token) > 0:
            return int(token), args[1:]
    return None, args


async def _ensure_chat(message: Message) -> tuple[int, int]:
    chat_id = message.peer_id
    if chat_id < 2_000_000_000:
        raise ValueError("Команда доступна только в беседе.")
    if message.from_id <= 0:
        raise ValueError("Команда доступна только пользователям.")
    return chat_id, message.from_id


async def _bound_group(chat_id: int) -> Optional[int]:
    chat = await chats.get(chat_id)
    return int(chat["group_id"]) if chat and chat.get("group_id") else None


async def _active_bound_chats(group_id: int) -> list[int]:
    active = []
    for bound_chat in await groups.get_bound_chats(group_id):
        chat = await chats.get(bound_chat)
        if chat and chat.get("is_active"):
            active.append(bound_chat)
    return active


async def _can_moderate(
    message: Message, chat_id: int, actor_id: int, target_id: int
) -> bool:
    if actor_id == target_id:
        await message.answer("⛔ Нельзя применять эту команду к себе.")
        return False
    actor_role = await members.get_role(chat_id, actor_id)
    target_role = await members.get_role(chat_id, target_id)
    if target_role >= actor_role:
        await message.answer("⛔ Нельзя применять эту команду к пользователю с равной или старшей ролью.")
        return False
    return True


async def _named_mention(chat_id: int, user_id: int) -> str:
    names = await vk_api.get_member_names(chat_id, [user_id]) if vk_api else {}
    return format_user_mention(user_id, names.get(user_id) or f"ID {user_id}")


async def _add_log(
    chat_id: int,
    target_id: int,
    moderator_id: int,
    kind: str,
    reason: Optional[str] = None,
    duration: Optional[timedelta] = None,
) -> dict:
    record = await punishments.add(chat_id, target_id, moderator_id, kind, reason, duration)
    if not record:
        raise RuntimeError(f"Не удалось сохранить запись действия {kind}.")
    return record


async def _revoke_role_after_removal(
    chat_id: int, target_id: int, actor_id: int, reason: str
) -> None:
    previous_role = await members.get_role(chat_id, target_id)
    if previous_role == 0:
        return
    if not await members.set_role(chat_id, target_id, 0):
        raise RuntimeError(f"Не удалось снять роль пользователя {target_id}.")
    await _add_log(
        chat_id,
        target_id,
        actor_id,
        "role_change",
        f"{reason} Роль: {get_role_name(previous_role)} ({previous_role}) → "
        f"{get_role_name(0)} (0)",
    )


async def _owned_group_for(owner_id: int, reference: str) -> Optional[dict]:
    owned_groups = await groups.get_by_owner(owner_id)
    reference = reference.strip()
    if reference.isdigit():
        group_id = int(reference)
        return next((item for item in owned_groups if item["id"] == group_id), None)
    normalized = reference.casefold()
    return next(
        (
            item
            for item in owned_groups
            if str(item["name"]).casefold() == normalized
        ),
        None,
    )


async def _render_nick_list(
    chat_id: int, page: int
) -> tuple[str, str]:
    entries = [
        entry
        for entry in await members.get_all_in_chat(chat_id)
        if entry.get("nickname")
    ]
    entries.sort(
        key=lambda entry: (
            str(entry["nickname"]).casefold(),
            int(entry["user_id"]),
        )
    )
    page_count = max(1, (len(entries) + _NICK_LIST_PAGE_SIZE - 1) // _NICK_LIST_PAGE_SIZE)
    page = max(0, min(page, page_count - 1))
    start = page * _NICK_LIST_PAGE_SIZE
    current_page = entries[start:start + _NICK_LIST_PAGE_SIZE]
    names = (
        await vk_api.get_member_names(
            chat_id, [int(entry["user_id"]) for entry in current_page]
        )
        if vk_api
        else {}
    )
    lines = [f"🏷 Пользователей с ником: {len(entries)}"]
    for index, entry in enumerate(current_page, start=1):
        user_id = int(entry["user_id"])
        name = names.get(user_id) or f"ID {user_id}"
        lines.append(
            f"{start + index}) [id{user_id}|{name}] — {entry['nickname']}"
        )
    lines.append(f"Страница {page + 1}/{page_count}")
    return "\n".join(lines), get_nick_list_keyboard(page, page_count)


async def _delete_clear_messages_later(chat_id: int, cmids: list[int]) -> None:
    await asyncio.sleep(_CLEAR_RESULT_DELETE_DELAY_SECONDS)
    if not vk_api or not await vk_api.delete_message(chat_id, cmids):
        logger.warning(
            "Could not delete /clear command and result messages %s in chat %s after delay",
            cmids,
            chat_id,
        )


def _schedule_clear_message_cleanup(chat_id: int, command_cmid: int, response) -> None:
    response_cmid = getattr(response, "conversation_message_id", None)
    cmids = list(dict.fromkeys(cmid for cmid in (command_cmid, response_cmid) if cmid))
    if not cmids:
        logger.error(
            "Could not schedule /clear message cleanup in chat %s: no message IDs",
            chat_id,
        )
        return
    asyncio.create_task(
        _delete_clear_messages_later(chat_id, cmids),
        name=f"clear-message-cleanup-{chat_id}",
    )


@bp.on.chat_message()
async def command_router(message: Message):
    text = (message.text or "").strip()
    help_level = _help_level_from_payload(message)
    if help_level is not None:
        command, args = "help", [str(help_level)]
    elif text.startswith("/") and text.split():
        command, args = _parts(text)
    else:
        return
    invoked_command = command
    command = _COMMAND_ALIASES.get(command, command)
    activation_command = str(config.activation_command or "/activate").strip()
    activation_command = activation_command.lstrip("/").split("@", 1)[0].lower()
    if command in {"activate", "deactivate", activation_command}:
        return
    if command == "start":
        return
    if _is_duplicate_message(message):
        logger.debug(
            "Ignoring duplicate command event %s in chat %s",
            message.conversation_message_id,
            message.peer_id,
        )
        return
    try:
        chat_id, user_id = await _ensure_chat(message)
        if command in {"help", "start"}:
            user_role = await members.get_role(chat_id, user_id)
            selected_level = (
                min(MAX_HELP_ROLE, int(args[0]))
                if args and args[0].isdigit()
                else min(MAX_HELP_ROLE, user_role)
            )
            text = format_help_level_text(user_role, selected_level)
            await message.answer(
                text,
                keyboard=get_help_keyboard(user_role, selected_level),
            )
            return
        if command == "id":
            target_id, _ = _target_from_args(message, args)
            target_id = target_id or user_id
            member = await members.get_or_create(chat_id, target_id)
            stat = await stats.get_user_stats(chat_id, target_id)
            names = await vk_api.get_member_names(chat_id, [target_id]) if vk_api else {}
            await message.answer(
                format_user_info(target_id, chat_id, member, stat, names.get(target_id))
            )
            return
        if command == "stats":
            target_id, _ = _target_from_args(message, args)
            target_id = target_id or user_id
            member = await members.get_or_create(chat_id, target_id)
            stat = await stats.get_user_stats(chat_id, target_id)
            role = member.get("role", 0)
            role_name = get_role_name(role)
            assignment = await punishments.get_latest_role_assignment(
                chat_id, target_id, role, role_name
            )
            assigned_at = assignment.get("created_at") if assignment else None
            if assigned_at:
                try:
                    if isinstance(assigned_at, str):
                        assigned_at = datetime.fromisoformat(
                            assigned_at.replace("Z", "+00:00")
                        )
                    assigned_at = assigned_at.astimezone(timezone.utc).strftime(
                        "%d.%m.%Y %H:%M UTC"
                    )
                except (AttributeError, TypeError, ValueError):
                    logger.warning(
                        "Could not format role assignment date for user %s in chat %s",
                        target_id,
                        chat_id,
                    )
                    assigned_at = None
            names = await vk_api.get_member_names(chat_id, [target_id]) if vk_api else {}
            await message.answer(
                f"Nick_Name: {names.get(target_id) or member.get('nickname') or 'Не указано'}\n"
                f"ID: {target_id}\n"
                f"Должность: {role_name}\n"
                f"Кол-во сообщений в беседе: {stat.get('count', 0) if stat else 0}\n"
                f"Дата постановления: {assigned_at or 'Не указана'}"
            )
            return
        if command == "chatid":
            await message.answer(f"🆔 ID беседы: {chat_id}")
            return
        if command == "info":
            chat = await chats.get(chat_id)
            settings = (chat or {}).get("settings") or {}
            links = settings.get("info_links") or []
            if not isinstance(links, list) or any(
                not isinstance(link, dict)
                or not isinstance(link.get("label"), str)
                or not isinstance(link.get("url"), str)
                for link in links
            ):
                raise RuntimeError("Некорректный формат официальных ссылок в настройках беседы.")
            action = args[0].lower() if args else ""
            if action in {"add", "remove", "удалить", "добавить"}:
                role = await members.get_role(chat_id, user_id)
                if role < 4:
                    await message.answer(
                        "⛔ Настраивать официальные ссылки могут пользователи с ролью 4."
                    )
                    return

                if action in {"add", "добавить"}:
                    if len(args) < 3:
                        await message.answer(
                            "Использование: /info add Название ссылки https://example.com"
                        )
                        return
                    label = " ".join(args[1:-1]).strip()[:64]
                    url = args[-1].strip()
                    parsed_url = urlsplit(url)
                    if (
                        not label
                        or len(url) > 500
                        or parsed_url.scheme not in {"http", "https"}
                        or not parsed_url.netloc
                    ):
                        await message.answer(
                            "Укажите название и корректную ссылку, начинающуюся с http:// или https://."
                        )
                        return
                    if len(links) >= 20:
                        await message.answer("Можно добавить не более 20 ссылок.")
                        return
                    links.append({"label": label, "url": url})
                    if not await chats.update_settings(chat_id, {"info_links": links}):
                        raise RuntimeError("Не удалось сохранить официальные ссылки.")
                    await message.answer(f"✅ Ссылка «{label}» добавлена в /info.")
                    return

                if len(args) != 2 or not args[1].isdigit():
                    await message.answer("Использование: /info remove НОМЕР")
                    return
                index = int(args[1]) - 1
                if not 0 <= index < len(links):
                    await message.answer("Ссылки с таким номером нет. Посмотрите список: /info")
                    return
                removed = links.pop(index)
                if not await chats.update_settings(chat_id, {"info_links": links}):
                    raise RuntimeError("Не удалось удалить официальную ссылку.")
                await message.answer(f"✅ Ссылка «{removed.get('label', 'без названия')}» удалена.")
                return

            if not links:
                await message.answer(
                    "Официальные ссылки ещё не добавлены. Пользователь с ролью 4 "
                    "может добавить ссылку командой /info add Название https://example.com."
                )
                return
            lines = ["🔗 Официальные ресурсы отдела:"]
            lines.extend(
                f"{index}) {link['label']}: {link['url']}"
                for index, link in enumerate(links, start=1)
            )
            await message.answer("\n".join(lines))
            return
        if command == "top":
            rows = await stats.get_top(chat_id, 10)
            names = await vk_api.get_member_names(chat_id, [row["user_id"] for row in rows]) if vk_api else {}
            output = ["🏆 Топ участников по сообщениям:"]
            output.extend(
                format_stats_entry(
                    row,
                    index,
                    format_user_mention(
                        row["user_id"],
                        names.get(row["user_id"]) or f"ID {row['user_id']}",
                    ),
                )
                for index, row in enumerate(rows, 1)
            )
            await message.answer("\n".join(output) if rows else "Пока нет статистики.")
            return
        if command == "rep":
            target_id, _ = _target_from_args(message, args)
            if not target_id:
                await message.answer("Ответьте на сообщение пользователя или укажите его ID: /rep [id]")
                return
            if target_id == user_id:
                await message.answer("Нельзя повысить собственную репутацию.")
                return
            from db.supabase import get_supabase
            sb = get_supabase()
            existing = sb.table("chat_reputation").select("target_id").eq(
                "chat_id", chat_id
            ).eq("voter_id", user_id).eq("target_id", target_id).limit(1).execute()
            if existing.data:
                await message.answer("Вы уже голосовали за этого пользователя.")
                return
            try:
                sb.table("chat_reputation").insert({
                    "chat_id": chat_id, "voter_id": user_id, "target_id": target_id
                }).execute()
            except Exception as exc:
                if getattr(exc, "code", None) == 23505 or getattr(exc, "pgcode", None) == "23505":
                    await message.answer("Вы уже голосовали за этого пользователя.")
                    return
                raise
            votes = sb.table("chat_reputation").select("voter_id").eq(
                "chat_id", chat_id
            ).eq("target_id", target_id).execute()
            count = len(votes.data or [])
            target = await _named_mention(chat_id, target_id)
            await message.answer(f"⭐ Репутация {target}: {count}")
            return
        if command in {"staff", "olist"}:
            staff = await members.get_staff(chat_id)
            if command == "olist" and vk_api:
                members_list = await vk_api.get_conversation_members(chat_id)
                present = {
                    member.get("member_id") if isinstance(member, dict) else member.member_id
                    for member in members_list
                }
                staff = [row for row in staff if row["user_id"] in present]
            if not staff:
                await message.answer("👮 Администрация не найдена.")
                return
            names = (
                await vk_api.get_member_names(
                    chat_id, [int(entry["user_id"]) for entry in staff]
                )
                if vk_api
                else {}
            )
            lines = ["Сотрудники отдела:"]
            lines.extend(
                f"• [id{entry['user_id']}|"
                f"{entry.get('nickname') or names.get(entry['user_id']) or entry['user_id']}] "
                f"— {get_role_name(entry['role'])}"
                for entry in staff
            )
            await message.answer("\n".join(lines))
            return
        if command == "check":
            target_id, _ = _target_from_args(message, args)
            if not target_id:
                await message.answer("Ответьте на сообщение или укажите ID пользователя.")
                return
            entry = await members.get_or_create(chat_id, target_id)
            target = await _named_mention(chat_id, target_id)
            await message.answer(
                f"{target}\n"
                f"Роль: {get_role_name(entry['role'])} ({entry['role']})\n"
                f"Предупреждения: {entry.get('warns', 0)}"
            )
            return
        if command == "getwarn":
            target_id, _ = _target_from_args(message, args)
            if not target_id:
                target_id = user_id
            entry = await members.get_or_create(chat_id, target_id)
            target = await _named_mention(chat_id, target_id)
            await message.answer(
                f"⚠️ У {target} "
                f"{entry.get('warns', 0)} предупреждений "
                f"({entry.get('warns', 0)}/3)."
            )
            return
        if command == "warn":
            target_id, rest = _target_from_args(message, args)
            if not target_id:
                await message.answer(
                    "Использование: /warn [id] | [1–3] | причина "
                    "(или ответьте на сообщение)"
                )
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            warn_count = 1
            if "|" in rest:
                parts = " ".join(rest).split("|")
                if len(parts) >= 2 and parts[1].strip().isdigit():
                    warn_count = int(parts[1].strip())
                    reason = "|".join(parts[2:]).strip() or None
                else:
                    reason = "|".join(parts[1:]).strip() or None
            elif rest and rest[0].isdigit() and 1 <= int(rest[0]) <= 3:
                warn_count = int(rest[0])
                reason = " ".join(rest[1:]) or None
            else:
                reason = " ".join(rest) or None
            if not 1 <= warn_count <= 3:
                await message.answer("Можно выдать от 1 до 3 выговоров за раз.")
                return
            target_member = await members.get_or_create(chat_id, target_id)
            if int(target_member.get("warns", 0)) + warn_count > 3:
                await message.answer("У пользователя уже достигнут лимит в 3 выговора.")
                return
            count = await members.add_warn(chat_id, target_id, warn_count)
            record = None
            for _ in range(warn_count):
                record = await _add_log(chat_id, target_id, user_id, "warn", reason)
            names = (
                await vk_api.get_member_names(chat_id, [user_id, target_id])
                if vk_api
                else {}
            )
            moderator = format_user_mention(
                user_id, names.get(user_id) or f"ID {user_id}"
            )
            target = format_user_mention(
                target_id, names.get(target_id) or f"ID {target_id}"
            )
            await message.answer(
                f"⚠️ {moderator} выдал {_count_word(warn_count)} "
                f"{'выговор' if warn_count == 1 else 'выговора'} сотруднику {target}.\n"
                f"По причине: {reason or 'не указана'}\n"
                f"Итог: {count}/3.",
                keyboard=get_punishment_keyboard(
                    "unwarn", target_id, record["id"] if record else None
                ),
            )
            return
        if command == "skick":
            target_id, rest = _target_from_args(message, args)
            group_id = await _bound_group(chat_id)
            if not target_id or not group_id:
                await message.answer(
                    "Укажите пользователя и привяжите беседу к отделу."
                )
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            reason = " ".join(rest) or None
            bound_chats = await groups.get_bound_chats(group_id)
            kicked = 0
            failures = 0
            for bound_chat in bound_chats:
                if not vk_api or not await vk_api.kick_user(bound_chat, target_id):
                    failures += 1
                    continue
                kicked += 1
                await _add_log(bound_chat, target_id, user_id, "skick", reason)
                await _revoke_role_after_removal(
                    bound_chat, target_id, user_id, "Снята при исключении из отдела."
                )
            names = (
                await vk_api.get_member_names(chat_id, [user_id, target_id])
                if vk_api
                else {}
            )
            await message.answer(
                f"👢 {format_user_mention(user_id, names.get(user_id) or f'ID {user_id}')} исключил "
                f"{format_user_mention(target_id, names.get(target_id) or f'ID {target_id}')} "
                f"из бесед отдела: {kicked}. Ошибок: {failures}. "
                f"Причина: {reason or 'не указана'}."
            )
            return
        if command in {"kick", "ban"}:
            target_id, rest = _target_from_args(message, args)
            if not target_id:
                await message.answer(f"Использование: /{command} [id] причина (или ответьте на сообщение)")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            duration, duration_tokens = _duration_from_args(rest)
            if command == "ban" and duration_tokens and not duration:
                await message.answer("Срок блокировки должен быть положительным.")
                return
            if command == "ban" and duration and duration > timedelta(days=350):
                await message.answer("Срок блокировки должен быть не более 350 дней.")
                return
            if command == "ban" and duration_tokens:
                reason = " ".join(rest[duration_tokens:]) or None
            else:
                duration = None
                reason = " ".join(rest) or None
            if command == "ban":
                from db.supabase import get_supabase
                result = get_supabase().table("chat_bans").upsert({
                    "chat_id": chat_id,
                    "user_id": target_id,
                    "reason": reason,
                    "banned_by": user_id,
                    "expires_at": (
                        (datetime.now(timezone.utc) + duration).isoformat()
                        if duration
                        else None
                    ),
                }).select("user_id").execute()
                if not result.data:
                    raise RuntimeError("Не удалось сохранить локальную блокировку.")
            kicked = bool(vk_api and await vk_api.kick_user(chat_id, target_id))
            if not kicked and command != "ban":
                await message.answer("❌ Не удалось исключить пользователя. Проверьте права бота.")
                return
            record = await _add_log(chat_id, target_id, user_id, command, reason, duration)
            if kicked or command == "ban":
                await _revoke_role_after_removal(
                    chat_id, target_id, user_id, "Снята при исключении из беседы."
                )
            names = (
                await vk_api.get_member_names(chat_id, [user_id, target_id])
                if vk_api
                else {}
            )
            moderator = format_user_mention(
                user_id, names.get(user_id) or f"ID {user_id}"
            )
            target = format_user_mention(
                target_id, names.get(target_id) or f"ID {target_id}"
            )
            action_text = {
                "ban": "заблокировал в чате",
                "kick": "исключил",
            }[command]
            duration_text = (
                f" на {duration.days} дней" if duration and duration.days else
                f" на {format_duration(duration)}" if duration else
                " навсегда" if command == "ban" else ""
            )
            notice = (
                f"👢 {moderator} {action_text} {target}{duration_text}.\n"
                f"Причина: {reason or 'не указана'}"
            )
            if command == "ban" and not kicked:
                await message.answer(
                    f"⚠️ {notice}\nНе удалось исключить, блокировка сработает "
                    "при следующем входе.",
                    keyboard=get_punishment_keyboard("unban", target_id, record["id"]),
                )
            else:
                await message.answer(
                    notice,
                    keyboard=get_punishment_keyboard(
                        "unban" if command == "ban" else "restore_kick",
                        target_id,
                        record["id"],
                    ),
                )
            return
        if command == "unban":
            target_id, rest = _target_from_args(message, args)
            if not target_id:
                await message.answer("Укажите ID пользователя.")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            from db.supabase import get_supabase
            sb = get_supabase()
            existing_ban = sb.table("chat_bans").select("user_id").eq(
                "chat_id", chat_id
            ).eq("user_id", target_id).limit(1).execute()
            if not existing_ban.data:
                await message.answer("Пользователь не найден в списке блокировок этой беседы.")
                return
            deleted = (
                sb.table("chat_bans").delete().eq("chat_id", chat_id)
                .eq("user_id", target_id).select("user_id").execute()
            )
            if not deleted.data:
                await message.answer("Блокировка уже была снята.")
                return
            reason = " ".join(rest).strip() or None
            await _add_log(chat_id, target_id, user_id, "unban", reason)
            target = await _named_mention(chat_id, target_id)
            if not vk_api or not await vk_api.add_chat_user(chat_id, target_id):
                await message.answer(
                    "✅ Блокировка снята, но добавить пользователя обратно не удалось.\n"
                    f"Причина: {reason or 'не указана'}."
                )
                return
            await message.answer(
                f"✅ Блокировка в чате с {target} снята.\n"
                f"Причина: {reason or 'не указана'}."
            )
            return
        if command == "getban":
            target_id, _ = _target_from_args(message, args)
            if not target_id:
                await message.answer(
                    "Укажите ID пользователя или ответьте на его сообщение: "
                    "/getban [id]"
                )
                return
            local_ban, group_id = await asyncio.gather(
                chats.get_ban(chat_id, target_id),
                _bound_group(chat_id),
            )
            sections = [
                format_ban_list(
                    [local_ban] if local_ban else [],
                    f"⛔ Блокировка {format_user_mention(target_id)} в этой беседе:",
                )
            ]
            if group_id:
                global_ban = await global_data.is_banned(group_id, target_id)
                sections.append(
                    format_ban_list(
                        [global_ban] if global_ban else [],
                        f"🌐 Глобальная блокировка {format_user_mention(target_id)} "
                        "в синхронизированных беседах:",
                    )
                )
            await message.answer("\n\n".join(sections))
            return
        if command == "mute":
            target_id, rest = _target_from_args(message, args)
            duration, duration_tokens = _duration_from_args(rest)
            if not target_id or not duration:
                await message.answer(
                    "Использование: /mute [id] 15–450м причина "
                    "(например, /mute 123 30 минут флуд)."
                )
                return
            duration_minutes = int(duration.total_seconds() // 60)
            if not 15 <= duration_minutes <= 450:
                await message.answer("Срок мута должен быть от 15 до 450 минут.")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            reason = " ".join(rest[duration_tokens:]) or None
            expires = datetime.now(timezone.utc) + duration
            if not await members.set_mute(chat_id, target_id, True, expires.isoformat()):
                raise RuntimeError("Не удалось сохранить статус мута.")
            record = await _add_log(chat_id, target_id, user_id, "mute", reason, duration)
            names = (
                await vk_api.get_member_names(chat_id, [user_id, target_id])
                if vk_api
                else {}
            )
            moderator = format_user_mention(
                user_id, names.get(user_id) or f"ID {user_id}"
            )
            target = format_user_mention(
                target_id, names.get(target_id) or f"ID {target_id}"
            )
            await message.answer(
                f"🔇 {moderator} выдал затычку в чате пользователю {target}.\n"
                f"Причина: {reason or 'не указана'}\n"
                f"Сколько осталось до снятия мута: {format_duration(duration)}.",
                keyboard=get_punishment_keyboard("unmute", target_id, record["id"]),
            )
            return
        if command == "unmute":
            target_id, rest = _target_from_args(message, args)
            if not target_id:
                await message.answer("Укажите ID или ответьте на сообщение пользователя.")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            if not await members.set_mute(chat_id, target_id, False):
                raise RuntimeError("Не удалось снять мут.")
            reason = " ".join(rest).strip() or None
            await _add_log(chat_id, target_id, user_id, "unmute", reason)
            target = await _named_mention(chat_id, target_id)
            await message.answer(
                f"🔊 Затычка в чате с {target} снята.\n"
                f"Причина: {reason or 'не указана'}."
            )
            return
        if command == "unwarn":
            target_id, rest = _target_from_args(message, args)
            if not target_id:
                await message.answer("Укажите ID или ответьте на сообщение пользователя.")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            amount = int(rest[0]) if rest and rest[0].isdigit() else 1
            if not 1 <= amount <= 3:
                await message.answer("Можно снять от 1 до 3 выговоров за раз.")
                return
            target_member = await members.get_or_create(chat_id, target_id)
            current_warns = int(target_member.get("warns", 0))
            if current_warns < amount:
                await message.answer(
                    f"У пользователя только {current_warns} активных выговоров."
                )
                return
            count = await members.remove_warn(chat_id, target_id, amount)
            for _ in range(amount):
                await _add_log(chat_id, target_id, user_id, "unwarn")
            actor = await _named_mention(chat_id, user_id)
            target = await _named_mention(chat_id, target_id)
            await message.answer(
                f"✅ {actor} снял {_count_word(amount)} "
                f"{'выговор' if amount == 1 else 'выговора'} с "
                f"{target}.\nИтог: {count}/3."
            )
            return
        if command == "clear":
            reply = message.reply_message
            if reply:
                target_id = int(reply.from_id)
                actor_role = await members.get_role(chat_id, user_id)
                if target_id > 0:
                    target_role = await members.get_role(chat_id, target_id)
                    if target_role > actor_role:
                        await message.answer(
                            "⛔ Нельзя удалять сообщения пользователей с более высокой ролью."
                        )
                        return
                elif target_id != -config.group_id:
                    await message.answer(
                        "⛔ Нельзя определить роль автора этого сообщения."
                    )
                    return

                target_cmid = getattr(reply, "conversation_message_id", None)
                if (
                    not target_cmid
                    or not vk_api
                    or not await vk_api.delete_message(chat_id, [target_cmid])
                ):
                    await message.answer(
                        "❌ Не удалось удалить отмеченное сообщение. Проверьте права "
                        "сообщества и администратора беседы на удаление сообщений."
                    )
                    return
                response = await message.answer("✅ Отмеченное сообщение удалено.")
                _schedule_clear_message_cleanup(
                    chat_id,
                    message.conversation_message_id,
                    response,
                )
                return

            if args and args[0].isdigit():
                target_cmid = int(args[0])
                target_message = (
                    await vk_api.get_message_by_cmid(chat_id, target_cmid)
                    if vk_api
                    else None
                )
                if not target_message:
                    await message.answer("Сообщение с таким ID не найдено.")
                    return
                target_id = int(getattr(target_message, "from_id", 0) or 0)
                if target_id == 0:
                    await message.answer("Не удалось определить автора сообщения.")
                    return
                actor_role = await members.get_role(chat_id, user_id)
                if target_id > 0 and await members.get_role(chat_id, target_id) > actor_role:
                    await message.answer(
                        "⛔ Нельзя удалять сообщения пользователей с более высокой ролью."
                    )
                    return
                if target_id < 0 and target_id != -config.group_id:
                    await message.answer(
                        "⛔ Нельзя определить роль автора этого сообщения."
                    )
                    return
                if not vk_api or not await vk_api.delete_message(chat_id, [target_cmid]):
                    await message.answer("❌ Не удалось удалить указанное сообщение.")
                    return
                target = await _named_mention(chat_id, target_id)
                response = await message.answer(
                    f"✅ Сообщение пользователя {target} удалено."
                )
                _schedule_clear_message_cleanup(
                    chat_id, message.conversation_message_id, response
                )
                return

            amount = (
                int(args[1])
                if len(args) > 1
                and args[0].lower() in {"last", "последние"}
                and args[1].isdigit()
                else 1
            )
            if not 1 <= amount <= 100:
                await message.answer("Количество сообщений должно быть от 1 до 100.")
                return
            actor_role = await members.get_role(chat_id, user_id)
            higher_staff = await members.get_staff(chat_id, min_role=actor_role + 1)
            protected_user_ids = {
                int(entry["user_id"]) for entry in higher_staff
            }
            if not vk_api or not await vk_api.clear_recent_messages(
                chat_id,
                amount,
                message.conversation_message_id,
                protected_user_ids,
            ):
                await message.answer(
                    "❌ Не удалось удалить сообщения. При ошибке VK 15 бот "
                    "переключается на сообщения, полученные после последнего запуска. "
                    "Проверьте, что у сообщества включены сообщения и бот добавлен "
                    "в беседу. Старые сообщения VK не отдаёт."
                )
                return
            response = await message.answer(
                "✅ Сообщения удалены. Сообщения пользователей с более высокой "
                "ролью пропущены."
            )
            _schedule_clear_message_cleanup(
                chat_id,
                message.conversation_message_id,
                response,
            )
            return
        if command == "del":
            reply = message.reply_message
            if not reply:
                await message.answer("Ответьте командой /del на сообщение, которое нужно удалить.")
                return
            target_id = int(reply.from_id)
            if target_id > 0:
                target_role = await members.get_role(chat_id, target_id)
                actor_role = await members.get_role(chat_id, user_id)
                if target_role > actor_role:
                    await message.answer(
                        "⛔ Нельзя удалять сообщения пользователей с более высокой ролью."
                    )
                    return
            elif target_id != -config.group_id:
                await message.answer(
                    "⛔ Нельзя определить роль автора этого сообщения."
                )
                return
            cmid = getattr(reply, "conversation_message_id", None)
            if not cmid or not vk_api or not await vk_api.delete_message(chat_id, [cmid]):
                await message.answer(
                    "❌ Не удалось удалить сообщение. Проверьте права сообщества "
                    "и администратора беседы на удаление сообщений."
                )
                return
            await message.answer("✅ Сообщение удалено.")
            return
        if command in {"warnlist", "mutelist", "logs"}:
            if command == "warnlist":
                rows = await punishments.get_warn_list(chat_id)
                title = "⚠️ Активные предупреждения:"
            elif command == "mutelist":
                rows = await punishments.get_mute_list(chat_id)
                title = "🔇 Активные муты:"
            else:
                rows = await punishments.get_recent_logs(chat_id)
                title = "📜 Последние действия:"
            lines = [title] + [format_punishment(row) for row in rows]
            await message.answer("\n".join(lines) if rows else "Записей нет.")
            return
        if command == "timeout":
            if args:
                if args[0].lower() not in {"on", "off", "вкл", "выкл", "1", "0"}:
                    await message.answer("Использование: /timeout [on|off]")
                    return
                enabled = args[0].lower() in {"on", "вкл", "1"}
            else:
                current = await chats.get(chat_id)
                enabled = not bool(
                    ((current or {}).get("settings") or {}).get("timeout")
                )
            if not await chats.update_settings(chat_id, {"timeout": enabled}):
                raise RuntimeError("Не удалось сохранить режим тишины.")
            await message.answer(f"🔕 Режим тишины {'включён' if enabled else 'выключен'}.")
            return
        if command == "zov":
            if not vk_api:
                raise RuntimeError("VK API не инициализирован.")
            mentions = await vk_api.mention_all(chat_id, config.max_mentions_per_zov)
            if not mentions:
                await message.answer("Не удалось получить список участников.")
                return
            names = await vk_api.get_member_names(chat_id, [user_id])
            actor = format_user_mention(
                user_id, names.get(user_id) or f"ID {user_id}"
            )
            await message.answer(
                f"📢 {actor} упомянул участников текущей беседы.\n{mentions}"
            )
            return
        if command in {"snick", "rnick"}:
            target_id, rest = _target_from_args(message, args)
            nickname = " ".join(rest).strip() if rest else ""
            if command == "snick" and (not target_id or not nickname):
                await message.answer("Использование: /snick [id] ник (или ответьте на сообщение)")
                return
            target_id = target_id or user_id
            previous_nickname = await members.get_nickname(chat_id, target_id)
            if command == "snick":
                new_nickname = nickname[:64]
                if not await members.set_nickname(chat_id, target_id, new_nickname):
                    raise RuntimeError("Не удалось сохранить никнейм.")
                await _add_log(
                    chat_id,
                    target_id,
                    user_id,
                    "nickname_set",
                    f"Локальный ник: {previous_nickname or 'не установлен'} → {new_nickname}",
                )
                names = (
                    await vk_api.get_member_names(chat_id, [user_id, target_id])
                    if vk_api
                    else {}
                )
                actor = format_user_mention(
                    user_id, names.get(user_id) or f"ID {user_id}"
                )
                target = format_user_mention(
                    target_id, names.get(target_id) or f"ID {target_id}"
                )
                await message.answer(
                    f"🏷 {actor} изменил никнейм {target}. "
                    f"Новый никнейм: «{new_nickname}»."
                )
            else:
                if not await members.set_nickname(chat_id, target_id, None):
                    raise RuntimeError("Не удалось удалить никнейм.")
                await _add_log(
                    chat_id,
                    target_id,
                    user_id,
                    "nickname_removed",
                    f"Удалён локальный ник: {previous_nickname or 'не установлен'}",
                )
                names = (
                    await vk_api.get_member_names(chat_id, [user_id, target_id])
                    if vk_api
                    else {}
                )
                actor = format_user_mention(
                    user_id, names.get(user_id) or f"ID {user_id}"
                )
                target = format_user_mention(
                    target_id, names.get(target_id) or f"ID {target_id}"
                )
                await message.answer(
                    f"✅ {actor} удалил никнейм у {target}."
                )
            return
        if command == "getnick":
            target_id, _ = _target_from_args(message, args)
            target_id = target_id or user_id
            nickname = await members.get_nickname(chat_id, target_id)
            names = await vk_api.get_member_names(chat_id, [target_id]) if vk_api else {}
            await message.answer(
                f"🏷 Текущий ник пользователя "
                f"{format_user_mention(target_id, names.get(target_id) or f'ID {target_id}')}: "
                f"{nickname or 'не установлен'}."
            )
            return
        if command == "nlist":
            entries = [
                entry
                for entry in await members.get_all_in_chat(chat_id)
                if entry.get("nickname")
            ]
            if not entries:
                await message.answer("📋 Пользователей с ником нет.")
                return
            text, keyboard = await _render_nick_list(chat_id, 0)
            await message.answer(text, keyboard=keyboard)
            return
        if command == "gnick":
            target_id, _ = _target_from_args(message, args)
            group_id = await _bound_group(chat_id)
            if not target_id or not group_id:
                await message.answer("Укажите пользователя и привяжите беседу к группе.")
                return
            nickname = await global_data.get_nickname(group_id, target_id)
            await message.answer(f"🌐 Глобальный ник: {nickname or 'не установлен'}")
            return
        if command in {"gsnick", "grnick"}:
            target_id, rest = _target_from_args(message, args)
            group_id = await _bound_group(chat_id)
            if not target_id or not group_id or (command == "gsnick" and not rest):
                usage = (
                    f"/{invoked_command} [id] ник"
                    if command == "gsnick"
                    else f"/{invoked_command} [id]"
                )
                await message.answer(
                    f"Использование: {usage}; нужна привязанная группа."
                )
                return
            if command == "gsnick":
                previous_nickname = await global_data.get_nickname(group_id, target_id)
                new_nickname = " ".join(rest)[:64]
                if not await global_data.set_nickname(
                    group_id, target_id, new_nickname, user_id
                ):
                    raise RuntimeError("Не удалось сохранить глобальный никнейм.")
                await _add_log(
                    chat_id,
                    target_id,
                    user_id,
                    "global_nickname_set",
                    f"Группа {group_id}: {previous_nickname or 'не установлен'} → {new_nickname}",
                )
                await message.answer("✅ Глобальный ник установлен.")
            else:
                previous_nickname = await global_data.get_nickname(group_id, target_id)
                if not await global_data.remove_nickname(group_id, target_id):
                    await message.answer("Глобальный никнейм не найден.")
                    return
                await _add_log(
                    chat_id,
                    target_id,
                    user_id,
                    "global_nickname_removed",
                    f"Группа {group_id}: удалён ник {previous_nickname or 'не установлен'}",
                )
                await message.answer("✅ Глобальный ник удалён.")
            return
        if command == "mygroups":
            user_groups = await groups.get_by_owner(user_id)
            await message.answer(
                "Ваши отделы:\n"
                + "\n".join(f"• {item['name']} (ID: {item['id']})" for item in user_groups)
                if user_groups
                else "У вас пока нет отделов."
            )
            return
        if command == "creategroup":
            name = " ".join(args).strip()
            if not name:
                await message.answer(
                    f"Укажите название отдела: /{invoked_command} Название"
                )
                return
            group = await groups.create(name[:100], user_id)
            await message.answer(f"✅ Отдел «{group['name']}» создан. ID: {group['id']}")
            return
        if command == "delgroup":
            reference = " ".join(args).strip()
            if not reference:
                await message.answer(
                    f"Использование: /{invoked_command} Название отдела"
                )
                return
            group = await _owned_group_for(user_id, reference)
            if not group:
                await message.answer("Отдел не найден среди ваших отделов.")
                return
            if not await groups.delete(group["id"]):
                raise RuntimeError("Не удалось удалить отдел.")
            await message.answer(f"✅ Отдел «{group['name']}» удалён.")
            return
        if command == "bind":
            reference = " ".join(args).strip()
            if not reference:
                await message.answer("Использование: /bind Название отдела")
                return
            group = await _owned_group_for(user_id, reference)
            if not group:
                await message.answer("Отдел не найден среди ваших отделов.")
                return
            group_id = group["id"]
            current_group_id = await _bound_group(chat_id)
            if current_group_id == group_id:
                await message.answer(f"Эта беседа уже привязана к отделу «{group['name']}».")
                return
            if current_group_id and current_group_id != group_id:
                current_group = await groups.get(current_group_id)
                if not current_group or current_group["owner_id"] != user_id:
                    await message.answer(
                        "⛔ Эта беседа уже связана с чужой группой. "
                        "Её владелец должен сначала выполнить /unbind."
                    )
                    return
            if not await chats.bind_group(chat_id, group_id):
                raise RuntimeError("Не удалось привязать беседу.")
            await message.answer(f"✅ Беседа привязана к отделу «{group['name']}».")
            return
        if command == "unbind":
            group_id = await _bound_group(chat_id)
            if not group_id:
                await message.answer("Эта беседа не привязана к группе.")
                return
            group = await groups.get(group_id)
            if not group or group["owner_id"] != user_id:
                await message.answer(
                    "⛔ Отвязать беседу может только владелец связанной группы."
                )
                return
            if not await chats.unbind_group(chat_id):
                raise RuntimeError("Не удалось отвязать беседу от группы.")
            await message.answer(
                f"✅ Беседа отвязана от группы «{group['name']}». "
                "Синхронизация групповых команд для неё отключена."
            )
            return
        if command == "async":
            group_id = await _bound_group(chat_id)
            if not group_id:
                await message.answer("Беседа не привязана к группе.")
                return
            if not args:
                await message.answer(
                    "Использование: /async timeout on|off. "
                    "Команда применяется ко всем активным беседам группы."
                )
                return
            action = args[0].lower().lstrip("/")
            if action != "timeout" or len(args) != 2 or args[1].lower() not in {
                "on", "off", "вкл", "выкл", "1", "0"
            }:
                await message.answer("Поддерживается: /async timeout on|off")
                return
            enabled = args[1].lower() in {"on", "вкл", "1"}
            bound_chats = await _active_bound_chats(group_id)
            updated = 0
            failures = 0
            for bound_chat in bound_chats:
                if await chats.update_settings(bound_chat, {"timeout": enabled}):
                    updated += 1
                else:
                    failures += 1
            await message.answer(
                f"Режим тишины {'включён' if enabled else 'выключен'} "
                f"в {updated} активных беседах группы. Ошибок: {failures}."
            )
            return
        if command == "bindlist":
            group_id = await _bound_group(chat_id)
            if not group_id:
                await message.answer("Беседа не привязана к группе.")
                return
            bound = await groups.get_bound_chats(group_id)
            await message.answer("Привязанные беседы:\n" + "\n".join(map(str, bound)))
            return
        if command == "giveowner":
            target_id, rest = _target_from_args(message, args)
            if rest:
                group = await _owned_group_for(user_id, " ".join(rest))
            else:
                bound_group_id = await _bound_group(chat_id)
                group = await groups.get(bound_group_id) if bound_group_id else None
            if not target_id or not group:
                await message.answer(
                    "Использование: /giveowner @username Название отдела."
                )
                return
            if not group or group["owner_id"] != user_id:
                await message.answer("⛔ Передать владельца может только владелец группы.")
                return
            if not await groups.update(group["id"], {"owner_id": target_id}):
                raise RuntimeError("Не удалось передать права владельца.")
            await _add_log(
                chat_id,
                target_id,
                user_id,
                "group_owner_change",
                f"Отдел {group['id']}: владелец {user_id} → {target_id}",
            )
            target = await _named_mention(chat_id, target_id)
            await message.answer(
                f"✅ Владение отделом «{group['name']}» передано "
                f"{target}."
            )
            return
        if command == "gban":
            target_id, rest = _target_from_args(message, args)
            group_id = await _bound_group(chat_id)
            if not target_id or not group_id:
                await message.answer(
                    "Укажите пользователя и привяжите беседу к отделу."
                )
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            duration, duration_tokens = _duration_from_args(rest)
            if duration_tokens and not duration:
                await message.answer("Срок блокировки должен быть положительным.")
                return
            if duration and duration > timedelta(days=350):
                await message.answer("Срок блокировки должен быть не более 350 дней.")
                return
            reason = (
                " ".join(rest[duration_tokens:]) if duration_tokens else " ".join(rest)
            ) or None
            if not await global_data.ban(
                group_id, target_id, reason or "", user_id, duration
            ):
                raise RuntimeError("Не удалось сохранить глобальную блокировку.")
            failures = 0
            bound_chats = await groups.get_bound_chats(group_id)
            for bound_chat in bound_chats:
                if not vk_api or not await vk_api.kick_user(bound_chat, target_id):
                    failures += 1
                await _revoke_role_after_removal(
                    bound_chat,
                    target_id,
                    user_id,
                    "Снята при глобальной блокировке.",
                )
            await _add_log(chat_id, target_id, user_id, "gban", reason, duration)
            target = await _named_mention(chat_id, target_id)
            actor = await _named_mention(chat_id, user_id)
            status = f" Не удалось исключить из бесед: {failures}." if failures else ""
            duration_text = (
                f" на {duration.days} дней" if duration and duration.days else
                f" на {format_duration(duration)}" if duration else
                " навсегда"
            )
            await message.answer(
                f"🌐 {actor} заблокировал пользователя {target} во всех чатах "
                f"отдела{duration_text}. Причина: {reason or 'не указана'}.{status}"
            )
            return
        if command == "gunban":
            target_id, rest = _target_from_args(message, args)
            group_id = await _bound_group(chat_id)
            if not target_id or not group_id:
                await message.answer("Укажите ID пользователя; беседа должна быть привязана к группе.")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            removed = await global_data.unban(group_id, target_id)
            if removed:
                reason = " ".join(rest).strip() or None
                await _add_log(chat_id, target_id, user_id, "gunban", reason)
                target = await _named_mention(chat_id, target_id)
                actor = await _named_mention(chat_id, user_id)
                await message.answer(
                    f"✅ {actor} снял глобальную блокировку с "
                    f"{target} во всех чатах отдела.\n"
                    f"Причина: {reason or 'не указана'}."
                )
            else:
                await message.answer("Пользователь не найден в списке глобальных блокировок.")
            return
        if command == "gzov":
            group_id = await _bound_group(chat_id)
            if not group_id or not vk_api:
                await message.answer("Нужна привязанная группа и доступ к VK API.")
                return
            names = await vk_api.get_member_names(chat_id, [user_id])
            actor = format_user_mention(
                user_id, names.get(user_id) or f"ID {user_id}"
            )
            sent = 0
            failures = 0
            bound_chats = await _active_bound_chats(group_id)
            for bound_chat in bound_chats:
                mentions = await vk_api.mention_all(bound_chat, config.max_mentions_per_zov)
                if not mentions:
                    failures += 1
                    continue
                if not await vk_api.send_message(
                    bound_chat,
                    f"📢 {actor} упомянул участников во всех чатах отдела.\n{mentions}",
                ):
                    failures += 1
                else:
                    sent += 1
            await message.answer(
                f"✅ {actor} упомянул участников во всех чатах отдела. "
                f"Успешно: {sent}, ошибок: {failures}."
            )
            return
        if command == "pin":
            target_message = message.reply_message
            if not target_message or not vk_api:
                await message.answer("Ответьте командой на сообщение, которое нужно закрепить.")
                return
            if not await vk_api.pin_message(chat_id, target_message.conversation_message_id):
                await message.answer("❌ Не удалось закрепить сообщение.")
            else:
                await message.answer("📌 Сообщение закреплено.")
            return
        if command == "unpin":
            target_cmid = None
            if message.reply_message:
                target_cmid = getattr(
                    message.reply_message, "conversation_message_id", None
                )
            elif args and args[0].isdigit():
                target_cmid = int(args[0])
            if not vk_api or not await vk_api.unpin_message(chat_id, target_cmid):
                await message.answer("❌ Не удалось открепить сообщение.")
            else:
                await message.answer("✅ Сообщение откреплено.")
            return
        if command == "antitag":
            current = await chats.get(chat_id)
            settings = current.get("settings") or {}
            restricted = list(settings.get("antitag_users", []))
            target_id, _ = _target_from_args(message, args)
            if args and args[0].lower() in {"off", "выкл"}:
                settings["antitag"] = False
                if not await chats.update_settings(chat_id, {"antitag": False}):
                    raise RuntimeError("Не удалось обновить настройки антитега.")
                await message.answer("✅ Антитег отключён.")
            elif target_id:
                if target_id in restricted:
                    restricted.remove(target_id)
                else:
                    restricted.append(target_id)
                if not await chats.update_settings(
                    chat_id, {"antitag": True, "antitag_users": restricted}
                ):
                    raise RuntimeError("Не удалось обновить настройки антитега.")
                await message.answer(f"✅ Настройки антитега обновлены для ID {target_id}.")
            else:
                enabled = not bool(settings.get("antitag"))
                if not await chats.update_settings(chat_id, {"antitag": enabled}):
                    raise RuntimeError("Не удалось обновить настройки антитега.")
                await message.answer(f"✅ Антитег {'включён' if enabled else 'выключен'}.")
            return
        if command == "chat":
            chat_data = await chats.get(chat_id)
            info = await vk_api.get_chat_info(chat_id) if vk_api else None
            if info:
                if not await chats.update(chat_id, {"title": info["title"]}):
                    raise RuntimeError("Не удалось сохранить название беседы.")
                chat_data["title"] = info["title"]
                await message.answer(
                    f"💬 {info['title']}\n🆔 ID: {chat_id}\n"
                    f"👥 Участников: {info['members_count']}\n"
                    f"⚙️ Бот: {'активен' if chat_data.get('is_active') else 'не активирован'}"
                )
            else:
                await message.answer(f"🆔 ID беседы: {chat_id}\nБот: {'активен' if chat_data.get('is_active') else 'не активирован'}")
            return
        if command == "settings":
            if not args:
                current = await chats.get(chat_id)
                settings = (current or {}).get("settings") or {}
                await message.answer(
                    "⚙️ Настройки беседы:\n"
                    f"• Режим тишины: {'включён' if settings.get('timeout') else 'выключен'}\n"
                    f"• Антитег: {'включён' if settings.get('antitag') else 'выключен'}\n"
                    f"• Официальных ссылок: {len(settings.get('info_links') or [])}"
                )
                return
            key, _, value = " ".join(args).partition(" ")
            if key not in {"antitag", "timeout"} or value.lower() not in {
                "on", "off", "вкл", "выкл", "1", "0"
            }:
                await message.answer("Использование: /settings antitag|timeout on|off")
                return
            enabled = value.lower() in {"on", "вкл", "1"}
            if not await chats.update_settings(chat_id, {key: enabled}):
                raise RuntimeError(f"Не удалось сохранить настройку {key}.")
            await message.answer(f"✅ Настройка {key}: {'включена' if enabled else 'выключена'}.")
            return
        if command == "addmlmoder":
            await _assign_role(message, args, 1, user_id, chat_id)
            return
        if command == "delmlmoder":
            await _assign_role(message, args, 0, user_id, chat_id)
            return
        if command == "addmoder":
            await _assign_role(message, args, 1, user_id, chat_id)
            return
        if command == "delmoder":
            await _assign_role(message, args, 0, user_id, chat_id)
            return
        if command == "addadmin":
            await _assign_role(message, args, 2, user_id, chat_id)
            return
        if command == "deladmin":
            await _assign_role(message, args, 1, user_id, chat_id)
            return
        if command == "addzam":
            await _assign_role(message, args, 3, user_id, chat_id)
            return
        if command == "delzam":
            await _assign_role(message, args, 2, user_id, chat_id)
            return
        if command == "addstmoder":
            await _assign_role(message, args, 3, user_id, chat_id)
            return
        if command == "import":
            group_id = await _bound_group(chat_id)
            if not group_id:
                await message.answer("Сначала привяжите беседу к группе командой /bind.")
                return
            ids = [int(value) for value in re.findall(r"\d+", " ".join(args))]
            if not ids:
                await message.answer("Укажите список ID через пробел: /import 123 456")
                return
            kick_failures = 0
            target_ids = list(dict.fromkeys(ids))[:100]
            bound_chats = await groups.get_bound_chats(group_id)
            for target_id in target_ids:
                if not await global_data.ban(
                    group_id, target_id, "Импортированная блокировка", user_id
                ):
                    raise RuntimeError("Не удалось сохранить одну из импортируемых блокировок.")
                if vk_api:
                    for bound_chat in bound_chats:
                        if not await vk_api.kick_user(bound_chat, target_id):
                            kick_failures += 1
                        await _revoke_role_after_removal(
                            bound_chat,
                            target_id,
                            user_id,
                            "Снята при глобальной блокировке.",
                        )
                else:
                    kick_failures += len(bound_chats)
                    for bound_chat in bound_chats:
                        await _revoke_role_after_removal(
                            bound_chat,
                            target_id,
                            user_id,
                            "Снята при глобальной блокировке.",
                        )
            await message.answer(
                f"✅ Импортировано блокировок: {len(target_ids)}. "
                f"Не удалось исключить участника из бесед: {kick_failures}."
            )
            return
        await message.answer(
            f"Неизвестная команда /{invoked_command}. Список команд: /help"
        )
    except ValueError as exc:
        await message.answer(f"❌ {exc}")
    except Exception:
        logger.exception(
            "Command /%s (canonical /%s) failed for chat %s",
            invoked_command,
            command,
            message.peer_id,
        )
        await message.answer("❌ Не удалось выполнить команду из-за ошибки. Попробуйте позже.")


@bp.on.raw_event("message_event", MessageEvent)
async def help_level_callback(event: MessageEvent):
    payload = event.payload
    if not isinstance(payload, dict):
        return
    if payload.get("cmd") == "revoke_punishment":
        await _handle_punishment_callback(event, payload)
        return
    if payload.get("cmd") == "nlist_page":
        page = payload.get("page")
        if (
            isinstance(page, bool)
            or not isinstance(page, int)
            or page < 0
            or event.peer_id < 2_000_000_000
            or await members.get_role(event.peer_id, event.user_id) < 1
        ):
            await event.show_snackbar("Недостаточно прав или неверная страница списка.")
            return
        try:
            text, keyboard = await _render_nick_list(event.peer_id, page)
            await event.edit_message(message=text, keyboard=keyboard)
            await event.send_empty_answer()
        except Exception:
            logger.exception(
                "Could not update nickname list in chat %s", event.peer_id
            )
            await event.show_snackbar("Не удалось обновить список ников.")
        return
    if payload.get("cmd") != "help_level":
        return

    level = payload.get("level")
    if (
        isinstance(level, bool)
        or not isinstance(level, int)
        or not 0 <= level <= MAX_HELP_ROLE
    ):
        await event.show_snackbar("Не удалось выбрать уровень команд.")
        return
    try:
        user_role = await members.get_role(event.peer_id, event.user_id)
        if event.peer_id < 2_000_000_000 or level > min(user_role, MAX_HELP_ROLE):
            await event.show_snackbar("Этот уровень вам недоступен.")
            return
        await event.edit_message(
            message=format_help_level_text(user_role, level),
            keyboard=get_help_keyboard(user_role, level),
        )
        await event.send_empty_answer()
    except Exception:
        logger.exception(
            "Could not update help message for user %s in chat %s",
            event.user_id,
            event.peer_id,
        )
        await event.show_snackbar("Не удалось обновить список команд.")


async def _handle_punishment_callback(event: MessageEvent, payload: dict) -> None:
    action = payload.get("action")
    target_id = payload.get("target_id")
    punishment_id = payload.get("punishment_id")
    allowed_actions = {"unwarn", "unmute", "unban", "restore_kick"}
    if (
        action not in allowed_actions
        or isinstance(target_id, bool)
        or not isinstance(target_id, int)
        or target_id <= 0
        or isinstance(punishment_id, bool)
        or not isinstance(punishment_id, int)
        or punishment_id <= 0
        or event.peer_id < 2_000_000_000
    ):
        await event.show_snackbar("Некорректная кнопка наказания.")
        return

    try:
        actor_role = await members.get_role(event.peer_id, event.user_id)
        target_role = await members.get_role(event.peer_id, target_id)
        required_action = "kick" if action == "restore_kick" else action
        if actor_role < get_required_role(required_action) or actor_role <= target_role:
            await event.show_snackbar(
                "Недостаточно прав или пользователь имеет равную/старшую роль."
            )
            return

        record = await punishments.get_by_id(event.peer_id, punishment_id)
        if not record or record.get("target_id") != target_id:
            await event.show_snackbar("Это наказание уже снято или недоступно.")
            return

        if action == "unwarn":
            if record.get("type") != "warn":
                await event.show_snackbar("Предупреждение уже недоступно.")
                return
            if not await punishments.delete_warn_by_id(
                event.peer_id, target_id, punishment_id
            ):
                await event.show_snackbar("Это предупреждение уже снято.")
                return
            remaining = await members.remove_warn(event.peer_id, target_id)
            await _add_log(event.peer_id, target_id, event.user_id, "unwarn")
            result = f"Предупреждение снято. Осталось: {remaining}."
        elif action == "unmute":
            if record.get("type") != "mute":
                await event.show_snackbar("Этот мут уже недоступен.")
                return
            latest_mute = await punishments.get_latest_by_type(
                event.peer_id, target_id, "mute"
            )
            if (
                not latest_mute
                or latest_mute.get("id") != punishment_id
                or not await members.is_muted(event.peer_id, target_id)
            ):
                await event.show_snackbar("Этот мут уже снят или заменён новым.")
                return
            if not await members.set_mute(event.peer_id, target_id, False):
                raise RuntimeError("Не удалось снять мут.")
            await _add_log(event.peer_id, target_id, event.user_id, "unmute")
            result = "Мут снят."
        elif action == "unban":
            if record.get("type") != "ban":
                await event.show_snackbar("Эта блокировка уже недоступна.")
                return
            from db.supabase import get_supabase

            sb = get_supabase()
            deleted = (
                sb.table("chat_bans").delete()
                .eq("chat_id", event.peer_id)
                .eq("user_id", target_id)
                .select("user_id")
                .execute()
            )
            if not deleted.data:
                await event.show_snackbar("Блокировка уже снята.")
                return
            if not vk_api or not await vk_api.add_chat_user(event.peer_id, target_id):
                await _add_log(event.peer_id, target_id, event.user_id, "unban")
                await event.show_snackbar(
                    "Блокировка снята, но добавить пользователя обратно не удалось."
                )
                return
            await _add_log(event.peer_id, target_id, event.user_id, "unban")
            result = "Блокировка снята, пользователь добавлен обратно."
        else:
            if record.get("type") not in {"kick", "skick"}:
                await event.show_snackbar("Это исключение уже недоступно.")
                return
            if not vk_api:
                raise RuntimeError("VK API не инициализирован.")
            conversation_members = await vk_api.get_conversation_members(event.peer_id)
            if any(
                (
                    member.get("member_id")
                    if isinstance(member, dict)
                    else getattr(member, "member_id", None)
                )
                == target_id
                for member in conversation_members
            ):
                result = "Пользователь уже находится в беседе."
            elif not await vk_api.add_chat_user(event.peer_id, target_id):
                await event.show_snackbar("Не удалось вернуть пользователя в беседу.")
                return
            else:
                result = "Пользователь возвращён в беседу."

        await event.show_snackbar(result)
    except Exception:
        logger.exception(
            "Could not revoke punishment %s for user %s in chat %s",
            punishment_id,
            target_id,
            event.peer_id,
        )
        await event.show_snackbar("Не удалось снять наказание. Попробуйте позже.")


async def _assign_role(message: Message, args: list[str], role: int, actor_id: int, chat_id: int):
    target_id, _ = _target_from_args(message, args)
    if not target_id:
        await message.answer("Ответьте на сообщение пользователя или укажите его ID.")
        return
    actor_role = await members.get_role(chat_id, actor_id)
    target_role = await members.get_role(chat_id, target_id)
    if target_role == role:
        target = await _named_mention(chat_id, target_id)
        await message.answer(
            f"{target} уже занимает должность "
            f"{get_role_name(role).lower()}."
        )
        return
    if target_id == actor_id or target_role >= actor_role or role >= actor_role:
        await message.answer("⛔ Нельзя изменять роль равного или старшего пользователя.")
        return
    if not await members.set_role(chat_id, target_id, role):
        raise RuntimeError("Не удалось сохранить роль пользователя.")
    await _add_log(
        chat_id,
        target_id,
        actor_id,
        "role_change",
        f"Роль: {get_role_name(target_role)} ({target_role}) → "
        f"{get_role_name(role)} ({role})",
    )
    names = (
        await vk_api.get_member_names(chat_id, [actor_id, target_id])
        if vk_api
        else {}
    )
    actor = format_user_mention(actor_id, names.get(actor_id) or f"ID {actor_id}")
    target = format_user_mention(target_id, names.get(target_id) or f"ID {target_id}")
    if role > target_role:
        action = f"повысил {target} на должность {get_role_name(role).lower()}"
    elif role == 0:
        action = (
            f"снял {target} с должности "
            f"{get_role_name(target_role).lower()}"
        )
    else:
        action = f"понизил {target} до должности {get_role_name(role).lower()}"
    await message.answer(f"✅ {actor} {action}.")


def _duration_match(args: list[str]) -> tuple[Optional[re.Match], int]:
    if not args:
        return None, 0
    token = args[0].lower().rstrip(".")
    match = re.fullmatch(
        r"(\d+)\s*(с|сек(?:унд(?:а|ы)?)?|м|мин(?:ут(?:а|ы)?)?|"
        r"ч|час(?:а|ов)?|д|дн(?:я|ей)?)",
        token,
    )
    consumed = 1
    if not match and len(args) > 1 and args[0].isdigit():
        match = re.fullmatch(
            r"(с|сек(?:унд(?:а|ы)?)?|м|мин(?:ут(?:а|ы)?)?|"
            r"ч|час(?:а|ов)?|д|дн(?:я|ей)?)",
            args[1].lower().rstrip("."),
        )
        if match:
            match = re.match(r"(\d+)(.*)", f"{args[0]}{match.group(1)}")
            consumed = 2
    return match, consumed


def _duration_from_args(args: list[str]) -> tuple[Optional[timedelta], int]:
    match, consumed = _duration_match(args)
    if not match:
        return None, 0
    amount = int(match.group(1))
    if amount <= 0:
        return None, consumed
    unit = match.group(2)[0]
    return timedelta(**{
        {"с": "seconds", "м": "minutes", "ч": "hours", "д": "days"}[unit]: amount
    }), consumed


def _count_word(count: int) -> str:
    return {1: "один", 2: "два", 3: "три"}.get(count, str(count))
