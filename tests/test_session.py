"""Tests for session management."""

import time

from src.services.session import Session, SessionManager


def test_session_stores_messages():
    s = Session()
    s.add_message("user", "привет")
    s.add_message("assistant", "здравствуйте")
    assert len(s.messages) == 2
    assert s.messages[0]["role"] == "user"
    assert s.messages[1]["content"] == "здравствуйте"


def test_session_trims_to_max(monkeypatch):
    monkeypatch.setattr("src.services.session.settings.session_max_messages", 3)
    s = Session()
    for i in range(5):
        s.add_message("user", f"msg {i}")
    assert len(s.messages) == 3
    assert s.messages[0]["content"] == "msg 2"


def test_session_expiry(monkeypatch):
    monkeypatch.setattr("src.services.session.settings.session_ttl_minutes", 0)
    s = Session()
    s.last_active = time.time() - 1
    assert s.is_expired()


def test_session_not_expired():
    s = Session()
    assert not s.is_expired()


def test_session_history_text():
    s = Session()
    s.add_message("user", "курица")
    s.add_message("assistant", "вот рецепт")
    text = s.get_history_text()
    assert "Пользователь: курица" in text
    assert "Бот: вот рецепт" in text


def test_session_manager_creates_new():
    mgr = SessionManager()
    s = mgr.get(123)
    assert isinstance(s, Session)
    assert len(s.messages) == 0


def test_session_manager_reuses():
    mgr = SessionManager()
    s1 = mgr.get(123)
    s1.add_message("user", "test")
    s2 = mgr.get(123)
    assert len(s2.messages) == 1


def test_session_manager_reset():
    mgr = SessionManager()
    s = mgr.get(123)
    s.add_message("user", "test")
    mgr.reset(123)
    s2 = mgr.get(123)
    assert len(s2.messages) == 0
