"""Helpers de configuração via variáveis de ambiente."""
import os


def require_password(env_name: str) -> str:
    """Lê uma senha obrigatória do ambiente.

    Levanta RuntimeError se a variável não estiver definida ou estiver vazia.
    Evita que a aplicação suba com uma senha default fraca/pública quando o
    deploy esquecer de configurar a env.
    """
    value = os.getenv(env_name)
    if value is None or not value.strip():
        raise RuntimeError(
            f"Variável de ambiente obrigatória '{env_name}' não definida. "
            "Configure-a antes de iniciar a aplicação."
        )
    return value
