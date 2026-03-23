"""Per-chat conversation context with TTL."""

import time
from dataclasses import dataclass, field

from src.config import settings


@dataclass
class Session:
    messages: list[dict] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > settings.session_max_messages:
            self.messages = self.messages[-settings.session_max_messages:]
        self.last_active = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > settings.session_ttl_minutes * 60

    def get_history_text(self) -> str:
        if not self.messages:
            return ""
        return "\n".join(
            f"{'Пользователь' if m['role'] == 'user' else 'Бот'}: {m['content']}"
            for m in self.messages
        )


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[int, Session] = {}

    def get(self, chat_id: int) -> Session:
        session = self._sessions.get(chat_id)
        if session is None or session.is_expired():
            session = Session()
            self._sessions[chat_id] = session
        return session

    def reset(self, chat_id: int) -> None:
        self._sessions.pop(chat_id, None)


session_manager = SessionManager()
