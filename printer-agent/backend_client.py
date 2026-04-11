"""Cliente HTTP assíncrono para o backend FORJA3D."""
import logging
from dataclasses import dataclass
from typing import Literal

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Order:
    id: str
    nome: str
    email: str
    status: str
    modelo_url: str
    material: str
    escala: float
    peso_gramas: float
    tempo_impressao_horas: float

    @classmethod
    def from_dict(cls, d: dict) -> "Order":
        return cls(
            id=d["id"],
            nome=d["nome"],
            email=d.get("email", ""),
            status=d["status"],
            modelo_url=d["modelo_url"],
            material=d["material"],
            escala=d.get("escala", 1.0),
            peso_gramas=d.get("peso_gramas", 0.0),
            tempo_impressao_horas=d.get("tempo_impressao_horas", 0.0),
        )


class BackendClient:
    def __init__(self, backend_url: str, agent_password: str):
        self.base = backend_url
        self.password = agent_password
        self._client = httpx.AsyncClient(timeout=60.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def claim_next_job(self) -> Order | None:
        try:
            r = await self._client.post(
                f"{self.base}/api/printer/claim",
                json={"agent_password": self.password},
            )
            r.raise_for_status()
            body = r.json()
            if not body.get("success") or body.get("data") is None:
                return None
            return Order.from_dict(body["data"])
        except Exception as e:
            logger.warning("claim_next_job falhou: %s", e)
            return None

    async def update_status(self, order_id: str, status: Literal["IMPRIMINDO", "IMPRESSO"]) -> None:
        r = await self._client.post(
            f"{self.base}/api/printer/orders/{order_id}/status",
            json={"agent_password": self.password, "status": status},
        )
        r.raise_for_status()

    async def update_progress(self, order_id: str, percentual: int, camada_atual: int, camada_total: int) -> None:
        try:
            r = await self._client.post(
                f"{self.base}/api/printer/orders/{order_id}/progress",
                json={
                    "agent_password": self.password,
                    "percentual": percentual,
                    "camada_atual": camada_atual,
                    "camada_total": camada_total,
                },
            )
            r.raise_for_status()
        except Exception as e:
            logger.warning("update_progress falhou: %s", e)

    async def report_error(self, order_id: str, mensagem: str) -> None:
        try:
            r = await self._client.post(
                f"{self.base}/api/printer/orders/{order_id}/erro",
                json={"agent_password": self.password, "mensagem": mensagem},
            )
            r.raise_for_status()
        except Exception as e:
            logger.error("report_error falhou: %s (mensagem original: %s)", e, mensagem)

    async def download_model(self, modelo_url: str, dest_path: str) -> None:
        url = modelo_url if modelo_url.startswith("http") else f"{self.base}{modelo_url}"
        async with self._client.stream("GET", url) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in r.aiter_bytes():
                    f.write(chunk)
