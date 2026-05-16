import asyncio
import os

import mercadopago


class MercadoPagoService:
    """Integração com Mercado Pago para pagamentos PIX e cartão."""

    def __init__(self):
        self.access_token = os.getenv("MP_ACCESS_TOKEN", "")
        self._sdk: mercadopago.SDK | None = None

    def _get_sdk(self) -> mercadopago.SDK:
        if self._sdk is None:
            self._sdk = mercadopago.SDK(self.access_token)
        return self._sdk

    @staticmethod
    def _unwrap(result: dict, contexto: str) -> dict:
        """Valida a resposta do MP e expõe o erro real.

        O SDK do Mercado Pago não levanta exceção em erro HTTP — devolve
        {"status": 4xx, "response": {"message": ...}}. Sem isso, o caller
        fazia response["id"] e estourava um KeyError 'id' opaco.
        """
        status = result.get("status")
        response = result.get("response") or {}
        if status is None or status >= 400 or "error" in response:
            msg = response.get("message") or response.get("error") or "erro desconhecido"
            raise RuntimeError(
                f"Mercado Pago falhou em {contexto} (HTTP {status}): {msg}"
            )
        return response

    async def criar_preferencia(
        self, order_id: str, valor_centavos: int, descricao: str, email: str
    ) -> dict:
        """Cria preferência de pagamento. Retorna init_point e preference_id."""
        sdk = self._get_sdk()
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

        preference_data = {
            "items": [
                {
                    "id": order_id,
                    "title": descricao,
                    "quantity": 1,
                    "unit_price": valor_centavos / 100,
                    "currency_id": "BRL",
                }
            ],
            "payer": {"email": email},
            "payment_methods": {
                "excluded_payment_types": [],
                "installments": 6,
            },
            "external_reference": order_id,
            "back_urls": {
                "success": f"{frontend_url}/pedido/{order_id}",
                "failure": f"{frontend_url}/checkout?order_id={order_id}&error=1",
                "pending": f"{frontend_url}/pedido/{order_id}",
            },
        }

        # auto_return só é aceito pelo MP quando a success URL é pública HTTPS;
        # com localhost/http o MP responde 400 invalid_auto_return.
        if frontend_url.startswith("https://"):
            preference_data["auto_return"] = "approved"

        # MP rejeita notification_url vazia — só envia se houver webhook configurado.
        webhook_url = os.getenv("MP_WEBHOOK_URL", "").strip()
        if webhook_url:
            preference_data["notification_url"] = webhook_url

        # SDK do Mercado Pago é síncrono — executa em thread separada
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: sdk.preference().create(preference_data)
        )
        response = self._unwrap(result, "criar preferência")

        return {
            "preference_id": response["id"],
            "init_point": response["init_point"],
        }

    async def verificar_pagamento(self, payment_id: str) -> dict:
        """Verifica status de um pagamento."""
        sdk = self._get_sdk()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: sdk.payment().get(payment_id)
        )
        response = self._unwrap(result, "verificar pagamento")

        return {
            "payment_id": str(response["id"]),
            "status": response["status"],
            "external_reference": response.get("external_reference"),
        }


mp_service = MercadoPagoService()
