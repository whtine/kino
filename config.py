import os
from dataclasses import dataclass


@dataclass
class Config:
    # VK
    vk_token: str
    group_id: int  # ID группы (без минуса), для Long Poll

    # Supabase
    supabase_url: str
    supabase_key: str  # server-side secret/service_role key

    # Bot settings
    activation_command: str = "/activate"
    max_mentions_per_zov: int = 100  # лимит упоминаний за один зов

    # Render web server
    port: int = 8000
    health_ping_url: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        vk_token = os.getenv("VK_TOKEN")
        if not vk_token:
            raise ValueError("VK_TOKEN environment variable is required")

        supabase_url = os.getenv("SUPABASE_URL")
        if not supabase_url:
            raise ValueError("SUPABASE_URL environment variable is required")

        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_key:
            raise ValueError("SUPABASE_KEY environment variable is required")
        if supabase_key.startswith("sb_publishable_"):
            raise ValueError(
                "SUPABASE_KEY must be a server-side secret/service_role key, "
                "not a publishable key"
            )

        group_id_str = os.getenv("GROUP_ID")
        if not group_id_str:
            raise ValueError("GROUP_ID environment variable is required")
        group_id = int(group_id_str)
        if group_id <= 0:
            raise ValueError("GROUP_ID must be a positive VK community ID")

        max_mentions = int(os.getenv("MAX_MENTIONS_PER_ZOV", "100"))
        if max_mentions < 1:
            raise ValueError("MAX_MENTIONS_PER_ZOV must be at least 1")

        port = int(os.getenv("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be between 1 and 65535")

        return cls(
            vk_token=vk_token,
            group_id=group_id,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            activation_command=os.getenv("ACTIVATION_COMMAND", "/activate"),
            max_mentions_per_zov=max_mentions,
            port=port,
            health_ping_url=(
                os.getenv("HEALTH_PING_URL") or os.getenv("RENDER_EXTERNAL_URL")
            ),
        )


config = Config.from_env()