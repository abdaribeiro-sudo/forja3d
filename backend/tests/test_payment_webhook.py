"""Testes do webhook do Mercado Pago (POST /api/payment/webhook).

É o ponto onde dinheiro encontra o sistema, então cobrimos:
- notificação que não é de pagamento (ignorada)
- payment_id ausente
- pagamento aprovado -> pedido vira PAGO + email disparado
- idempotência: notificação duplicada não reprocessa pedido já PAGO
- pagamento não aprovado -> pedido continua AGUARDANDO_PAGAMENTO
- external_reference apontando pra pedido inexistente (não quebra)

A API do Mercado Pago (mp_service.verificar_pagamento) é a única fronteira
externa mockada — é serviço pago/remoto, mock inevitável. O resto roda real
contra o banco de teste.
"""
import pytest

from services.mercadopago import mp_service
from services.notifier import notifier
from tests.test_printer_claim import _make_order


def _fake_verificar(status: str, external_reference):
    """Devolve um substituto async de mp_service.verificar_pagamento."""
    async def _inner(payment_id: str) -> dict:
        return {
            "payment_id": str(payment_id),
            "status": status,
            "external_reference": external_reference,
        }
    return _inner


def _recording_notifier():
    """Substituto async de notifier.send_payment_received que registra chamadas."""
    chamadas = []

    async def _inner(order) -> None:
        chamadas.append(order.id)

    return chamadas, _inner


@pytest.mark.asyncio
async def test_webhook_ignores_non_payment_notification(client, db_session):
    o = _make_order(status="AGUARDANDO_PAGAMENTO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        "/api/payment/webhook",
        json={"type": "plan", "data": {"id": "123"}},
    )

    assert resp.status_code == 200
    assert resp.json() == {"success": True, "data": {"received": True}, "error": None}
    await db_session.refresh(o)
    assert o.status == "AGUARDANDO_PAGAMENTO"


@pytest.mark.asyncio
async def test_webhook_missing_payment_id_returns_error(client):
    resp = await client.post(
        "/api/payment/webhook",
        json={"type": "payment", "data": {}},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"] == "Payment ID não encontrado."


@pytest.mark.asyncio
async def test_webhook_approved_marks_order_pago_and_notifies(
    client, db_session, monkeypatch
):
    o = _make_order(status="AGUARDANDO_PAGAMENTO")
    db_session.add(o)
    await db_session.commit()

    chamadas, recorder = _recording_notifier()
    monkeypatch.setattr(mp_service, "verificar_pagamento", _fake_verificar("approved", o.id))
    monkeypatch.setattr(notifier, "send_payment_received", recorder)

    resp = await client.post(
        "/api/payment/webhook",
        json={"type": "payment", "data": {"id": "MP-999"}},
    )

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    await db_session.refresh(o)
    assert o.status == "PAGO"
    assert o.mp_payment_id == "MP-999"
    assert chamadas == [o.id]


@pytest.mark.asyncio
async def test_webhook_idempotent_when_order_already_pago(
    client, db_session, monkeypatch
):
    o = _make_order(status="PAGO", mp_payment_id="MP-ORIGINAL")
    db_session.add(o)
    await db_session.commit()

    chamadas, recorder = _recording_notifier()
    monkeypatch.setattr(mp_service, "verificar_pagamento", _fake_verificar("approved", o.id))
    monkeypatch.setattr(notifier, "send_payment_received", recorder)

    resp = await client.post(
        "/api/payment/webhook",
        json={"type": "payment", "data": {"id": "MP-DUPLICADO"}},
    )

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    await db_session.refresh(o)
    assert o.status == "PAGO"
    assert o.mp_payment_id == "MP-ORIGINAL"  # não sobrescreve
    assert chamadas == []  # não reenvia email


@pytest.mark.asyncio
async def test_webhook_not_approved_keeps_order_awaiting(
    client, db_session, monkeypatch
):
    o = _make_order(status="AGUARDANDO_PAGAMENTO")
    db_session.add(o)
    await db_session.commit()

    chamadas, recorder = _recording_notifier()
    monkeypatch.setattr(mp_service, "verificar_pagamento", _fake_verificar("pending", o.id))
    monkeypatch.setattr(notifier, "send_payment_received", recorder)

    resp = await client.post(
        "/api/payment/webhook",
        json={"type": "payment", "data": {"id": "MP-PEND"}},
    )

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    await db_session.refresh(o)
    assert o.status == "AGUARDANDO_PAGAMENTO"
    assert chamadas == []


@pytest.mark.asyncio
async def test_webhook_unknown_order_reference_does_not_crash(
    client, monkeypatch
):
    monkeypatch.setattr(
        mp_service,
        "verificar_pagamento",
        _fake_verificar("approved", "pedido-que-nao-existe"),
    )

    resp = await client.post(
        "/api/payment/webhook",
        json={"type": "payment", "data": {"id": "MP-ORFAO"}},
    )

    assert resp.status_code == 200
    assert resp.json() == {"success": True, "data": {"received": True}, "error": None}
