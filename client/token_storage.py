import json
import os
from typing import Optional, Dict

class TokenStorage:
    def __init__(self, storage_file: str = "user_tokens.json"):
        self.storage_file = storage_file
        self.tokens: Dict[str, dict] = self._load_tokens()

    def _load_tokens(self) -> Dict[str, dict]:
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_tokens(self):
        with open(self.storage_file, 'w') as f:
            json.dump(self.tokens, f)

    def store_tokens(self, email: str, access_token: str, refresh_token: str):
        self.tokens[email] = {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
        self._save_tokens()

    def get_tokens(self, email: str) -> Optional[dict]:
        return self.tokens.get(email)

    def clear_tokens(self, email: str):
        if email in self.tokens:
            del self.tokens[email]
            self._save_tokens()

    def clear_all(self):
        self.tokens = {}
        if os.path.exists(self.storage_file):
            os.remove(self.storage_file)

    def get_all_tokens(self) -> Dict[str, dict]:
        """Возвращает все сохраненные токены."""
        return self.tokens.copy()  # Возвращаем копию для безопасности 