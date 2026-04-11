"""Regras de transição de estado para pedidos.

Só valida as transições automáticas (agent + requeue).
Admin tem override manual via endpoint genérico que não passa por aqui.
"""


class TransitionError(Exception):
    """Transição não permitida."""


# key = estado atual, value = set de estados destino permitidos
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "PAGO": {"PREPARANDO"},
    "PREPARANDO": {"IMPRIMINDO", "ERRO_IMPRESSAO"},
    "IMPRIMINDO": {"IMPRESSO", "ERRO_IMPRESSAO"},
    "ERRO_IMPRESSAO": {"PAGO"},  # só via requeue admin
}


def assert_allowed(from_status: str, to_status: str) -> None:
    """Levanta TransitionError se a transição não for permitida."""
    allowed = ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise TransitionError(
            f"Transição ilegal: {from_status} → {to_status}. "
            f"Permitido de {from_status}: {sorted(allowed) or 'nenhum'}"
        )
