from supabase import create_client, Client
import os

_client = None

def get_supabase_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_KEY')
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment.")
        _client = create_client(url, key)
    return _client
