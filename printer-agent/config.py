"""Carrega e valida config.json do printer-agent."""
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PrinterConfig:
    ip: str
    serial: str
    access_code: str


@dataclass
class AgentConfig:
    printer: PrinterConfig
    backend_url: str
    agent_password: str
    poll_interval: int
    bambu_studio_cli: str
    download_dir: Path


def load_config(path: str | None = None) -> AgentConfig:
    path = path or os.path.join(os.path.dirname(__file__), "config.json")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    required_top = ["printer", "backend_url", "agent_password", "bambu_studio_cli"]
    for k in required_top:
        if not raw.get(k):
            raise ValueError(f"config.json: campo obrigatório ausente: {k}")

    required_printer = ["ip", "serial", "access_code"]
    for k in required_printer:
        if not raw["printer"].get(k):
            raise ValueError(f"config.json: printer.{k} obrigatório")

    cli = raw["bambu_studio_cli"]
    if not os.path.isfile(cli):
        raise FileNotFoundError(
            f"BambuStudio CLI não encontrado em: {cli}. "
            f"Configure o caminho correto em config.json ou instale o Bambu Studio."
        )

    download_dir = Path(os.path.dirname(__file__)) / "downloads"
    download_dir.mkdir(exist_ok=True)

    return AgentConfig(
        printer=PrinterConfig(**raw["printer"]),
        backend_url=raw["backend_url"].rstrip("/"),
        agent_password=raw["agent_password"],
        poll_interval=int(raw.get("poll_interval_seconds", 30)),
        bambu_studio_cli=cli,
        download_dir=download_dir,
    )
