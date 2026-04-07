from fastapi import APIRouter

from services.correios import correios_service

router = APIRouter(tags=["shipping"])


@router.get("/shipping/estimate")
async def estimate_shipping(cep_destino: str, peso_gramas: float):
    """Calcula estimativa de frete PAC."""
    try:
        frete = await correios_service.calcular_frete(cep_destino, peso_gramas)
        return {"success": True, "data": frete, "error": None}
    except ValueError as e:
        return {"success": False, "data": None, "error": str(e)}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
