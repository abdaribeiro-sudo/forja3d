"""Envio de emails transacionais via Resend.

Best-effort: falhas não bloqueiam as transições de estado.
"""
import logging
import os
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "emails"


class Notifier:
    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY", "")
        self.from_address = os.getenv("EMAIL_FROM", "FORJA3D <no-reply@forja3d.com.br>")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        self.enabled = bool(self.api_key)
        if self.enabled:
            resend.api_key = self.api_key

        self.jinja = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def _render(self, template_name: str, **ctx) -> str:
        tmpl = self.jinja.get_template(template_name)
        return tmpl.render(frontend_url=self.frontend_url, **ctx)

    async def _send(self, to: str, subject: str, html: str) -> None:
        if not self.enabled:
            logger.warning("Resend não configurado; email '%s' não enviado", subject)
            return
        try:
            resend.Emails.send({
                "from": self.from_address,
                "to": to,
                "subject": subject,
                "html": html,
            })
        except Exception as e:
            logger.warning("Falha ao enviar email '%s': %s", subject, e)

    async def send_payment_received(self, order) -> None:
        html = self._render("payment_received.html", order=order)
        await self._send(order.email, "Recebemos seu pagamento — FORJA3D", html)

    async def send_print_started(self, order) -> None:
        html = self._render("print_started.html", order=order)
        await self._send(order.email, "Sua peça entrou na impressora", html)

    async def send_print_finished(self, order) -> None:
        html = self._render("print_finished.html", order=order)
        await self._send(order.email, "Sua peça está pronta!", html)

    async def send_shipped(self, order) -> None:
        html = self._render("shipped.html", order=order)
        await self._send(order.email, "Seu pedido foi postado", html)

    async def send_print_error(self, order) -> None:
        html = self._render("print_error.html", order=order)
        await self._send(order.email, "Tivemos um contratempo com sua peça", html)


notifier = Notifier()
