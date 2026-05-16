"""Integração com a API Tencent Hunyuan 3D.

IMPORTANTE: a conta é Tencent Cloud International. Nesse caso o Hunyuan 3D
é exposto no namespace de serviço `hunyuan` versão v20230901 (SDK
`tencentcloud-sdk-python-intl-en`), região `ap-singapore` — e NÃO no
namespace `ai3d` v20250513 (que é o produto mainland). Chamar `ai3d`
retorna `ResourceUnavailable.InterfaceNotExist`.
"""
import asyncio
import os
from typing import Optional

import httpx
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models


class HunyuanService:
    """Integração com Tencent Hunyuan 3D (namespace `hunyuan` v20230901)."""

    def __init__(self):
        self.secret_id = os.getenv("TENCENT_SECRET_ID", "")
        self.secret_key = os.getenv("TENCENT_SECRET_KEY", "")
        self.region = os.getenv("TENCENT_REGION", "ap-singapore")
        self.endpoint = os.getenv(
            "TENCENT_HUNYUAN_ENDPOINT", "hunyuan.intl.tencentcloudapi.com"
        )
        self._client: hunyuan_client.HunyuanClient | None = None

    def _get_client(self) -> hunyuan_client.HunyuanClient:
        if self._client is None:
            cred = credential.Credential(self.secret_id, self.secret_key)
            http_profile = HttpProfile()
            http_profile.endpoint = self.endpoint
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            self._client = hunyuan_client.HunyuanClient(
                cred, self.region, client_profile
            )
        return self._client

    async def submit_generation(
        self,
        prompt: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> str:
        """Submete job de geração 3D (Pro). Retorna o JobId."""
        client = self._get_client()
        req = models.SubmitHunyuanTo3DProJobRequest()
        if prompt:
            req.Prompt = prompt
        if image_base64:
            req.ImageBase64 = image_base64
        if image_url:
            req.ImageUrl = image_url

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, client.SubmitHunyuanTo3DProJob, req
        )
        return resp.JobId

    async def check_status(self, job_id: str) -> dict:
        """Verifica status do job. Normaliza p/ o contrato usado em generate.py.

        Status do Hunyuan v20230901: WAIT / RUN / FAIL / DONE.
        generate.py espera "FINISHED" + model_url quando pronto, e error_code
        quando falha — então mapeamos DONE -> FINISHED.
        """
        client = self._get_client()
        req = models.QueryHunyuanTo3DProJobRequest()
        req.JobId = job_id

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, client.QueryHunyuanTo3DProJob, req
        )

        status = "FINISHED" if resp.Status == "DONE" else resp.Status
        result = {"job_id": job_id, "status": status}

        files = resp.ResultFile3Ds or []
        if resp.Status == "DONE" and files:
            urls = [f.Url for f in files if getattr(f, "Url", None)]
            glb = next(
                (f.Url for f in files if (f.Type or "").upper() == "GLB"),
                urls[0] if urls else None,
            )
            result["model_urls"] = urls
            result["model_url"] = glb

        if resp.ErrorCode:
            result["error_code"] = resp.ErrorCode
            result["error_message"] = resp.ErrorMessage

        return result

    async def download_model(self, model_url: str, output_path: str) -> str:
        """Baixa o arquivo de modelo gerado. Retorna caminho local."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(model_url, follow_redirects=True)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(resp.content)
        return output_path


hunyuan_service = HunyuanService()
