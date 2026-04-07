import os
import base64
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.tables import Generation
from models.schemas import GenerateRequest
from services.hunyuan import hunyuan_service
from services.mesh_repair import mesh_service

router = APIRouter(tags=["generate"])

STORAGE_PATH = os.getenv("STORAGE_PATH", "./uploads")


@router.post("/generate")
async def generate_model(request: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """Submete geração de modelo 3D via texto ou imagem base64."""
    if not request.prompt and not request.imagem_base64:
        return {"success": False, "data": None, "error": "Envie um prompt ou imagem."}

    try:
        # Se enviou imagem, salva e gera URL temporária
        image_path = None
        if request.imagem_base64:
            image_path = os.path.join(STORAGE_PATH, f"{uuid.uuid4()}.png")
            os.makedirs(STORAGE_PATH, exist_ok=True)
            with open(image_path, "wb") as f:
                f.write(base64.b64decode(request.imagem_base64))

        task_id = await hunyuan_service.submit_generation(
            prompt=request.prompt,
            image_url=None,  # TODO: servir imagem via URL pública se necessário
        )

        # Salva geração no banco
        generation = Generation(
            task_id=task_id,
            prompt=request.prompt,
            image_path=image_path,
            status="PENDING",
        )
        db.add(generation)
        await db.commit()

        return {
            "success": True,
            "data": {"task_id": task_id, "status": "PENDING"},
            "error": None,
        }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


@router.get("/generate/{task_id}/status")
async def get_generation_status(task_id: str, db: AsyncSession = Depends(get_db)):
    """Verifica status da geração e baixa modelo quando pronto."""
    # Busca no banco
    result = await db.execute(select(Generation).where(Generation.task_id == task_id))
    generation = result.scalar_one_or_none()

    if not generation:
        return {"success": False, "data": None, "error": "Geração não encontrada."}

    # Se já finalizou, retorna direto
    if generation.status == "FINISHED" and generation.model_path:
        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "status": "FINISHED",
                "model_url": f"/uploads/{os.path.basename(generation.model_path)}",
            },
            "error": None,
        }

    try:
        # Consulta status na API
        status_data = await hunyuan_service.check_status(task_id)

        if status_data["status"] == "FINISHED" and "model_url" in status_data:
            # Baixa e repara o modelo
            raw_path = os.path.join(STORAGE_PATH, f"{task_id}_raw.glb")
            repaired_path = os.path.join(STORAGE_PATH, f"{task_id}.glb")

            await hunyuan_service.download_model(status_data["model_url"], raw_path)
            mesh_info = await mesh_service.repair(raw_path, repaired_path)

            # Atualiza no banco
            generation.status = "FINISHED"
            generation.model_url = status_data["model_url"]
            generation.model_path = repaired_path
            await db.commit()

            return {
                "success": True,
                "data": {
                    "task_id": task_id,
                    "status": "FINISHED",
                    "model_url": f"/uploads/{task_id}.glb",
                    "mesh_info": mesh_info,
                },
                "error": None,
            }

        # Ainda processando
        generation.status = status_data["status"]
        await db.commit()

        return {
            "success": True,
            "data": {"task_id": task_id, "status": status_data["status"], "model_url": None},
            "error": None,
        }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
