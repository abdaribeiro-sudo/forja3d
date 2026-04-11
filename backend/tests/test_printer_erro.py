import pytest

from tests.test_printer_claim import _make_order


@pytest.mark.asyncio
async def test_erro_marks_order_and_saves_message(client, db_session):
    o = _make_order(status="IMPRIMINDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/erro",
        json={"agent_password": "test_agent", "mensagem": "filament out"},
    )
    assert resp.status_code == 200
    await db_session.refresh(o)
    assert o.status == "ERRO_IMPRESSAO"
    assert o.erro_mensagem == "filament out"
    assert o.erro_em is not None


@pytest.mark.asyncio
async def test_erro_from_preparando_also_works(client, db_session):
    o = _make_order(status="PREPARANDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/erro",
        json={"agent_password": "test_agent", "mensagem": "slice failed"},
    )
    assert resp.status_code == 200
    await db_session.refresh(o)
    assert o.status == "ERRO_IMPRESSAO"
