import pytest

from models.tables import Order
from tests.test_printer_claim import _make_order


@pytest.mark.asyncio
async def test_status_preparando_to_imprimindo(client, db_session):
    o = _make_order(status="PREPARANDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/status",
        json={"agent_password": "test_agent", "status": "IMPRIMINDO"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "IMPRIMINDO"

    await db_session.refresh(o)
    assert o.status == "IMPRIMINDO"


@pytest.mark.asyncio
async def test_status_imprimindo_to_impresso_sets_concluded_at(client, db_session):
    o = _make_order(status="IMPRIMINDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/status",
        json={"agent_password": "test_agent", "status": "IMPRESSO"},
    )
    assert resp.status_code == 200

    await db_session.refresh(o)
    assert o.status == "IMPRESSO"
    assert o.impressao_concluida_em is not None


@pytest.mark.asyncio
async def test_status_rejects_illegal_transition(client, db_session):
    o = _make_order(status="PAGO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/status",
        json={"agent_password": "test_agent", "status": "IMPRIMINDO"},
    )
    assert resp.status_code == 400
    assert "ilegal" in resp.json()["detail"].lower() or "illegal" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_status_returns_404_for_missing_order(client):
    resp = await client.post(
        "/api/printer/orders/nope/status",
        json={"agent_password": "test_agent", "status": "IMPRIMINDO"},
    )
    assert resp.status_code == 404
