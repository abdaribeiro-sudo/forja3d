import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.tables import Order
from services.notifier import notifier

router = APIRouter(tags=["admin"])

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def verify_admin(password: str) -> bool:
    return password == ADMIN_PASSWORD


class LoginRequest(BaseModel):
    password: str


class UpdateOrderRequest(BaseModel):
    password: str
    status: Optional[str] = None
    codigo_rastreio: Optional[str] = None


class RequeueRequest(BaseModel):
    password: str


@router.post("/admin/login")
async def admin_login(request: LoginRequest):
    if verify_admin(request.password):
        return {"success": True, "data": {"authenticated": True}, "error": None}
    return {"success": False, "data": {"authenticated": False}, "error": "Senha incorreta."}


@router.get("/admin/orders")
async def admin_list_orders(
    password: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if not verify_admin(password):
        return {"success": False, "data": None, "error": "Não autorizado."}

    result = await db.execute(select(Order).order_by(Order.created_at.desc()))
    orders_list = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": o.id,
                "nome": o.nome,
                "email": o.email,
                "status": o.status,
                "material": o.material,
                "escala": o.escala,
                "peso_gramas": o.peso_gramas,
                "preco_centavos": o.preco_centavos,
                "frete_centavos": o.frete_centavos,
                "total_centavos": o.preco_centavos + o.frete_centavos,
                "prazo_dias": o.prazo_dias,
                "codigo_rastreio": o.codigo_rastreio,
                "mp_payment_id": o.mp_payment_id,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "updated_at": o.updated_at.isoformat() if o.updated_at else None,
            }
            for o in orders_list
        ],
        "error": None,
    }


@router.post("/admin/orders/{order_id}")
async def admin_update_order(
    order_id: str,
    request: UpdateOrderRequest,
    db: AsyncSession = Depends(get_db),
):
    if not verify_admin(request.password):
        return {"success": False, "data": None, "error": "Não autorizado."}

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        return {"success": False, "data": None, "error": "Pedido não encontrado."}

    old_status = order.status
    if request.status:
        order.status = request.status
    if request.codigo_rastreio is not None:
        order.codigo_rastreio = request.codigo_rastreio

    await db.commit()
    await db.refresh(order)

    if old_status != "ENVIADO" and order.status == "ENVIADO" and order.codigo_rastreio:
        await notifier.send_shipped(order)

    return {
        "success": True,
        "data": {"id": order.id, "status": order.status, "codigo_rastreio": order.codigo_rastreio},
        "error": None,
    }


@router.post("/admin/orders/{order_id}/requeue")
async def admin_requeue_order(
    order_id: str,
    request: RequeueRequest,
    db: AsyncSession = Depends(get_db),
):
    if not verify_admin(request.password):
        return {"success": False, "data": None, "error": "Não autorizado."}

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if order.status != "ERRO_IMPRESSAO":
        raise HTTPException(
            status_code=400,
            detail=f"Só é possível reenfileirar pedidos em ERRO_IMPRESSAO (status atual: {order.status})",
        )

    order.status = "PAGO"
    order.progresso_percentual = None
    order.camada_atual = None
    order.camada_total = None
    order.erro_mensagem = None
    order.erro_em = None
    order.impressao_iniciada_em = None
    order.impressao_concluida_em = None
    order.arquivo_3mf_path = None

    await db.commit()
    await db.refresh(order)
    return {
        "success": True,
        "data": {"id": order.id, "status": order.status},
        "error": None,
    }
