import os
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.tables import Order

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

    if request.status:
        order.status = request.status
    if request.codigo_rastreio is not None:
        order.codigo_rastreio = request.codigo_rastreio

    await db.commit()

    return {
        "success": True,
        "data": {"id": order.id, "status": order.status, "codigo_rastreio": order.codigo_rastreio},
        "error": None,
    }
