"""Cliente da Bambu X1 Carbon via bambulabs-api (MQTT + FTP).

Encapsula a biblioteca bambulabs-api (v2.6+) expondo uma interface
async limpa com callbacks para progresso, conclusão e erro.

Divergências descobertas vs. esboço do plano:
- GcodeState é um enum; valores são RUNNING/FINISHED/FAILED/IDLE/PAUSED
  (não strings "printing"/"finish"/"failed" como o esboço assumia)
- start_print() exige plate_number como 2º argumento obrigatório
- A biblioteca tem upload_file() próprio (FTP interno), mas usamos
  ftplib diretamente para maior controle e independência da lib
"""
from __future__ import annotations

import asyncio
import ftplib
import logging
import os
from dataclasses import dataclass, field
from typing import Callable

import bambulabs_api as bl

logger = logging.getLogger(__name__)


@dataclass
class ProgressEvent:
    percentual: int
    camada_atual: int
    camada_total: int


@dataclass
class CurrentJob:
    gcode_file: str  # nome do arquivo atual na X1
    state: str       # "idle" | "printing" | "paused" | "error"


def _normalize_state(raw_state) -> str:
    """Converte GcodeState (enum) ou string para um dos 4 estados canônicos."""
    # GcodeState é um enum; .name retorna "RUNNING", "FINISHED", etc.
    # Toleramos também strings brutas caso a versão da lib mude.
    if raw_state is None:
        return "idle"
    try:
        name = raw_state.name.upper()  # enum → "RUNNING", "FINISHED" …
    except AttributeError:
        name = str(raw_state).upper()  # fallback para string

    mapping = {
        "IDLE": "idle",
        "UNKNOWN": "idle",
        "PREPARING": "printing",
        "RUNNING": "printing",
        "PAUSED": "paused",
        "FINISHED": "finished",   # valor interno; não exposto via CurrentJob
        "FAILED": "error",
    }
    return mapping.get(name, "idle")


