import os

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.tables import Order
from models.schemas import OrderCreate
from services.price_calculator import price_service
from services.mesh_repair import mesh_service
from services.correios import correios_service

router = APIRouter(tags=["orders"])

STORAGE_PATH = os.getenv("STORAGE_PATH", "./uploads")


@router.post("/orders")
async def create_order(order: OrderCreate, db: AsyncSession = Depends(get_db)):
    """Cria pedido com cálculo de preço e frete."""
    try:
        # Calcula dimensões do modelo
        model_path = os.path.join(STORAGE_PATH, os.path.basename(order.modelo_url))
        volume_cm3 = 50.0  # Valor padrão se não conseguir calcular
        bounding_box = [100.0, 100.0, 100.0]

        if os.path.exists(model_path):
            repaired_path = model_path.replace(".glb", "_final.glb")
            mesh_info = await mesh_service.repair(model_path, repaired_path)
            volume_cm3 = mesh_info["volume_cm3"] * (order.escala ** 3)
            bounding_box = mesh_info["bounding_box_mm"]

            # Verifica se cabe na impressora
            if not mesh_service.check_dimensions(bounding_box, order.escala):
                return {
                    "success": False,
                    "data": None,
                    "error": "Modelo excede o volume máximo da impressora (256x256x256mm).",
                }

        # Calcula peso e tempo
        peso_gramas = mesh_service.estimate_weight(volume_cm3, order.material)
        tempo_horas = mesh_service.estimate_print_time(volume_cm3)

        # Calcula preço
        preco = price_service.calcular(peso_gramas, order.material, tempo_horas)

        # Calcula frete
        frete = await correios_service.calcular_frete(order.cep_destino, peso_gramas)

        # Cria pedido no banco
        new_order = Order(
            nome=order.nome,
            email=order.email,
            modelo_url=order.modelo_url,
            modelo_path=model_path if os.path.exists(model_path) else None,
            material=order.material,
            escala=order.escala,
            peso_gramas=peso_gramas,
            volume_cm3=volume_cm3,
            tempo_impressao_horas=tempo_horas,
            preco_centavos=preco["preco_final_centavos"],
            frete_centavos=frete["preco_centavos"],
            cep_destino=order.cep_destino,
            prazo_dias=frete["prazo_dias"],
        )
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)

        return {
            "success": True,
            "data": {
                "id": new_order.id,
                "status": new_order.status,
                "peso_gramas": peso_gramas,
                "tempo_impressao_horas": tempo_horas,
                "preco_centavos": preco["preco_final_centavos"],
                "preco_detalhado": preco,
                "frete_centavos": frete["preco_centavos"],
                "prazo_dias": frete["prazo_dias"],
                "total_centavos": preco["preco_final_centavos"] + frete["preco_centavos"],
            },
            "error": None,
        }
    except ValueError as e:
        return {"success": False, "data": None, "error": str(e)}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


@router.get("/orders/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Busca pedido por ID."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        return {"success": False, "data": None, "error": "Pedido não encontrado."}

    return {
        "success": True,
        "data": {
            "id": order.id,
            "nome": order.nome,
            "status": order.status,
            "material": order.material,
            "escala": order.escala,
            "peso_gramas": order.peso_gramas,
            "preco_centavos": order.preco_centavos,
            "frete_centavos": order.frete_centavos,
            "total_centavos": order.preco_centavos + order.frete_centavos,
            "prazo_dias": order.prazo_dias,
            "codigo_rastreio": order.codigo_rastreio,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        },
        "error": None,
    }


@router.get("/orders")
async def list_orders(db: AsyncSession = Depends(get_db)):
    """Lista todos os pedidos (para o painel admin)."""
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
                "preco_centavos": o.preco_centavos,
                "frete_centavos": o.frete_centavos,
                "total_centavos": o.preco_centavos + o.frete_centavos,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders_list
        ],
        "error": None,
    }
