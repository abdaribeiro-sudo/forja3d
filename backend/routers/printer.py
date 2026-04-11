import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.tables import Order

router = APIRouter(tags=["printer"], prefix="/printer")

AGENT_PASSWORD = os.getenv("AGENT_PASSWORD", "dev_agent_password")
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
