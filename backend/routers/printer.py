import os

from fastapi import APIRouter, Header, HTTPException, status

router = APIRouter(tags=["printer"], prefix="/printer")

AGENT_PASSWORD = os.getenv("AGENT_PASSWORD", "dev_agent_password")


def verify_agent(agent_password: str) -> None:
    """Valida senha do agent; levanta HTTP 401 se inválida."""
    if agent_password != AGENT_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autorizado (agent)",
        )
