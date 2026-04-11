"""Orquestra um pedido do download ao IMPRESSO / ERRO_IMPRESSAO."""
import asyncio
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from backend_client import BackendClient, Order
from printer_client import PrinterClient, ProgressEvent
from slicer import Slicer, SlicerError

logger = logging.getLogger(__name__)

PROGRESS_THROTTLE_SECONDS = 30


@dataclass
class JobResult:
    order_id: str
    status: Literal["IMPRESSO", "ERRO_IMPRESSAO"]
    error_message: str | None = None


class JobRunner:
    def __init__(
        self,
        backend: BackendClient,
        printer: PrinterClient,
        slicer: Slicer,
        download_dir: Path,
    ):
        self.backend = backend
        self.printer = printer
        self.slicer = slicer
        self.download_dir = download_dir
        self._last_progress: ProgressEvent | None = None
        self._last_flush_at: float = 0.0
        self._done = asyncio.Event()
        self._error_msg: str | None = None
        self._order_id: str = ""

    async def run(self, order: Order) -> JobResult:
        logger.info("Processando pedido %s", order.id)

        glb_path = self.download_dir / f"{order.id}.glb"
        mf_path = self.download_dir / f"{order.id}.3mf"

        # 1. Download
        try:
            await self.backend.download_model(order.modelo_url, str(glb_path))
        except Exception as e:
            return await self._fail(order.id, f"Falha ao baixar modelo: {e}")

        # 2. Slice
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self.slicer.slice, str(glb_path), order.material, str(mf_path)
            )
        except SlicerError as e:
            return await self._fail(order.id, f"Falha no fatiamento: {e}")
        except Exception as e:
            return await self._fail(order.id, f"Erro inesperado no slicer: {e}")

        # 3. Upload
        try:
            remote = await self.printer.upload_file(str(mf_path))
        except Exception as e:
            return await self._fail(order.id, f"Falha no upload FTP: {e}")

        # 4. Register callbacks
        self._order_id = order.id
        self.printer.on_progress(self._on_progress)
        self.printer.on_finished(self._on_finished)
        self.printer.on_error(self._on_printer_error)

        # 5. Start print
        try:
            await self.printer.start_print(remote)
        except Exception as e:
            return await self._fail(order.id, f"Falha ao iniciar impressão: {e}")

        # 6. Status → IMPRIMINDO
        try:
            await self.backend.update_status(order.id, "IMPRIMINDO")
        except Exception as e:
            return await self._fail(order.id, f"Falha ao atualizar status: {e}")

        # 7. Wait for completion or error
        await self._done.wait()

        if self._error_msg:
            return await self._fail(order.id, self._error_msg)

        # Final progress flush (100%)
        if self._last_progress is not None:
            try:
                await self.backend.update_progress(
                    order.id,
                    100,
                    self._last_progress.camada_total or self._last_progress.camada_atual,
                    self._last_progress.camada_total,
                )
            except Exception as e:
                logger.warning("Flush final de progresso falhou: %s", e)

        # 8. Status → IMPRESSO
        try:
            await self.backend.update_status(order.id, "IMPRESSO")
        except Exception as e:
            return await self._fail(order.id, f"Falha ao marcar IMPRESSO: {e}")

        return JobResult(order_id=order.id, status="IMPRESSO")

    def _on_progress(self, ev: ProgressEvent) -> None:
        self._last_progress = ev
        now = time.monotonic()
        if now - self._last_flush_at >= PROGRESS_THROTTLE_SECONDS:
            self._last_flush_at = now
            asyncio.create_task(self._flush_progress())

    async def _flush_progress(self) -> None:
        if self._last_progress is None:
            return
        p = self._last_progress
        await self.backend.update_progress(
            self._order_id, p.percentual, p.camada_atual, p.camada_total
        )

    def _on_finished(self) -> None:
        self._done.set()

    def _on_printer_error(self, msg: str) -> None:
        self._error_msg = msg
        self._done.set()

    async def _fail(self, order_id: str, msg: str) -> JobResult:
        logger.error("Job %s falhou: %s", order_id, msg)
        await self.backend.report_error(order_id, msg)
        return JobResult(order_id=order_id, status="ERRO_IMPRESSAO", error_message=msg)
