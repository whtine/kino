# Permission levels mapping
ROLE_NAMES = {
    0: "Пользователь",
    1: "Младший модератор",
    2: "Модератор",
    3: "Старший модератор",
    4: "Администратор",
    5: "Старший администратор",
    6: "Спец. права",
}

# Commands grouped by minimum required role
COMMAND_PERMISSIONS = {
    # Level 0 - Пользователь
    "id": 0,
    "stats": 0,
    "top": 0,
    "chatid": 0,
    "rep": 0,
    "help": 0,
    "start": 0,
    
    # Level 1 - Младший модератор
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
    "gnick": 1,
    "getwarn": 1,
    
    # Level 2 - Модератор
    "unmute": 2,
    "unwarn": 2,
    "mutelist": 2,
    "warnlist": 2,
    "addmlmoder": 2,
    "delmlmoder": 2,
    
    # Level 3 - Старший модератор
    "ban": 3,
    "unban": 3,
    "timeout": 3,
    "zov": 3,
    "addmoder": 3,
    "logs": 3,
    
    # Level 4 - Администратор
    "skick": 4,
    "gban": 4,
    "gunban": 4,
    "gsnick": 4,
    "grnick": 4,
    "gzov": 4,
    "addstmoder": 4,
    
    # Level 5 - Старший администратор
    "chat": 5,
    "antitag": 5,
    "pin": 5,
    "unpin": 5,
    
    # Level 6 - Спец. права
    "mygroups": 6,
    "creategroup": 6,
    "delgroup": 6,
    "async": 6,
    "bind": 6,
    "giveowner": 6,
    "settings": 6,
    "import": 6,
    "bindlist": 6,
    "addadmin": 6,
    "deactivate": 6,
}

COMMAND_DESCRIPTIONS = {
    "id": "Показать профиль, роль и статистику участника.",
    "stats": "Показать профиль, роль и статистику участника.",
    "top": "Показать топ участников по числу сообщений.",
    "chatid": "Показать ID текущей беседы.",
    "rep": "Отдать пользователю один балл репутации.",
    "help": "Показать команды и выбрать уровень доступа.",
    "start": "Показать команды и выбрать уровень доступа.",
    "kick": "Исключить пользователя из беседы.",
    "mute": "Выдать временный мут: укажите время и причину.",
    "warn": "Выдать предупреждение пользователю.",
    "clear": "Удалить последние сообщения (до 100).",
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
    "unwarn": "Снять одно предупреждение пользователя.",
    "mutelist": "Показать пользователей с активным мутом.",
    "warnlist": "Показать активные предупреждения беседы.",
    "addmlmoder": "Назначить младшим модератором (роль 1).",
    "delmlmoder": "Снять роль младшего модератора.",
    "ban": "Заблокировать пользователя в этой беседе.",
    "unban": "Снять локальную блокировку пользователя.",
    "timeout": "Включить или выключить режим тишины беседы.",
    "zov": "Упомянуть участников текущей беседы.",
    "addmoder": "Назначить модератором (роль 2).",
    "logs": "Показать последние действия модераторов.",
    "skick": "Исключить пользователя с проверкой его роли.",
    "gban": "Заблокировать пользователя во всех беседах группы.",
    "gunban": "Снять глобальную блокировку группы.",
    "gsnick": "Установить глобальный ник в группе бесед.",
    "grnick": "Удалить глобальный ник в группе бесед.",
    "gzov": "Упомянуть участников во всех беседах группы.",
    "addstmoder": "Назначить старшим модератором (роль 3).",
    "chat": "Показать сведения о текущей беседе.",
    "antitag": "Настроить запрет упоминаний выбранных пользователей.",
    "pin": "Закрепить сообщение, на которое дан ответ.",
    "unpin": "Открепить сообщение в текущей беседе.",
    "addadmin": "Назначить старшим администратором (роль 5); доступно роли 6.",
    "mygroups": "Показать группы бесед, которыми вы владеете.",
    "creategroup": "Создать группу бесед.",
    "delgroup": "Удалить группу бесед, которой вы владеете.",
    "async": "Изменить режим тишины в активных беседах группы.",
    "bind": "Привязать текущую беседу к вашей группе.",
    "giveowner": "Передать владельца группы другому пользователю.",
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