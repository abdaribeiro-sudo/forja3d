"""FORJA3D Printer Agent — entrypoint.

Loop: claim → download → slice → upload → start → monitor → (IMPRESSO | ERRO).
"""
import asyncio
import logging

from backend_client import BackendClient
from config import load_config
from job_runner import JobRunner
from logging_setup import setup_logging
from printer_client import PrinterClient
from slicer import Slicer

logger = logging.getLogger(__name__)


async def reconcile_on_startup(backend: BackendClient, printer: PrinterClient) -> None:
    """Se a X1 está imprimindo, tenta casar com um pedido do backend.
    Se não casar, loga warning e deixa o humano resolver.
    """
    job = await printer.get_current_job()
    if job is None or job.state != "printing":
        logger.info("X1 ociosa ou state desconhecido, seguindo loop normal.")
        return

    # Extrai order_id do nome do arquivo
    basename = job.gcode_file.split("/")[-1]
    order_id = basename.replace(".3mf", "").replace(".gcode.3mf", "")
    logger.info("X1 imprimindo arquivo %s → order_id=%s", basename, order_id)
    # Nota: por simplicidade, o agent só loga e segue. O pedido provavelmente
    # já está em IMPRIMINDO ou PREPARANDO no backend e vai receber update final
    # quando a impressão acabar naturalmente.
    logger.warning(
        "Reconciliação não-retomável nesta versão: X1 continuará imprimindo %s, "
        "mas o agent não vai reportar progresso. Aguarde conclusão e verifique "
        "manualmente se o status no admin bate.",
        order_id,
    )


async def main() -> None:
    setup_logging()
    config = load_config()
    logger.info("=" * 50)
    logger.info("FORJA3D Printer Agent")
    logger.info("Backend: %s", config.backend_url)
    logger.info("Impressora: %s", config.printer.ip)
    logger.info("Intervalo de poll: %ss", config.poll_interval)
    logger.info("=" * 50)

    backend = BackendClient(config.backend_url, config.agent_password)
    printer = PrinterClient(
        config.printer.ip, config.printer.serial, config.printer.access_code
    )
    slicer = Slicer(config.bambu_studio_cli)

    try:
        await printer.connect()
        await reconcile_on_startup(backend, printer)

        while True:
            try:
                order = await backend.claim_next_job()
                if order is None:
                    await asyncio.sleep(config.poll_interval)
                    continue

                runner = JobRunner(backend, printer, slicer, config.download_dir)
                result = await runner.run(order)
                logger.info("Job %s terminou: %s", result.order_id, result.status)
            except KeyboardInterrupt:
                logger.info("Agent encerrado pelo usuário.")
                break
            except Exception:
                logger.exception("Erro no loop principal")
                await asyncio.sleep(config.poll_interval)
    finally:
        await printer.disconnect()
        await backend.close()


if __name__ == "__main__":
    asyncio.run(main())
