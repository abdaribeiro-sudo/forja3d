"""Testa o helper de variáveis de ambiente obrigatórias.

Garante que a aplicação se recusa a subir com senha default fraca:
se ADMIN_PASSWORD / AGENT_PASSWORD não estiverem definidas, deve falhar
explicitamente em vez de cair num valor público conhecido.
"""
import pytest

from config import require_password


def test_require_password_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("SOME_SECRET", "s3nh4-forte")
    assert require_password("SOME_SECRET") == "s3nh4-forte"


def test_require_password_raises_when_missing(monkeypatch):
    monkeypatch.delenv("SOME_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="SOME_SECRET"):
        require_password("SOME_SECRET")


def test_require_password_raises_when_blank(monkeypatch):
    monkeypatch.setenv("SOME_SECRET", "   ")
    with pytest.raises(RuntimeError, match="SOME_SECRET"):
        require_password("SOME_SECRET")
