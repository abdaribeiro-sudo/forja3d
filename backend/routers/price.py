from fastapi import APIRouter
from pydantic import BaseModel

from services.price_calculator import price_service
from services.mesh_repair import mesh_service

router = APIRouter(tags=["price"])


class PriceEstimateRequest(BaseModel):
    volume_cm3: float
    material: str = "PLA"
    escala: float = 1.0


@router.post("/price/estimate")
async def estimate_price(request: PriceEstimateRequest):
    """Calcula estimativa de preço com base no volume e material."""
    volume_escalado = request.volume_cm3 * (request.escala ** 3)
    peso = mesh_service.estimate_weight(volume_escalado, request.material)
    tempo = mesh_service.estimate_print_time(volume_escalado)
    preco = price_service.calcular(peso, request.material, tempo)

    return {
        "success": True,
        "data": {
            "peso_gramas": round(peso, 1),
            "tempo_impressao_horas": tempo,
            **preco,
        },
        "error": None,
    }
