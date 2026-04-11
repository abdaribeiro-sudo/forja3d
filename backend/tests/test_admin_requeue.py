from datetime import datetime

import pytest

from tests.test_printer_claim import _make_order


@pytest.mark.asyncio
async def test_requeue_erro_back_to_pago(client, db_session):
    o = _make_order(
        status="ERRO_IMPRESSAO",
        erro_mensagem="deu ruim",
        erro_em=datetime.utcnow(),
        progresso_percentual=50,
    )
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/admin/orders/{o.id}/requeue",
        json={"password": "test_admin"},
    )
    assert resp.status_code == 200
    await db_session.refresh(o)
    assert o.status == "PAGO"
    assert o.erro_mensagem is None
    assert o.erro_em is None
    assert o.progresso_percentual is None


@pytest.mark.asyncio
async def test_requeue_non_erro_is_rejected(client, db_session):
    o = _make_order(status="IMPRIMINDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/admin/orders/{o.id}/requeue",
        json={"password": "test_admin"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_requeue_rejects_wrong_password(client, db_session):
    o = _make_order(status="ERRO_IMPRESSAO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/admin/orders/{o.id}/requeue",
        json={"password": "wrong"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is False
