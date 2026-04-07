from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.tables import Order
from services.mercadopago import mp_service

router = APIRouter(tags=["payment"])


@router.post("/payment/create/{order_id}")
async def create_payment(order_id: str, db: AsyncSession = Depends(get_db)):
    """Cria preferência de pagamento no Mercado Pago."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        return {"success": False, "data": None, "error": "Pedido não encontrado."}

    if order.status != "AGUARDANDO_PAGAMENTO":
        return {"success": False, "data": None, "error": "Pedido já foi pago."}

    try:
        total = order.preco_centavos + order.frete_centavos
        descricao = f"FORJA3D - Impressão 3D {order.material} ({order.peso_gramas}g)"

        payment_data = await mp_service.criar_preferencia(
            order_id=order.id,
            valor_centavos=total,
            descricao=descricao,
            email=order.email,
        )

        # Salva preference_id no pedido
        order.mp_preference_id = payment_data["preference_id"]
        await db.commit()

        return {
            "success": True,
            "data": {
                "preference_id": payment_data["preference_id"],
                "init_point": payment_data["init_point"],
            },
            "error": None,
        }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


@router.post("/payment/webhook")
async def payment_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Processa notificação de pagamento do Mercado Pago."""
    body = await request.json()

    # O Mercado Pago envia diferentes tipos de notificação
    if body.get("type") != "payment":
        return {"success": True, "data": {"received": True}, "error": None}

    payment_id = str(body.get("data", {}).get("id", ""))
    if not payment_id:
        return {"success": False, "data": None, "error": "Payment ID não encontrado."}

    try:
        # Verifica o pagamento na API do Mercado Pago
        payment_info = await mp_service.verificar_pagamento(payment_id)

        if payment_info["status"] == "approved":
            order_id = payment_info.get("external_reference")
            if order_id:
                result = await db.execute(select(Order).where(Order.id == order_id))
                order = result.scalar_one_or_none()

                if order and order.status == "AGUARDANDO_PAGAMENTO":
                    order.status = "PAGO"
                    order.mp_payment_id = payment_id
                    await db.commit()

        return {"success": True, "data": {"received": True}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
