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

    async def criar_preferencia(
        self, order_id: str, valor_centavos: int, descricao: str, email: str
    ) -> dict:
        """Cria preferência de pagamento. Retorna init_point e preference_id."""
        sdk = self._get_sdk()

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
            "notification_url": os.getenv("MP_WEBHOOK_URL", ""),
            "back_urls": {
                "success": f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/pedido/{order_id}",
                "failure": f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/checkout?error=1",
                "pending": f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/pedido/{order_id}",
            },
            "auto_return": "approved",
        }

        result = sdk.preference().create(preference_data)
        response = result["response"]

        return {
            "preference_id": response["id"],
            "init_point": response["init_point"],
        }

    async def verificar_pagamento(self, payment_id: str) -> dict:
        """Verifica status de um pagamento."""
        sdk = self._get_sdk()
        result = sdk.payment().get(payment_id)
        response = result["response"]

        return {
            "payment_id": str(response["id"]),
            "status": response["status"],
            "external_reference": response.get("external_reference"),
        }


mp_service = MercadoPagoService()
