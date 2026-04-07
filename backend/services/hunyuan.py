import asyncio
import os
from typing import Optional

import httpx
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models as hunyuan_models


class HunyuanService:
    """Integração com a API Tencent Cloud Hunyuan 3D."""

    def __init__(self):
        self.secret_id = os.getenv("TENCENT_SECRET_ID", "")
        self.secret_key = os.getenv("TENCENT_SECRET_KEY", "")
        self.region = "ap-singapore"
        self._client: hunyuan_client.HunyuanClient | None = None

    def _get_client(self) -> hunyuan_client.HunyuanClient:
        if self._client is None:
            cred = credential.Credential(self.secret_id, self.secret_key)
            http_profile = HttpProfile()
            http_profile.endpoint = "hunyuan.tencentcloudapi.com"
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            self._client = hunyuan_client.HunyuanClient(cred, self.region, client_profile)
        return self._client

    async def submit_generation(
        self, prompt: Optional[str] = None, image_url: Optional[str] = None
    ) -> str:
        """Submete job de geração 3D. Retorna task_id."""
        client = self._get_client()
        req = hunyuan_models.SubmitHunyuan3DModelGenerationJobRequest()
        params = {}
        if prompt:
            params["Prompt"] = prompt
        if image_url:
            params["ImageUrl"] = image_url
        req.from_json_string(str(params).replace("'", '"'))

        # Executa chamada síncrona do SDK em thread separada
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, client.SubmitHunyuan3DModelGenerationJob, req
        )
        return resp.TaskId

    async def check_status(self, task_id: str) -> dict:
        """Verifica status do job. Retorna dict com status e URL do modelo."""
        client = self._get_client()
        req = hunyuan_models.QueryHunyuan3DModelGenerationJobRequest()
        req.from_json_string(f'{{"TaskId": "{task_id}"}}')

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, client.QueryHunyuan3DModelGenerationJob, req
        )

        result = {"task_id": task_id, "status": resp.Status}
        if resp.Status == "FINISHED" and resp.ModelUrl:
            result["model_url"] = resp.ModelUrl
        return result

    async def download_model(self, model_url: str, output_path: str) -> str:
        """Baixa o arquivo GLB gerado. Retorna caminho local."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        async with httpx.AsyncClient() as client:
            resp = await client.get(model_url, follow_redirects=True)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(resp.content)
        return output_path


hunyuan_service = HunyuanService()
