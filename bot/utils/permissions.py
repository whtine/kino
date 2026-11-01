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
    "addadmin": 5,
    
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
    "deactivate": 6,
    # addadmin for level 6 also exists (give senior admin)
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