"""Unit tests for tenant-context and background-task scoping primitives.

Covers the fail-closed accessor (`require_tenant_context`) and the context-local
background-task marker (`background_task_context` / `is_background_task`) added in
place of the mutable `settings.BACKGROUND_TASK` global.

Each case runs inside a fresh `contextvars.Context()` so the "never set" path is
genuine and tests stay order-independent.
"""

import contextvars

import pytest

from app.core.tenant_scope import (
    TenantContextError,
    background_task_context,
    clear_tenant_context,
    get_tenant_context,
    is_background_task,
    require_tenant_context,
    set_tenant_context,
)


def _in_fresh_context(fn):
    """Run `fn` in a pristine context where the tenant ContextVar is unset."""
    return contextvars.Context().run(fn)


# ───────────── require_tenant_context (fail-closed) ─────────────

def test_require_raises_when_context_never_set():
    def body():
        with pytest.raises(TenantContextError):
            require_tenant_context()

    _in_fresh_context(body)


def test_require_raises_when_context_is_none():
    def body():
        set_tenant_context(None)  # explicit None must still fail closed
        with pytest.raises(TenantContextError):
            require_tenant_context()

    _in_fresh_context(body)


def test_require_returns_tenant_slug_when_set():
    def body():
        set_tenant_context("acme")
        assert require_tenant_context() == "acme"

    _in_fresh_context(body)


def test_require_accepts_explicit_master_via_clear():
    def body():
        # clear_tenant_context() sets the value to "master" — an explicit,
        # intentional master target, so require_tenant_context must NOT raise.
        clear_tenant_context()
        assert require_tenant_context() == "master"

    _in_fresh_context(body)


def test_require_accepts_explicit_master_via_set():
    def body():
        set_tenant_context("master")
        assert require_tenant_context() == "master"

    _in_fresh_context(body)


# ───────────── get_tenant_context (lenient) ─────────────

def test_get_is_lenient_when_unset():
    def body():
        assert get_tenant_context() == "master"

    _in_fresh_context(body)


def test_get_returns_set_value():
    def body():
        set_tenant_context("acme")
        assert get_tenant_context() == "acme"

    _in_fresh_context(body)


# ───────────── background_task_context ─────────────

def test_background_defaults_false():
    def body():
        assert is_background_task() is False

    _in_fresh_context(body)


def test_background_context_sets_and_restores():
    def body():
        assert is_background_task() is False
        with background_task_context():
            assert is_background_task() is True
        assert is_background_task() is False

    _in_fresh_context(body)


def test_background_context_nested_restores_to_outer():
    def body():
        with background_task_context():
            assert is_background_task() is True
            with background_task_context():
                assert is_background_task() is True
            # inner exit must not clear the still-active outer scope
            assert is_background_task() is True
        assert is_background_task() is False

    _in_fresh_context(body)


def test_background_context_restores_on_exception():
    def body():
        assert is_background_task() is False
        raised = False
        try:
            with background_task_context():
                assert is_background_task() is True
                raise RuntimeError("boom")
        except RuntimeError:
            raised = True
        # exception must propagate out of the context manager...
        assert raised is True
        # ...and the flag must still be restored on the way out
        assert is_background_task() is False

    _in_fresh_context(body)
