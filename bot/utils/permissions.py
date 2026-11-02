# Permission levels mapping
ROLE_NAMES = {
    0: "Участник",
    1: "Модератор фильмов",
    2: "Администратор",
    3: "Зам. главы отдела кинопоказов",
    4: "Глава отдела кинопоказов",
    5: "Старший администратор",
    6: "Спец. права",
}

# Commands grouped by minimum required role
COMMAND_PERMISSIONS = {
    # Level 0 - Пользователь
    "id": 0,
    "stats": 0,
    "top": 0,
    "info": 0,
    "rep": 0,
    "help": 0,
    
    # Level 1 - Модератор фильмов
    "kick": 1,
    "mute": 1,
    "warn": 1,
    "unwarn": 1,
    "clear": 1,
    "staff": 1,
    "getnick": 1,
    "snick": 1,
    "rnick": 1,
    "getwarn": 1,
    
    # Level 2 - Администратор
    "unmute": 2,
    "mutelist": 2,
    "warnlist": 2,
    "addmoder": 2,
    "delmoder": 2,
    "ban": 2,
    "getban": 2,
    "unban": 2,
    "timeout": 2,
    
    # Level 3 - Заместитель главы отдела
    "zov": 3,
    "addadmin": 3,
    "deladmin": 3,
    "sban": 3,
    "sunban": 3,
    "ssnick": 3,
    "srnick": 3,
    "szov": 3,
    "skick": 3,
    "pin": 3,
    "unpin": 3,
    
    # Level 4 - Глава отдела кинопоказов
    "addzam": 4,
    "delzam": 4,
    "otdel": 4,
    "delotdel": 4,
    "myotdel": 4,
    "mygroups": 4,
    "creategroup": 4,
    "delgroup": 4,
    "bind": 4,
    "unbind": 4,
    "bindlist": 4,
    "giveowner": 4,
    "settings": 4,
    # Legacy commands stay restricted to special rights and are omitted from /help.
    "del": 6,
    "olist": 6,
    "nlist": 6,
    "check": 6,
    "gnick": 6,
    "addmlmoder": 6,
    "delmlmoder": 6,
    "logs": 6,
    "gban": 6,
    "gunban": 6,
    "gsnick": 6,
    "grnick": 6,
    "gzov": 6,
    "addstmoder": 6,
    "chat": 6,
    "antitag": 6,
    "async": 6,
    "import": 6,
    "deactivate": 6,
}

# /help lists only the new commands introduced at each staff level.
HELP_COMMANDS_BY_ROLE = {
    0: ("help", "id", "info", "rep", "stats", "top"),
    1: (
        "clear", "getnick", "getwarn", "kick", "mute", "rnick",
        "snick", "staff", "warn", "unwarn",
    ),
    2: (
        "addmoder", "delmoder", "mutelist", "warnlist", "ban", "getban",
        "unban", "timeout",
    ),
    3: (
        "addadmin", "deladmin", "sban", "srnick", "ssnick", "sunban",
        "szov", "zov", "skick", "pin", "unpin",
    ),
    4: (
        "addzam", "delzam", "otdel", "bind", "unbind", "bindlist",
        "delotdel", "giveowner", "myotdel", "settings",
    ),
}
MAX_HELP_ROLE = max(HELP_COMMANDS_BY_ROLE)

