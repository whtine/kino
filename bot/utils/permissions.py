# Permission levels mapping
ROLE_NAMES = {
    0: "Участник",
    1: "Модератор фильмов",
    2: "Администратор",
    3: "Зам. главы отдела кинопоказов",
    4: "Глава отдела кинопоказов",
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
    "chatid": 0,
    "chat": 0,
    
    # Level 1 - Модератор фильмов
    "kick": 1,
    "mute": 1,
    "warn": 1,
    "clear": 1,
    "del": 1,
    "staff": 1,
    "olist": 1,
    "getnick": 1,
    "snick": 1,
    "rnick": 1,
    "nlist": 1,
    "check": 1,
    "getwarn": 1,
    "unwarn": 1,
    
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
    "logs": 2,
    "antitag": 2,
    "addmlmoder": 2,
    "delmlmoder": 2,
    
    # Level 3 - Заместитель главы отдела
    "zov": 3,
    "addadmin": 3,
    "deladmin": 3,
    "gnick": 3,
    "sban": 3,
    "gban": 3,
    "sunban": 3,
    "gunban": 3,
    "ssnick": 3,
    "gsnick": 3,
    "srnick": 3,
    "grnick": 3,
    "szov": 3,
    "gzov": 3,
    "skick": 3,
    "pin": 3,
    "unpin": 3,
    "async": 3,
    "import": 3,
    
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
    "addstmoder": 4,
    "deactivate": 4,
}

# /help lists the commands introduced at each level of the current hierarchy.
HELP_COMMANDS_BY_ROLE = {
    0: ("help", "id", "info", "rep", "stats", "top", "chat", "chatid"),
    1: (
        "clear", "del", "getnick", "getwarn", "kick", "mute", "nlist",
        "olist", "rnick", "snick", "staff", "unwarn", "warn", "check",
    ),
    2: (
        "addmoder", "antitag", "ban", "delmoder", "getban", "logs",
        "mutelist", "timeout", "unban", "unmute", "warnlist",
    ),
    3: (
        "addadmin", "async", "deladmin", "gnick", "pin", "sban",
        "import", "skick", "srnick", "ssnick", "sunban", "szov",
        "unpin", "zov",
    ),
    4: (
        "addzam", "bind", "bindlist", "deactivate", "delgroup",
        "delotdel", "delzam", "giveowner", "mygroups", "myotdel",
        "otdel", "settings", "unbind",
    ),
}
MAX_HELP_ROLE = max(HELP_COMMANDS_BY_ROLE)

COMMAND_DESCRIPTIONS = {
    "id": "Показать профиль, роль и статистику участника.",
    "stats": "Показать роль, статистику и дату назначения должности участника.",
    "top": "Показать топ участников по числу сообщений.",
    "chatid": "Показать ID текущей беседы.",
    "info": "Показать официальные ссылки беседы; настройка доступна с роли 4.",
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
    "chat": "Показать сведения о текущей беседе.",
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
    "addstmoder": "Устаревший псевдоним команды /addzam.",
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