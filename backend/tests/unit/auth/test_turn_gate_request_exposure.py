"""Unit test: the auth dependency exposes the request to the chat turn gate"""

from types import SimpleNamespace

from starlette_context import context, request_cycle_context

from app.auth.dependencies import expose_request_to_turn_gate


def test_request_is_stored_under_the_key_the_turn_gate_reads():
    request = SimpleNamespace()

    with request_cycle_context({}):
        expose_request_to_turn_gate(request)

        assert context["http_request"] is request
