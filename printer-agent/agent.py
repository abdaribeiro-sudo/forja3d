"""
Printer Agent — Monitora fila de pedidos pagos e envia para a Bambu Lab X1 Carbon.
Roda localmente no PC conectado à impressora.

Uso: python agent.py
"""

import asyncio
import json
import os
import subprocess
import sys

import httpx


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path) as f:
        return json.load(f)


class PrinterAgent:
    def __init__(self, config: dict):
        self.backend_url = config["backend_url"]
        self.admin_password = config.get("admin_password", "admin123")
        self.poll_interval = config.get("poll_interval_seconds", 30)
        self.printer_ip = config["printer"]["ip"]
        self.printer_serial = config["printer"]["serial"]
        self.printer_access_code = config["printer"]["access_code"]
        self.bambu_studio_path = config.get("bambu_studio_cli", "")
        self.download_dir = os.path.join(os.path.dirname(__file__), "downloads")
        os.makedirs(self.download_dir, exist_ok=True)

    async def fetch_paid_orders(self) -> list:
        """Busca pedidos com status PAGO no backend."""
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{self.backend_url}/api/admin/orders",
                params={"password": self.admin_password},
            )
            data = res.json()
            if data.get("success") and data.get("data"):
                return [o for o in data["data"] if o["status"] == "PAGO"]
        return []

    async def update_order_status(self, order_id: str, status: str, rastreio: str = ""):
        """Atualiza status do pedido no backend."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.backend_url}/api/admin/orders/{order_id}",
                json={
                    "password": self.admin_password,
                    "status": status,
                    "codigo_rastreio": rastreio if rastreio else None,
                },
            )

    async def download_model(self, order: dict) -> str | None:
        """Baixa o arquivo GLB do pedido."""
        model_url = order.get("modelo_url", "")
        if not model_url:
            return None

        filename = f"{order['id']}.glb"
        filepath = os.path.join(self.download_dir, filename)

        if os.path.exists(filepath):
            return filepath

        async with httpx.AsyncClient() as client:
            url = f"{self.backend_url}{model_url}" if model_url.startswith("/") else model_url
            res = await client.get(url, follow_redirects=True)
            res.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(res.content)

        print(f"  Modelo baixado: {filepath}")
        return filepath

    def slice_model(self, glb_path: str, material: str) -> str | None:
        """Fatia o modelo GLB usando BambuStudio CLI. Retorna caminho do .3mf."""
        if not self.bambu_studio_path or not os.path.exists(self.bambu_studio_path):
            print("  AVISO: BambuStudio CLI não configurado. Pulando fatiamento.")
            return None

        output_path = glb_path.replace(".glb", ".3mf")
        try:
            subprocess.run(
                [
                    self.bambu_studio_path,
                    "--export-3mf", output_path,
                    "--load-filament", material,
                    glb_path,
                ],
                check=True,
                capture_output=True,
            )
            print(f"  Fatiado: {output_path}")
            return output_path
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  Erro ao fatiar: {e}")
            return None

    async def send_to_printer(self, file_path: str) -> bool:
        """Envia arquivo para a impressora via FTP/MQTT."""
        # Usa FTP para enviar o arquivo para a X1 Carbon
        # A impressora aceita uploads FTP na porta padrão
        import ftplib

        try:
            ftp = ftplib.FTP()
            ftp.connect(self.printer_ip, 990, timeout=30)
            ftp.login("bblp", self.printer_access_code)
            ftp.set_pasv(True)

            filename = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                ftp.storbinary(f"STOR /sdcard/{filename}", f)

            ftp.quit()
            print(f"  Enviado para impressora: {filename}")
            return True
        except Exception as e:
            print(f"  Erro ao enviar para impressora: {e}")
            return False

    async def process_order(self, order: dict):
        """Processa um pedido completo: baixa, fatia, envia e atualiza."""
        order_id = order["id"]
        print(f"\nProcessando pedido #{order_id[:8]}...")

        # 1. Baixa o modelo
        glb_path = await self.download_model(order)
        if not glb_path:
            print(f"  Erro: não foi possível baixar o modelo do pedido #{order_id[:8]}")
            return

        # 2. Fatia o modelo
        file_to_print = self.slice_model(glb_path, order.get("material", "PLA"))
        if not file_to_print:
            file_to_print = glb_path  # Envia GLB direto se fatiamento falhar

        # 3. Atualiza status para IMPRIMINDO
        await self.update_order_status(order_id, "IMPRIMINDO")

        # 4. Envia para a impressora
        sent = await self.send_to_printer(file_to_print)
        if not sent:
            print(f"  Falha ao enviar para impressora. Pedido continua como IMPRIMINDO.")
            return

        print(f"  Pedido #{order_id[:8]} enviado para impressão!")

    async def run(self):
        """Loop principal do agent."""
        print("=" * 50)
        print("FORJA3D Printer Agent")
        print(f"Backend: {self.backend_url}")
        print(f"Impressora: {self.printer_ip}")
        print(f"Intervalo de polling: {self.poll_interval}s")
        print("=" * 50)

        while True:
            try:
                orders = await self.fetch_paid_orders()
                if orders:
                    print(f"\n{len(orders)} pedido(s) na fila de impressão:")
                    for order in orders:
                        await self.process_order(order)

                await asyncio.sleep(self.poll_interval)

            except KeyboardInterrupt:
                print("\nAgent encerrado.")
                break
            except Exception as e:
                print(f"\nErro no loop principal: {e}")
                await asyncio.sleep(self.poll_interval)


async def main():
    config = load_config()
    agent = PrinterAgent(config)
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
