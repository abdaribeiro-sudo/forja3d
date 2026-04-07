import asyncio
import os
from typing import Optional

import httpx
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ai3d.v20250513 import ai3d_client, models as ai3d_models


class HunyuanService:
    """Integração com a API Tencent Cloud Hunyuan 3D (módulo ai3d)."""

    def __init__(self):
        self.secret_id = os.getenv("TENCENT_SECRET_ID", "")
        self.secret_key = os.getenv("TENCENT_SECRET_KEY", "")
        self.region = os.getenv("TENCENT_REGION", "ap-singapore")
        self._client: ai3d_client.Ai3dClient | None = None

    def _get_client(self) -> ai3d_client.Ai3dClient:
        if self._client is None:
            cred = credential.Credential(self.secret_id, self.secret_key)
            http_profile = HttpProfile()
            http_profile.endpoint = "ai3d.tencentcloudapi.com"
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            self._client = ai3d_client.Ai3dClient(cred, self.region, client_profile)
        return self._client

    async def submit_generation(
        self,
        prompt: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> str:
        """Submete job de geração 3D. Retorna job_id."""
        client = self._get_client()
        req = ai3d_models.SubmitHunyuanTo3DRapidJobRequest()

        params = {"ResultFormat": "glb"}
        if prompt:
            params["Prompt"] = prompt
        if image_base64:
            params["ImageBase64"] = image_base64
        if image_url:
            params["ImageUrl"] = image_url

        req.from_json_string(str(params).replace("'", '"'))

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, client.SubmitHunyuanTo3DRapidJob, req
        )
        return resp.JobId

    async def check_status(self, job_id: str) -> dict:
        """Verifica status do job. Retorna dict com status e URLs dos modelos."""
        client = self._get_client()
        req = ai3d_models.QueryHunyuanTo3DRapidJobRequest()
        req.from_json_string(f'{{"JobId": "{job_id}"}}')

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, client.QueryHunyuanTo3DRapidJob, req
        )

        result = {"job_id": job_id, "status": resp.Status}

        if resp.Status == "FINISHED" and resp.ResultFile3Ds:
            # ResultFile3Ds é uma lista de URLs dos arquivos gerados
            result["model_urls"] = resp.ResultFile3Ds
            result["model_url"] = resp.ResultFile3Ds[0] if resp.ResultFile3Ds else None

        if resp.ErrorCode:
            result["error_code"] = resp.ErrorCode
            result["error_message"] = resp.ErrorMessage

        return result

    async def download_model(self, model_url: str, output_path: str) -> str:
        """Baixa o arquivo GLB gerado. Retorna caminho local."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(model_url, follow_redirects=True)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(resp.content)
        return output_path


hunyuan_service = HunyuanService()