COMMAND_DESCRIPTIONS = {
    "id": "Показать профиль, роль и статистику участника.",
    "stats": "Показать роль, статистику и дату назначения должности участника.",
    "top": "Показать топ участников по числу сообщений.",
    "chatid": "Показать ID текущей беседы.",
    "info": "Показать официальные ссылки беседы; настройка доступна с роли 5.",
    "rep": "Отдать пользователю один балл репутации.",
    "help": "Показать команды и выбрать уровень доступа.",
    "start": "Показать команды и выбрать уровень доступа.",
    "kick": "Исключить пользователя из беседы.",
    "mute": "Выдать мут на 15–450 минут: /mute @username 30 минут причина.",
    "warn": "Выдать предупреждение пользователю.",
    "clear": "Удалить сообщение.",
    "del": "Удалить сообщение, на которое вы ответили, если автор не выше вас по роли.",
    "staff": "Показать список модераторов беседы.",
    "olist": "Показать модераторов, которые сейчас в беседе.",
    "getnick": "Показать локальный ник пользователя.",
    "snick": "Установить локальный ник пользователя.",
    "rnick": "Удалить локальный ник пользователя.",
    "nlist": "Показать пользователей с локальными никами.",
    "check": "Проверить роль и предупреждения пользователя.",
    "gnick": "Показать глобальный ник в привязанной группе.",
    "getwarn": "Показать число предупреждений пользователя.",
    "unmute": "Снять мут с пользователя.",
    "unwarn": "Снять предупреждение пользователю.",
    "mutelist": "Показать пользователей с активным мутом.",
    "warnlist": "Показать активные предупреждения беседы.",
    "addmoder": "Назначить модератором фильмов.",
    "delmoder": "Снять с должности модератора фильмов.",
    "addmlmoder": "Назначить модератором фильмов (устаревшая команда).",
    "delmlmoder": "Снять с должности модератора фильмов (устаревшая команда).",
    "ban": "Заблокировать пользователя в этой беседе.",
    "getban": "Показать активные блокировки беседы и синхронизированной группы.",
    "unban": "Разблокировать пользователя в этой беседе.",
    "timeout": "Включить или выключить режим тишины беседы.",
    "zov": "Упомянуть участников текущей беседы.",
    "addadmin": "Назначить пользователю роль администратора (уровень 2) в беседе.",
    "deladmin": "Понизить администратора беседы до модератора фильмов (уровень 1).",
    "logs": "Показать последние действия модераторов.",
    "skick": "Исключить пользователя из всех бесед отдела.",
    "gban": "Заблокировать пользователя во всех беседах группы.",
    "gunban": "Снять глобальную блокировку группы.",
    "gsnick": "Установить глобальный ник в группе бесед.",
    "grnick": "Удалить глобальный ник в группе бесед.",
    "gzov": "Упомянуть участников во всех беседах группы.",
    "addstmoder": "Назначить старшим модератором (устаревшая команда).",
    "chat": "Показать сведения о текущей беседе.",
    "antitag": "Настроить запрет упоминаний выбранных пользователей.",
    "pin": "Закрепить сообщение, на которое дан ответ.",
    "unpin": "Открепить сообщение в текущей беседе.",
    "addzam": "Назначить заместителем главы отдела кинопоказов (уровень 3).",
    "delzam": "Понизить заместителя главы отдела до администратора (уровень 2).",
    "otdel": "Создать отдел бесед.",
    "delotdel": "Удалить принадлежащий вам отдел бесед.",
    "myotdel": "Показать ваши отделы бесед.",
    "sban": "Заблокировать пользователя во всех беседах отдела.",
    "sunban": "Снять глобальную блокировку во всех беседах отдела.",
    "ssnick": "Установить глобальный ник во всех беседах отдела.",
    "srnick": "Удалить глобальный ник во всех беседах отдела.",
    "szov": "Упомянуть участников во всех беседах отдела.",
    "mygroups": "Показать группы бесед, которыми вы владеете.",
    "creategroup": "Создать группу бесед.",
    "delgroup": "Удалить группу бесед, которой вы владеете.",
    "async": "Изменить режим тишины в активных беседах группы.",
    "bind": "Подключить беседу к группе и включить групповые команды синхронизации.",
    "giveowner": "Передать владельца группы другому пользователю.",
    "unbind": "Отвязать беседу от группы общей синхронизации.",
    "settings": "Посмотреть или изменить настройки беседы.",
    "import": "Импортировать список ID в глобальные блокировки.",
    "bindlist": "Показать беседы, привязанные к группе.",
    "deactivate": "Деактивировать бота в текущей беседе.",
}


def get_role_name(role: int) -> str:
    """Get role display name."""
    return ROLE_NAMES.get(role, f"Уровень {role}")


def get_required_role(command: str) -> int:
    """Get minimum role required for command."""
    return COMMAND_PERMISSIONS.get(command.lower(), 6)


def has_permission(user_role: int, required_role: int) -> bool:
    """Check if user role meets required role."""
    return user_role >= required_role


def check_permission(user_role: int, command: str) -> bool:
    """Check if user has permission for command."""
    required = get_required_role(command)
    return has_permission(user_role, required)


def get_commands_for_role(role: int) -> list[str]:
    """Get all commands available for a given role."""
    return [cmd for cmd, req in COMMAND_PERMISSIONS.items() if req <= role]