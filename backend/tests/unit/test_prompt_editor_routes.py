"""The prompt-editor route table: permissions, removals and path bounds"""

import inspect

import pytest

from app.api.v1.routes.prompt_editor import (
    NodeIdPath,
    NodeTypeQuery,
    PromptFieldPath,
    router,
)
from app.auth.dependencies import auth
from app.core.permissions.constants import Permissions as P

CONTEXT_PATH = "/{workflow_id}/{node_id}/{prompt_field}"


def _route(method: str, path: str):
    return next(r for r in router.routes if r.path == path and method in r.methods)


def _guards(route):
    dependencies = [d.dependency for d in route.dependencies]
    granted = tuple(
        permission
        for dependency in dependencies
        if dependency is not auth
        for permission in inspect.getclosurevars(dependency).nonlocals["permissions"]
    )
    return auth in dependencies, granted


@pytest.mark.parametrize(
    "method,path,expected",
    [
        ("GET", f"/history{CONTEXT_PATH}", (P.Evaluation.READ,)),
        ("GET", f"/versions{CONTEXT_PATH}", (P.Evaluation.READ,)),
        ("POST", f"/versions{CONTEXT_PATH}", (P.Evaluation.UPDATE,)),
        ("DELETE", "/versions/{version_id}", (P.Evaluation.UPDATE,)),
        ("GET", f"/config{CONTEXT_PATH}", (P.Evaluation.READ,)),
        ("PUT", f"/config{CONTEXT_PATH}/gold-suite", (P.Evaluation.UPDATE,)),
        ("POST", f"/evaluate{CONTEXT_PATH}", (P.Evaluation.RUN,)),
        ("POST", f"/optimize{CONTEXT_PATH}", (P.Evaluation.UPDATE,)),
    ],
)
def test_every_route_is_authenticated_and_keeps_its_permission(method, path, expected):
    authenticated, granted = _guards(_route(method, path))

    assert authenticated
    assert granted == expected


def test_the_version_list_survives_one_release_as_deprecated():
    assert _route("GET", f"/versions{CONTEXT_PATH}").deprecated is True


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/versions/{version_id}/restore"),
        ("DELETE", "/versions/{version_id}/hard"),
    ],
)
def test_the_destructive_routes_are_gone(method, path):
    assert (method, path) not in {(m, r.path) for r in router.routes for m in r.methods}


@pytest.mark.parametrize(
    "annotation,max_length", [(NodeIdPath, 100), (PromptFieldPath, 50), (NodeTypeQuery, 100)]
)
def test_ids_are_bounded_at_their_column_widths(annotation, max_length):
    constraints = annotation.__metadata__[0].metadata

    assert any(getattr(c, "max_length", None) == max_length for c in constraints)


def test_the_node_type_hint_is_optional_and_reaches_reads_only():
    history = inspect.signature(_route("GET", f"/history{CONTEXT_PATH}").endpoint)

    assert history.parameters["node_type"].default is None

    for method, path in [
        ("POST", f"/versions{CONTEXT_PATH}"),
        ("PUT", f"/config{CONTEXT_PATH}/gold-suite"),
    ]:
        writer = inspect.signature(_route(method, path).endpoint)

        assert "node_type" not in writer.parameters
