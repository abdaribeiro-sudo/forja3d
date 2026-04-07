import os

import httpx
from fastapi import APIRouter, Depends, Response
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
        job_id = await hunyuan_service.submit_generation(
            prompt=request.prompt,
            image_base64=request.imagem_base64,
        )

        generation = Generation(
            task_id=job_id,
            prompt=request.prompt,
            status="PENDING",
        )
        db.add(generation)
        await db.commit()

        return {
            "success": True,
            "data": {"task_id": job_id, "status": "PENDING"},
            "error": None,
        }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


@router.get("/generate/{task_id}/status")
async def get_generation_status(task_id: str, db: AsyncSession = Depends(get_db)):
    """Verifica status da geração e baixa modelo quando pronto."""
    result = await db.execute(select(Generation).where(Generation.task_id == task_id))
    generation = result.scalar_one_or_none()

    if not generation:
        return {"success": False, "data": None, "error": "Geração não encontrada."}

    # Se já finalizou, retorna URL
    if generation.status == "FINISHED":
        model_url = _get_model_url(generation)
        return {
            "success": True,
            "data": {"task_id": task_id, "status": "FINISHED", "model_url": model_url},
            "error": None,
        }

    try:
        status_data = await hunyuan_service.check_status(task_id)

        if status_data.get("error_code"):
            generation.status = "FAILED"
            await db.commit()
            return {
                "success": False,
                "data": {"task_id": task_id, "status": "FAILED"},
                "error": status_data.get("error_message", "Erro na geração."),
            }

        if status_data["status"] == "FINISHED" and status_data.get("model_url"):
            tencent_url = status_data["model_url"]

            # Salva URL da Tencent no banco (sempre disponível como fallback)
            generation.status = "FINISHED"
            generation.model_url = tencent_url

            # Tenta baixar, reparar e salvar localmente
            mesh_info = None
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    resp = await client.get(tencent_url, follow_redirects=True)
                    resp.raise_for_status()
                    glb_bytes = resp.content

                repaired_bytes, mesh_info = await mesh_service.repair_from_bytes(glb_bytes)

                # Salva localmente se possível
                local_path = os.path.join(STORAGE_PATH, f"{task_id}.glb")
                os.makedirs(STORAGE_PATH, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(repaired_bytes)
                generation.model_path = local_path
            except Exception:
                # Se falhar o reparo/salvar, usa URL da Tencent direto
                pass

            await db.commit()

            model_url = _get_model_url(generation)
            data = {"task_id": task_id, "status": "FINISHED", "model_url": model_url}
            if mesh_info:
                data["mesh_info"] = mesh_info

            return {"success": True, "data": data, "error": None}

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


@router.get("/generate/{task_id}/model")
async def get_model_file(task_id: str, db: AsyncSession = Depends(get_db)):
    """Serve o arquivo GLB do modelo (proxy para produção sem filesystem)."""
    result = await db.execute(select(Generation).where(Generation.task_id == task_id))
    generation = result.scalar_one_or_none()

    if not generation or generation.status != "FINISHED":
        return {"success": False, "data": None, "error": "Modelo não disponível."}

    # Se tem arquivo local, serve direto
    if generation.model_path and os.path.exists(generation.model_path):
        with open(generation.model_path, "rb") as f:
            content = f.read()
        return Response(content=content, media_type="model/gltf-binary")

    # Senão, faz proxy da URL da Tencent
    if generation.model_url:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(generation.model_url, follow_redirects=True)
            return Response(content=resp.content, media_type="model/gltf-binary")

    return {"success": False, "data": None, "error": "Arquivo não encontrado."}


def _get_model_url(generation: Generation) -> str:
    """Retorna a melhor URL disponível para o modelo."""
    # Se tem arquivo local, usa o endpoint estático
    if generation.model_path and os.path.exists(generation.model_path):
        return f"/uploads/{os.path.basename(generation.model_path)}"
    # Senão, usa o endpoint proxy
    if generation.model_url:
        return f"/api/generate/{generation.task_id}/model"
    return ""
