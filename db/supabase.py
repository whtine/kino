from supabase import create_client, Client
from config import config
import logging

logger = logging.getLogger(__name__)

# Global Supabase client
_supabase: Client | None = None


def get_supabase() -> Client:
    """Get or create Supabase client singleton."""
    global _supabase
    if _supabase is None:
        _supabase = create_client(config.supabase_url, config.supabase_key)
        logger.info("Supabase client initialized")
    return _supabase


async def close_supabase():
    """Close Supabase client (if needed)."""
    global _supabase
    if _supabase:
        # Supabase Python client doesn't have explicit close, but we can clear reference
        _supabase = None
        logger.info("Supabase client cleared")