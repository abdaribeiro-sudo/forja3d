import os
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import require_password
from database import get_db
from models.state_machine import TransitionError, assert_allowed
from models.tables import Order
from services.notifier import notifier

router = APIRouter(tags=["printer"], prefix="/printer")

AGENT_PASSWORD = require_password("AGENT_PASSWORD")
ORPHAN_PREPARING_MINUTES = int(os.getenv("ORPHAN_PREPARING_MINUTES", "45"))


def verify_agent(agent_password: str) -> None:
    """Valida senha do agent; levanta HTTP 401 se inválida."""
    if agent_password != AGENT_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autorizado (agent)",
        )


class AgentRequest(BaseModel):
    agent_password: str


def _order_to_dict(o: Order) -> dict:
    return {
        "id": o.id,
        "nome": o.nome,
        "email": o.email,
        "status": o.status,
        "modelo_url": o.modelo_url,
        "modelo_path": o.modelo_path,
        "material": o.material,
        "escala": o.escala,
        "peso_gramas": o.peso_gramas,
        "volume_cm3": o.volume_cm3,
        "tempo_impressao_horas": o.tempo_impressao_horas,
        "preco_centavos": o.preco_centavos,
        "frete_centavos": o.frete_centavos,
        "cep_destino": o.cep_destino,
        "prazo_dias": o.prazo_dias,
        "codigo_rastreio": o.codigo_rastreio,
        "progresso_percentual": o.progresso_percentual,
        "camada_atual": o.camada_atual,
        "camada_total": o.camada_total,
        "erro_mensagem": o.erro_mensagem,
        "impressao_iniciada_em": o.impressao_iniciada_em.isoformat() if o.impressao_iniciada_em else None,
        "impressao_concluida_em": o.impressao_concluida_em.isoformat() if o.impressao_concluida_em else None,
        "arquivo_3mf_path": o.arquivo_3mf_path,
    }


@router.post("/claim")
async def claim_next_job(
    req: AgentRequest,
    db: AsyncSession = Depends(get_db),
):
    verify_agent(req.agent_password)

    # 1. Cleanup de PREPARANDO órfão
    threshold = datetime.utcnow() - timedelta(minutes=ORPHAN_PREPARING_MINUTES)
    orphans_stmt = select(Order).where(
        Order.status == "PREPARANDO",
        Order.impressao_iniciada_em < threshold,
    )
    orphans = (await db.execute(orphans_stmt)).scalars().all()
    for o in orphans:
        o.status = "ERRO_IMPRESSAO"
        o.erro_mensagem = "Preparação abandonada (timeout)"
        o.erro_em = datetime.utcnow()

    # 2. Claim próximo PAGO com SKIP LOCKED
    claim_stmt = (
        select(Order)
        .where(Order.status == "PAGO")
        .order_by(Order.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(claim_stmt)
    order = result.scalar_one_or_none()

    if order is None:
        await db.commit()  # flush do cleanup acima
        return {"success": True, "data": None, "error": None}

    order.status = "PREPARANDO"
    order.impressao_iniciada_em = datetime.utcnow()
    await db.commit()
    await db.refresh(order)

    return {"success": True, "data": _order_to_dict(order), "error": None}


class StatusUpdateRequest(BaseModel):
    agent_password: str
    status: Literal["IMPRIMINDO", "IMPRESSO"]


@router.post("/orders/{order_id}/status")
async def update_status(
    order_id: str,
    req: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    verify_agent(req.agent_password)

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    try:
        assert_allowed(order.status, req.status)
    except TransitionError as e:
        raise HTTPException(status_code=400, detail=f"Transição ilegal: {e}")

    order.status = req.status
    if req.status == "IMPRESSO":
        order.impressao_concluida_em = datetime.utcnow()

    await db.commit()
    await db.refresh(order)

    if req.status == "IMPRIMINDO":
        await notifier.send_print_started(order)
    elif req.status == "IMPRESSO":
        await notifier.send_print_finished(order)

    return {"success": True, "data": _order_to_dict(order), "error": None}


class ProgressUpdateRequest(BaseModel):
    agent_password: str
    percentual: int
    camada_atual: int
    camada_total: int


@router.post("/orders/{order_id}/progress")
async def update_progress(
    order_id: str,
    req: ProgressUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    verify_agent(req.agent_password)

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    order.progresso_percentual = req.percentual
    order.camada_atual = req.camada_atual
    order.camada_total = req.camada_total

    await db.commit()
    return {"success": True, "data": {"updated": True}, "error": None}


class ErroRequest(BaseModel):
    agent_password: str
    mensagem: str


@router.post("/orders/{order_id}/erro")
async def report_error(
    order_id: str,
    req: ErroRequest,
    db: AsyncSession = Depends(get_db),
):
    verify_agent(req.agent_password)

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    order.status = "ERRO_IMPRESSAO"
    order.erro_mensagem = req.mensagem[:2000]  # trunca
    order.erro_em = datetime.utcnow()
    await db.commit()
    await db.refresh(order)
    await notifier.send_print_error(order)

    return {"success": True, "data": _order_to_dict(order), "error": None}