@dataclass
class PrinterClient:
    """Wrapper async sobre bambulabs_api.Printer com polling de estado."""

    ip: str
    serial: str
    access_code: str

    # Atributos internos (não fazem parte da interface pública)
    _printer: bl.Printer | None = field(default=None, init=False, repr=False)
    _progress_cb: Callable[[ProgressEvent], None] | None = field(
        default=None, init=False, repr=False
    )
    _finished_cb: Callable[[], None] | None = field(
        default=None, init=False, repr=False
    )
    _error_cb: Callable[[str], None] | None = field(
        default=None, init=False, repr=False
    )
    _poll_task: asyncio.Task | None = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    # Conexão
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Conecta MQTT à impressora e inicia loop de polling."""
        loop = asyncio.get_event_loop()
        # Assinatura real: Printer(IP, ACCESS_CODE, SERIAL)
        self._printer = bl.Printer(self.ip, self.access_code, self.serial)
        await loop.run_in_executor(None, self._printer.connect)
        logger.info("Conectado à X1 %s (serial=%s)", self.ip, self.serial)
        self._poll_task = asyncio.create_task(self._poll_state())

    async def disconnect(self) -> None:
        """Para o polling e desconecta MQTT."""
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._printer is not None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._printer.disconnect)
            self._printer = None
            logger.info("Desconectado da X1 %s", self.ip)

    # ------------------------------------------------------------------
    # Polling interno
    # ------------------------------------------------------------------

    async def _poll_state(self) -> None:
        """Loop de polling que dispara callbacks quando o estado muda.

        Intervalo: 2 segundos.  Roda até disconnect() cancelar a task.
        """
        last_pct: int = -1
        last_raw_state: str | None = None

        while self._printer is not None:
            try:
                # Getters síncronos — executados fora da event loop
                loop = asyncio.get_event_loop()

                raw_pct, raw_layer, raw_total, raw_state = await loop.run_in_executor(
                    None, self._snapshot
                )

                pct = int(raw_pct) if raw_pct is not None else 0
                layer = int(raw_layer) if raw_layer is not None else 0
                total = int(raw_total) if raw_total is not None else 0
                state_name = _normalize_state(raw_state)

                # Progresso mudou?
                if pct != last_pct and self._progress_cb is not None:
                    self._progress_cb(ProgressEvent(pct, layer, total))
                    last_pct = pct

                # Transição para FINISHED?
                if (
                    last_raw_state != "finished"
                    and state_name == "finished"
                    and self._finished_cb is not None
                ):
                    self._finished_cb()

                # Transição para FAILED/error?
                if (
                    last_raw_state != "error"
                    and state_name == "error"
                    and self._error_cb is not None
                ):
                    err_code = 0
                    try:
                        err_code = self._printer.print_error_code() or 0
                    except Exception:
                        pass
                    msg = f"Impressão falhou (código de erro: {err_code})"
                    self._error_cb(msg)

                last_raw_state = state_name

            except asyncio.CancelledError:
                raise  # deixa a task ser cancelada normalmente
            except Exception as exc:
                logger.debug("Erro no polling de estado MQTT: %s", exc)

            await asyncio.sleep(2)

    def _snapshot(self):
        """Lê os getters síncronos da impressora de uma vez (thread seguro)."""
        p = self._printer
        if p is None:
            return (None, None, None, None)
        pct = p.get_percentage()
        layer = p.current_layer_num()
        total = p.total_layer_num()
        state = p.get_state()
        return (pct, layer, total, state)

    # ------------------------------------------------------------------
    # Upload de arquivo (FTP independente da lib)
    # ------------------------------------------------------------------

    async def upload_file(self, local_path: str) -> str:
        """Upload do arquivo via FTPS (porta 990, TLS implícito).

        A X1 Carbon expõe FTP na porta 990 com TLS implícito.
        Usuário: bblp  |  Senha: access_code  |  Destino: /sdcard/<filename>

        Retorna o nome remoto do arquivo (sem caminho completo).
        """
        filename = os.path.basename(local_path)
        loop = asyncio.get_event_loop()

        def _ftp_upload() -> None:
            ftp = ftplib.FTP_TLS()
            ftp.connect(self.ip, 990, timeout=60)
            ftp.login("bblp", self.access_code)
            ftp.prot_p()          # canal de dados protegido
            ftp.set_pasv(True)
            with open(local_path, "rb") as fh:
                ftp.storbinary(f"STOR /sdcard/{filename}", fh)
            ftp.quit()

        await loop.run_in_executor(None, _ftp_upload)
        logger.info("Upload concluído: %s → /sdcard/%s", local_path, filename)
        return filename

    # ------------------------------------------------------------------
    # Iniciar impressão
    # ------------------------------------------------------------------

    async def start_print(self, remote_filename: str) -> None:
        """Envia comando MQTT para iniciar impressão do arquivo já na SD card.

        A API real exige plate_number como 2º argumento.
        Para arquivos .3mf fatiados pelo BambuStudio CLI usamos plate_number=1.
        use_ams=False porque o projeto usa apenas o tray externo (vt_tray).
        """
        if self._printer is None:
            raise RuntimeError("PrinterClient não está conectado")

        loop = asyncio.get_event_loop()

        def _start() -> bool:
            return self._printer.start_print(  # type: ignore[union-attr]
                remote_filename,
                plate_number=1,
                use_ams=False,
            )

        result = await loop.run_in_executor(None, _start)
        if not result:
            raise RuntimeError(f"start_print retornou False para '{remote_filename}'")
        logger.info("Comando start_print enviado: %s", remote_filename)

    # ------------------------------------------------------------------
    # Estado atual (para reconciliação no startup)
    # ------------------------------------------------------------------

    async def get_current_job(self) -> CurrentJob | None:
        """Retorna estado atual da impressora ou None se não conectado."""
        if self._printer is None:
            return None
        try:
            loop = asyncio.get_event_loop()

            def _read_job():
                p = self._printer
                if p is None:
                    return None, None
                raw_state = p.get_state()
                gcode_file = p.get_file_name() or ""
                return raw_state, gcode_file

            raw_state, gcode_file = await loop.run_in_executor(None, _read_job)
            state = _normalize_state(raw_state)

            # Mapeia "finished" → "idle" para estado canônico de CurrentJob
            # (a impressora já terminou; do ponto de vista do agent, está livre)
            canonical = state if state in ("idle", "printing", "paused", "error") else "idle"

            return CurrentJob(gcode_file=str(gcode_file), state=canonical)

        except Exception as exc:
            logger.warning("get_current_job falhou: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Registro de callbacks
    # ------------------------------------------------------------------

    def on_progress(self, cb: Callable[[ProgressEvent], None]) -> None:
        """Registra callback para eventos de progresso."""
        self._progress_cb = cb

    def on_finished(self, cb: Callable[[], None]) -> None:
        """Registra callback para evento de conclusão."""
        self._finished_cb = cb

    def on_error(self, cb: Callable[[str], None]) -> None:
        """Registra callback para evento de erro (string = mensagem)."""
        self._error_cb = cb
