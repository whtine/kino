import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from vkbottle.bot import Blueprint, Message

from bot.utils.formatters import (
    format_duration,
    format_help_text,
    format_punishment,
    format_stats_entry,
    format_user_info,
    format_user_mention,
)
from bot.utils.permissions import get_role_name
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

TARGET_PATTERN = re.compile(r"(?:\[id|@id)(\d+)(?:\||\])?")


def _parts(text: str) -> tuple[str, list[str]]:
    pieces = text.strip().split()
    command = pieces[0].split("@", 1)[0][1:].lower()
    return command, pieces[1:]


def _target_from_args(message: Message, args: list[str]) -> tuple[Optional[int], list[str]]:
    if message.reply_message and message.reply_message.from_id > 0:
        return message.reply_message.from_id, args
    if args:
        match = TARGET_PATTERN.search(args[0])
        token = match.group(1) if match else args[0].lstrip("id@")
        if token.isdigit() and int(token) > 0:
            return int(token), args[1:]
    return None, args


async def _ensure_chat(message: Message) -> tuple[int, int]:
    chat_id = message.peer_id
    if chat_id < 2_000_000_000:
        raise ValueError("Команда доступна только в беседе.")
    await chats.get_or_create(chat_id)
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


async def _add_log(
    chat_id: int,
    target_id: int,
    moderator_id: int,
    kind: str,
    reason: Optional[str] = None,
    duration: Optional[timedelta] = None,
) -> None:
    await punishments.add(chat_id, target_id, moderator_id, kind, reason, duration)


