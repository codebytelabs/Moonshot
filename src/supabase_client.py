from supabase import create_client
from loguru import logger

class SupabaseStore:
    def __init__(self, url: str, key: str):
        self.client = create_client(url, key)

    def insert(self, table: str, row: dict):
        try:
            return self.client.table(table).insert(row).execute()
        except Exception as e:
            logger.error(f"Supabase insert failed ({table}): {e}")
            return None
