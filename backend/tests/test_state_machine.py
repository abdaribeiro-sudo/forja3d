import pytest

from models.state_machine import (
    ALLOWED_TRANSITIONS,
    TransitionError,
    assert_allowed,
)


def test_pago_to_preparando_is_allowed():
    assert_allowed("PAGO", "PREPARANDO")


def test_preparando_to_imprimindo_is_allowed():
    assert_allowed("PREPARANDO", "IMPRIMINDO")


def test_imprimindo_to_impresso_is_allowed():
    assert_allowed("IMPRIMINDO", "IMPRESSO")


def test_preparando_to_erro_is_allowed():
    assert_allowed("PREPARANDO", "ERRO_IMPRESSAO")


def test_imprimindo_to_erro_is_allowed():
    assert_allowed("IMPRIMINDO", "ERRO_IMPRESSAO")


def test_erro_to_pago_is_allowed():
    """Requeue path."""
    assert_allowed("ERRO_IMPRESSAO", "PAGO")


def test_pago_to_imprimindo_is_not_allowed():
    with pytest.raises(TransitionError):
        assert_allowed("PAGO", "IMPRIMINDO")


def test_impresso_to_imprimindo_is_not_allowed():
    with pytest.raises(TransitionError):
        assert_allowed("IMPRESSO", "IMPRIMINDO")


def test_any_to_entregue_not_in_agent_machine():
    with pytest.raises(TransitionError):
        assert_allowed("IMPRESSO", "ENTREGUE")  # só via admin manual


def test_transitions_dict_contains_entry_for_each_active_state():
    for state in ["PAGO", "PREPARANDO", "IMPRIMINDO", "ERRO_IMPRESSAO"]:
        assert state in ALLOWED_TRANSITIONS