@bp.on.message()
async def command_router(message: Message):
    text = (message.text or "").strip()
    if not text.startswith("/") or not text.split():
        return

    command, args = _parts(text)
    try:
        chat_id, user_id = await _ensure_chat(message)
        if command in {"help", "start"}:
            await message.answer(format_help_text(await members.get_role(chat_id, user_id)))
            return
        if command in {"id", "stats"}:
            target_id, _ = _target_from_args(message, args)
            target_id = target_id or user_id
            member = await members.get_or_create(chat_id, target_id)
            stat = await stats.get_user_stats(chat_id, target_id)
            names = await vk_api.get_member_names(chat_id, [target_id]) if vk_api else {}
            await message.answer(
                format_user_info(target_id, chat_id, member, stat, names.get(target_id))
            )
            return
        if command == "chatid":
            await message.answer(f"🆔 ID беседы: {chat_id}")
            return
        if command == "top":
            rows = await stats.get_top(chat_id, 10)
            names = await vk_api.get_member_names(chat_id, [row["user_id"] for row in rows]) if vk_api else {}
            output = ["🏆 Топ участников по сообщениям:"]
            output.extend(
                format_stats_entry(row, index, format_user_mention(row["user_id"], names.get(row["user_id"])))
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
                if getattr(exc, "code", None) == "23505":
                    await message.answer("Вы уже голосовали за этого пользователя.")
                    return
                raise
            count = sb.table("chat_reputation").select("target_id", count="exact").eq(
                "chat_id", chat_id
            ).eq("target_id", target_id).execute().count
            await message.answer(f"⭐ Репутация {format_user_mention(target_id)}: {count or 0}")
            return
        if command in {"staff", "olist"}:
            staff = await members.get_staff(chat_id)
            if command == "olist" and vk_api:
                present = {profile.id for profile in await vk_api.get_conversation_members(chat_id)}
                staff = [row for row in staff if row["user_id"] in present]
            if not staff:
                await message.answer("👮 Администрация не найдена.")
                return
            lines = ["👮 Состав администрации:"]
            for entry in staff:
                nick = entry.get("nickname") or "пользователь"
                lines.append(
                    f"• [id{entry['user_id']}|{nick}] — "
                    f"{get_role_name(entry['role'])} ({entry['role']})"
                )
            await message.answer("\n".join(lines))
            return
        if command == "check":
            target_id, _ = _target_from_args(message, args)
            if not target_id:
                await message.answer("Ответьте на сообщение или укажите ID пользователя.")
                return
            entry = await members.get_or_create(chat_id, target_id)
            await message.answer(
                f"{format_user_mention(target_id)}\n"
                f"Роль: {get_role_name(entry['role'])} ({entry['role']})\n"
                f"Предупреждения: {entry.get('warns', 0)}"
            )
            return
        if command == "getwarn":
            target_id, _ = _target_from_args(message, args)
            if not target_id:
                target_id = user_id
            entry = await members.get_or_create(chat_id, target_id)
            await message.answer(
                f"⚠️ У {format_user_mention(target_id)} {entry.get('warns', 0)} предупреждений."
            )
            return
        if command == "warn":
            target_id, rest = _target_from_args(message, args)
            if not target_id:
                await message.answer("Использование: /warn [id] причина (или ответьте на сообщение)")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            reason = " ".join(rest) or None
            count = await members.add_warn(chat_id, target_id)
            await _add_log(chat_id, target_id, user_id, "warn", reason)
            await message.answer(f"⚠️ {format_user_mention(target_id)} получил предупреждение ({count}).")
            return
        if command in {"kick", "ban", "skick"}:
            target_id, rest = _target_from_args(message, args)
            if not target_id:
                await message.answer(f"Использование: /{command} [id] причина (или ответьте на сообщение)")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            reason = " ".join(rest) or None
            if command == "ban":
                from db.supabase import get_supabase
                get_supabase().table("chat_bans").upsert({
                    "chat_id": chat_id,
                    "user_id": target_id,
                    "reason": reason,
                    "banned_by": user_id,
                }).execute()
            kicked = bool(vk_api and await vk_api.kick_user(chat_id, target_id))
            if not kicked and command != "ban":
                await message.answer("❌ Не удалось исключить пользователя. Проверьте права бота.")
                return
            await _add_log(chat_id, target_id, user_id, command, reason)
            if command == "ban" and not kicked:
                await message.answer(
                    f"⚠️ {format_user_mention(target_id)} добавлен в список блокировок, "
                    "но исключить не удалось. При следующем входе блокировка сработает."
                )
            else:
                action = "заблокирован и исключён" if command == "ban" else "исключён"
                await message.answer(f"👢 {format_user_mention(target_id)} {action} из беседы.")
            return
        if command == "unban":
            target_id, _ = _target_from_args(message, args)
            if not target_id:
                await message.answer("Укажите ID пользователя.")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            from db.supabase import get_supabase
            removed = get_supabase().table("chat_bans").delete().eq(
                "chat_id", chat_id
            ).eq("user_id", target_id).execute()
            if not removed.data:
                await message.answer("Пользователь не найден в списке блокировок этой беседы.")
                return
            await _add_log(chat_id, target_id, user_id, "unban")
            if not vk_api or not await vk_api.add_chat_user(chat_id, target_id):
                await message.answer("✅ Блокировка снята, но добавить пользователя обратно не удалось.")
                return
            await message.answer(f"✅ Блокировка {format_user_mention(target_id)} снята.")
            return
        if command == "mute":
            target_id, rest = _target_from_args(message, args)
            duration = _parse_duration_arg(rest)
            if not target_id or not duration:
                await message.answer("Использование: /mute [id] время причина (например, /mute 123 30м флуд)")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            reason = " ".join(rest[1:]) or None
            expires = datetime.now(timezone.utc) + duration
            if not await members.set_mute(chat_id, target_id, True, expires.isoformat()):
                raise RuntimeError("Не удалось сохранить статус мута.")
            await _add_log(chat_id, target_id, user_id, "mute", reason, duration)
            await message.answer(
                f"🔇 {format_user_mention(target_id)} ограничен на {format_duration(duration)}."
            )
            return
        if command == "unmute":
            target_id, _ = _target_from_args(message, args)
            if not target_id:
                await message.answer("Укажите ID или ответьте на сообщение пользователя.")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            if not await members.set_mute(chat_id, target_id, False):
                raise RuntimeError("Не удалось снять мут.")
            await _add_log(chat_id, target_id, user_id, "unmute")
            await message.answer(f"🔊 Мут {format_user_mention(target_id)} снят.")
            return
        if command == "unwarn":
            target_id, _ = _target_from_args(message, args)
            if not target_id:
                await message.answer("Укажите ID или ответьте на сообщение пользователя.")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            count = await members.remove_warn(chat_id, target_id)
            await _add_log(chat_id, target_id, user_id, "unwarn")
            await message.answer(f"✅ Предупреждение снято. Осталось: {count}.")
            return
        if command == "clear":
            amount = int(args[0]) if args and args[0].isdigit() else 1
            if not 1 <= amount <= 100:
                await message.answer("Количество сообщений должно быть от 1 до 100.")
                return
            if not vk_api or not await vk_api.clear_recent_messages(chat_id, amount):
                await message.answer("❌ Не удалось удалить сообщения. Проверьте права бота.")
                return
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
            enabled = bool(args and args[0].lower() in {"on", "вкл", "1"})
            if not args or args[0].lower() not in {"on", "off", "вкл", "выкл", "1", "0"}:
                await message.answer("Использование: /timeout on|off")
                return
            if not await chats.update_settings(chat_id, {"timeout": enabled}):
                raise RuntimeError("Не удалось сохранить режим тишины.")
            await message.answer(f"🔕 Режим тишины {'включён' if enabled else 'выключен'}.")
            return
        if command == "zov":
            if not vk_api:
                raise RuntimeError("VK API не инициализирован.")
            text_to_send = await vk_api.mention_all(chat_id, config.max_mentions_per_zov)
            if not text_to_send:
                await message.answer("Не удалось получить список участников.")
            else:
                await message.answer(f"📢 Внимание!\n{text_to_send}")
            return
        if command in {"snick", "rnick"}:
            target_id, rest = _target_from_args(message, args)
            nickname = " ".join(rest).strip() if rest else ""
            if command == "snick" and (not target_id or not nickname):
                await message.answer("Использование: /snick [id] ник (или ответьте на сообщение)")
                return
            target_id = target_id or user_id
            if command == "snick":
                if not await members.set_nickname(chat_id, target_id, nickname[:64]):
                    raise RuntimeError("Не удалось сохранить никнейм.")
                await message.answer(f"🏷 Ник пользователя изменён на «{nickname[:64]}».")
            else:
                if not await members.set_nickname(chat_id, target_id, None):
                    raise RuntimeError("Не удалось удалить никнейм.")
                await message.answer("✅ Никнейм удалён.")
            return
        if command == "getnick":
            target_id, _ = _target_from_args(message, args)
            target_id = target_id or user_id
            nickname = await members.get_nickname(chat_id, target_id)
            await message.answer(f"🏷 Ник: {nickname or 'не установлен'}")
            return
        if command == "nlist":
            entries = await members.get_all_in_chat(chat_id)
            entries = [entry for entry in entries if entry.get("nickname")]
            await message.answer(
                "\n".join(f"• [id{entry['user_id']}|{entry['nickname']}]" for entry in entries)
                if entries else "📋 Никнеймы не установлены."
            )
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
                await message.answer(f"Использование: /{command} [id] ник; нужна привязанная группа.")
                return
            if command == "gsnick":
                if not await global_data.set_nickname(
                    group_id, target_id, " ".join(rest)[:64], user_id
                ):
                    raise RuntimeError("Не удалось сохранить глобальный никнейм.")
                await message.answer("✅ Глобальный ник установлен.")
            else:
                if not await global_data.remove_nickname(group_id, target_id):
                    await message.answer("Глобальный никнейм не найден.")
                    return
                await message.answer("✅ Глобальный ник удалён.")
            return
        if command == "mygroups":
            user_groups = await groups.get_by_owner(user_id)
            await message.answer(
                "\n".join(f"• {item['id']}: {item['name']}" for item in user_groups)
                if user_groups else "У вас пока нет групп."
            )
            return
        if command == "creategroup":
            name = " ".join(args).strip()
            if not name:
                await message.answer("Укажите название: /creategroup название")
                return
            group = await groups.create(name[:100], user_id)
            await message.answer(f"✅ Группа «{group['name']}» создана. ID: {group['id']}")
            return
        if command == "delgroup":
            if not args or not args[0].isdigit():
                await message.answer("Использование: /delgroup ID")
                return
            group_id = int(args[0])
            group = await groups.get(group_id)
            if not group or group["owner_id"] != user_id:
                await message.answer("Группа не найдена или вы не её владелец.")
                return
            if not await groups.delete(group_id):
                raise RuntimeError("Не удалось удалить группу.")
            await message.answer("✅ Группа удалена.")
            return
        if command == "bind":
            if not args or not args[0].isdigit():
                await message.answer("Использование: /bind ID_группы")
                return
            group_id = int(args[0])
            group = await groups.get(group_id)
            if not group or group["owner_id"] != user_id:
                await message.answer("Группа не найдена или вы не её владелец.")
                return
            if not await chats.bind_group(chat_id, group_id):
                raise RuntimeError("Не удалось привязать беседу.")
            await message.answer(f"✅ Беседа привязана к группе «{group['name']}».")
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
            target_id, _ = _target_from_args(message, args)
            group_id = await _bound_group(chat_id)
            if not target_id or not group_id:
                await message.answer("Укажите ID пользователя и привяжите беседу к группе.")
                return
            group = await groups.get(group_id)
            if not group or group["owner_id"] != user_id:
                await message.answer("⛔ Передать владельца может только владелец группы.")
                return
            if not await groups.update(group_id, {"owner_id": target_id}):
                raise RuntimeError("Не удалось передать права владельца.")
            await message.answer(f"✅ Владелец группы передан {format_user_mention(target_id)}.")
            return
        if command == "gban":
            target_id, rest = _target_from_args(message, args)
            group_id = await _bound_group(chat_id)
            if not target_id or not group_id:
                await message.answer("Укажите ID пользователя; беседа должна быть привязана к группе.")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            reason = " ".join(rest) or None
            if not await global_data.ban(group_id, target_id, reason or "", user_id):
                raise RuntimeError("Не удалось сохранить глобальную блокировку.")
            failures = 0
            bound_chats = await groups.get_bound_chats(group_id)
            for bound_chat in bound_chats:
                if vk_api:
                    if not await vk_api.kick_user(bound_chat, target_id):
                        failures += 1
                else:
                    failures += 1
            await _add_log(chat_id, target_id, user_id, "gban", reason)
            status = f" Не удалось исключить из бесед: {failures}." if failures else ""
            await message.answer(
                f"🌐 {format_user_mention(target_id)} заблокирован в группе бесед.{status}"
            )
            return
        if command == "gunban":
            target_id, _ = _target_from_args(message, args)
            group_id = await _bound_group(chat_id)
            if not target_id or not group_id:
                await message.answer("Укажите ID пользователя; беседа должна быть привязана к группе.")
                return
            if not await _can_moderate(message, chat_id, user_id, target_id):
                return
            removed = await global_data.unban(group_id, target_id)
            if removed:
                await _add_log(chat_id, target_id, user_id, "gunban")
                await message.answer("✅ Глобальная блокировка снята.")
            else:
                await message.answer("Пользователь не найден в списке глобальных блокировок.")
            return
        if command == "gzov":
            group_id = await _bound_group(chat_id)
            if not group_id or not vk_api:
                await message.answer("Нужна привязанная группа и доступ к VK API.")
                return
            sent = 0
            failures = 0
            bound_chats = await groups.get_bound_chats(group_id)
            for bound_chat in bound_chats:
                mentions = await vk_api.mention_all(bound_chat, config.max_mentions_per_zov)
                if not mentions:
                    failures += 1
                    continue
                if await vk_api.send_message(bound_chat, f"📢 Внимание!\n{mentions}") is None:
                    failures += 1
                else:
                    sent += 1
            await message.answer(
                f"Зов отправлен в {sent} активных бесед(ы). Ошибок: {failures}."
            )
            return
        if command == "pin":
            target_message = message.reply_message
            if not target_message or not vk_api:
                await message.answer("Ответьте командой на сообщение, которое нужно закрепить.")
                return
            if not await vk_api.pin_message(chat_id, target_message.conversation_message_id):
                await message.answer("❌ Не удалось закрепить сообщение.")
            return
        if command == "unpin":
            if not vk_api or not await vk_api.unpin_message(chat_id):
                await message.answer("❌ Не удалось открепить сообщение.")
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
                await message.answer(f"⚙️ Текущие настройки: {current.get('settings') or {}}")
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
            await _assign_role(message, args, 2, user_id, chat_id)
            return
        if command == "addstmoder":
            await _assign_role(message, args, 3, user_id, chat_id)
            return
        if command == "addadmin":
            await _assign_role(message, args, 5, user_id, chat_id)
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
                else:
                    kick_failures += len(bound_chats)
            await message.answer(
                f"✅ Импортировано блокировок: {len(target_ids)}. "
                f"Не удалось исключить участника из бесед: {kick_failures}."
            )
            return
    except ValueError as exc:
        await message.answer(f"❌ {exc}")
    except Exception:
        logger.exception("Command /%s failed for chat %s", command, message.peer_id)
        await message.answer("❌ Не удалось выполнить команду из-за ошибки. Попробуйте позже.")


async def _assign_role(message: Message, args: list[str], role: int, actor_id: int, chat_id: int):
    target_id, _ = _target_from_args(message, args)
    if not target_id:
        await message.answer("Ответьте на сообщение пользователя или укажите его ID.")
        return
    actor_role = await members.get_role(chat_id, actor_id)
    target_role = await members.get_role(chat_id, target_id)
    if target_id == actor_id or target_role >= actor_role or role >= actor_role:
        await message.answer("⛔ Нельзя изменять роль равного или старшего пользователя.")
        return
    if not await members.set_role(chat_id, target_id, role):
        raise RuntimeError("Не удалось сохранить роль пользователя.")
    await message.answer(
        f"✅ Роль {format_user_mention(target_id)} изменена на "
        f"{get_role_name(role)} ({role})."
    )


def _parse_duration_arg(args: list[str]) -> Optional[timedelta]:
    if not args:
        return None
    match = re.fullmatch(r"(\d+)([смчд])", args[0].lower())
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if amount <= 0:
        return None
    return timedelta(**{
        {"с": "seconds", "м": "minutes", "ч": "hours", "д": "days"}[unit]: amount
    })
