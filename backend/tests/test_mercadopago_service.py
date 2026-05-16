"""Testa MercadoPagoService: erro real do MP é exposto (não vira KeyError 'id')
e auto_return só vai quando a success URL é HTTPS pública.

Cobre os itens 2 e 3 achados no smoke test:
2. auto_return inválido com back_url localhost -> MP 400
3. erro do MP era engolido e virava `'id'` (KeyError)

O SDK do Mercado Pago é mockado (fronteira externa) via _get_sdk.
"""
import pytest

from services.mercadopago import MercadoPagoService


class _FakeEndpoint:
    def __init__(self, result, captured, key):
        self._result = result
        self._captured = captured
        self._key = key

    def create(self, data):
        self._captured["preference_data"] = data
        return self._result

    def get(self, payment_id):
        self._captured["payment_id"] = payment_id
        return self._result


class _FakeSDK:
    def __init__(self, pref_result=None, pay_result=None):
        self.captured = {}
        self._pref = _FakeEndpoint(pref_result, self.captured, "pref")
        self._pay = _FakeEndpoint(pay_result, self.captured, "pay")

    def preference(self):
        return self._pref

    def payment(self):
        return self._pay


def _service_with(monkeypatch, fake_sdk) -> MercadoPagoService:
    svc = MercadoPagoService()
    monkeypatch.setattr(svc, "_get_sdk", lambda: fake_sdk)
    return svc


# ---- Item 3: erro real do MP exposto ----

@pytest.mark.asyncio
async def test_criar_preferencia_raises_clear_error_on_mp_400(monkeypatch):
    fake = _FakeSDK(pref_result={
        "status": 400,
        "response": {
            "message": "auto_return invalid. back_url.success must be defined",
            "error": "invalid_auto_return",
        },
    })
    svc = _service_with(monkeypatch, fake)

    with pytest.raises(RuntimeError) as exc:
        await svc.criar_preferencia("ord-1", 3737, "desc", "a@b.com")

    msg = str(exc.value)
    assert "auto_return invalid" in msg
    assert "400" in msg


@pytest.mark.asyncio
async def test_verificar_pagamento_raises_clear_error_on_mp_error(monkeypatch):
    fake = _FakeSDK(pay_result={
        "status": 404,
        "response": {"message": "Payment not found", "error": "not_found"},
    })
    svc = _service_with(monkeypatch, fake)

    with pytest.raises(RuntimeError) as exc:
        await svc.verificar_pagamento("pay-inexistente")

    assert "Payment not found" in str(exc.value)


@pytest.mark.asyncio
async def test_criar_preferencia_returns_ids_on_success(monkeypatch):
    fake = _FakeSDK(pref_result={
        "status": 201,
        "response": {"id": "pref-123", "init_point": "https://mp/checkout/pref-123"},
    })
    svc = _service_with(monkeypatch, fake)

    out = await svc.criar_preferencia("ord-1", 3737, "desc", "a@b.com")

    assert out == {
        "preference_id": "pref-123",
        "init_point": "https://mp/checkout/pref-123",
    }


# ---- Item 2: auto_return condicional ----

@pytest.mark.asyncio
async def test_criar_preferencia_omits_auto_return_for_localhost(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    fake = _FakeSDK(pref_result={
        "status": 201,
        "response": {"id": "p", "init_point": "x"},
    })
    svc = _service_with(monkeypatch, fake)

    await svc.criar_preferencia("ord-1", 3737, "desc", "a@b.com")

    sent = fake.captured["preference_data"]
    assert "auto_return" not in sent
    assert sent["back_urls"]["success"].startswith("http://localhost:3000")


@pytest.mark.asyncio
async def test_criar_preferencia_includes_auto_return_for_https(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://forja3d.com.br")
    fake = _FakeSDK(pref_result={
        "status": 201,
        "response": {"id": "p", "init_point": "x"},
    })
    svc = _service_with(monkeypatch, fake)

    await svc.criar_preferencia("ord-1", 3737, "desc", "a@b.com")

    sent = fake.captured["preference_data"]
    assert sent["auto_return"] == "approved"
    assert sent["back_urls"]["success"] == "https://forja3d.com.br/pedido/ord-1"


@pytest.mark.asyncio
async def test_criar_preferencia_omits_empty_notification_url(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://forja3d.com.br")
    monkeypatch.delenv("MP_WEBHOOK_URL", raising=False)
    fake = _FakeSDK(pref_result={
        "status": 201,
        "response": {"id": "p", "init_point": "x"},
    })
    svc = _service_with(monkeypatch, fake)

    await svc.criar_preferencia("ord-1", 3737, "desc", "a@b.com")

    sent = fake.captured["preference_data"]
    # MP rejeita notification_url vazia: a chave deve ser omitida quando não há webhook
    assert "notification_url" not in sent
