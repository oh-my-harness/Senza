"""Tests for FinalAnswerValidator Python binding."""

import senza


def test_final_answer_validator_factory_exists():
    """senza.hooks.final_answer_validator should be callable."""
    assert hasattr(senza.hooks, "final_answer_validator")


def test_final_answer_validator_creates_hook():
    """final_answer_validator should return a Hook object."""
    def my_validator(ctx):
        return None

    hook = senza.hooks.final_answer_validator(my_validator)
    assert hook is not None


def test_builder_method_exists():
    """HarnessBuilder should have a final_answer_validator method."""
    assert hasattr(senza.HarnessBuilder, "final_answer_validator")
