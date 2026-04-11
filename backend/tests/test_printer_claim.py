from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from models.tables import Order


def _make_order(**overrides) -> Order:
    base = dict(
        nome="Teste",
        email="t@t.com",
        status="PAGO",
        modelo_url="/uploads/fake.glb",
        material="PLA",
        escala=1.0,
        peso_gramas=50.0,
        volume_cm3=30.0,
        tempo_impressao_horas=2.0,
        preco_centavos=5000,
        frete_centavos=2000,
        cep_destino="28035030",
        prazo_dias=5,
    )
    base.update(overrides)
    return Order(**base)


@pytest.mark.asyncio
async def test_claim_returns_null_when_no_pago_orders(client, db_session):
    resp = await client.post("/api/printer/claim", json={"agent_password": "test_agent"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] is None


@pytest.mark.asyncio
async def test_claim_picks_oldest_pago_and_marks_preparando(client, db_session):
    old = _make_order()
    new = _make_order()
    db_session.add_all([old, new])
    await db_session.commit()

    resp = await client.post("/api/printer/claim", json={"agent_password": "test_agent"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] is not None
    assert body["data"]["id"] == old.id
    assert body["data"]["status"] == "PREPARANDO"

    await db_session.refresh(old)
    assert old.status == "PREPARANDO"
    assert old.impressao_iniciada_em is not None


@pytest.mark.asyncio
async def test_claim_rejects_wrong_password(client):
    resp = await client.post("/api/printer/claim", json={"agent_password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_claim_cleans_orphan_preparando_older_than_threshold(client, db_session):
    orphan = _make_order(
        status="PREPARANDO",
        impressao_iniciada_em=datetime.utcnow() - timedelta(minutes=60),
    )
    fresh_pago = _make_order()
    db_session.add_all([orphan, fresh_pago])
    await db_session.commit()

    resp = await client.post("/api/printer/claim", json={"agent_password": "test_agent"})
    body = resp.json()
    # cleanup happened, then fresh_pago was claimed
    assert body["data"]["id"] == fresh_pago.id

    await db_session.refresh(orphan)
    assert orphan.status == "ERRO_IMPRESSAO"
    assert "abandonada" in (orphan.erro_mensagem or "").lower()
