import pytest

from tests.test_printer_claim import _make_order


@pytest.mark.asyncio
async def test_progress_updates_fields(client, db_session):
    o = _make_order(status="IMPRIMINDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/progress",
        json={
            "agent_password": "test_agent",
            "percentual": 42,
            "camada_atual": 85,
            "camada_total": 200,
        },
    )
    assert resp.status_code == 200
    await db_session.refresh(o)
    assert o.progresso_percentual == 42
    assert o.camada_atual == 85
    assert o.camada_total == 200


@pytest.mark.asyncio
async def test_progress_accepts_multiple_updates(client, db_session):
    o = _make_order(status="IMPRIMINDO")
    db_session.add(o)
    await db_session.commit()

    for pct, lyr in [(10, 20), (50, 100), (90, 180)]:
        resp = await client.post(
            f"/api/printer/orders/{o.id}/progress",
            json={
                "agent_password": "test_agent",
                "percentual": pct,
                "camada_atual": lyr,
                "camada_total": 200,
            },
        )
        assert resp.status_code == 200

    await db_session.refresh(o)
    assert o.progresso_percentual == 90
