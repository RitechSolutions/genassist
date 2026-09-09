"""SQLGlot parser/AST assumptions the TDS-2 read-only policy depends on.

These tests inspect installed SQLGlot behavior, not the policy outcome. If an
upgrade changes a root class, executable-comment AST, REPLACE representation,
or INTO/lock shape, they should fail so the allowlists get an explicit review.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from app.modules.integration.database.read_only_sql import (
    _ALLOWED_ROOTS,
    _FORBIDDEN_NODES,
    SQLGLOT_DIALECTS,
)

# Direct exp.Query subclasses observed in the SQLGlot version the policy was
# written against. A new subclass must not be treated as automatically allowed.
_KNOWN_QUERY_SUBCLASSES = frozenset({"SetOperation", "Select", "Subquery"})
_KNOWN_SET_OPERATION_SUBCLASSES = frozenset({"Union", "Except", "Intersect"})

_EXECUTABLE_AST_TYPES = (
    exp.Union,
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Command,
    exp.Into,
    exp.Lock,
)


def _mysql_dialect() -> str:
    return SQLGLOT_DIALECTS["mysql"]


def _parse_one(sql: str, dialect: str) -> exp.Expression:
    parsed = [stmt for stmt in sqlglot.parse(sql, dialect=dialect) if stmt is not None]
    assert parsed, (
        f"SQLGlot {sqlglot.__version__} produced no statement for {sql!r} dialect={dialect!r}"
    )
    assert len(parsed) == 1, parsed
    return parsed[0]


def _walk_types(root: exp.Expression) -> set[type]:
    return {type(node) for node in root.walk()}


def test_sqlglot_query_subtypes_match_the_explicit_allowlist():
    assert hasattr(exp, "Query")
    query_subclasses = {cls.__name__ for cls in exp.Query.__subclasses__()}
    assert query_subclasses == _KNOWN_QUERY_SUBCLASSES, (
        f"SQLGlot {sqlglot.__version__} Query subclasses changed: {sorted(query_subclasses)}. "
        "Review _ALLOWED_ROOTS before allowing new query forms."
    )
    setop_subclasses = {cls.__name__ for cls in exp.SetOperation.__subclasses__()}
    assert setop_subclasses == _KNOWN_SET_OPERATION_SUBCLASSES, (
        f"SQLGlot {sqlglot.__version__} SetOperation subclasses changed: {sorted(setop_subclasses)}. "
        "Review _ALLOWED_ROOTS before allowing new set operations."
    )
    assert _ALLOWED_ROOTS == (
        exp.Select,
        exp.Union,
        exp.Except,
        exp.Intersect,
        exp.Subquery,
    )


def test_sqlglot_supported_read_only_forms_parse_to_allowlisted_roots():
    cases = (
        ("SELECT 1", "postgres", exp.Select),
        ("SELECT 1 UNION SELECT 2", "postgres", exp.Union),
        ("SELECT 1 EXCEPT SELECT 2", "postgres", exp.Except),
        ("SELECT 1 INTERSECT SELECT 2", "postgres", exp.Intersect),
        ("(SELECT 1)", "postgres", exp.Subquery),
    )
    for sql, dialect, expected_root in cases:
        root = _parse_one(sql, dialect)
        assert type(root) is expected_root, (
            f"SQLGlot {sqlglot.__version__} parsed {sql!r} as {type(root).__name__}, "
            f"expected {expected_root.__name__}"
        )
        assert isinstance(root, _ALLOWED_ROOTS)


def test_sqlglot_mysql_executable_comment_body_is_not_exposed_as_executable_ast():
    """The /*! ... */ body is comment metadata, not Union/DML nodes.

    That is why the policy scans the raw SQL instead of trusting AST walks.
    """
    sql = "SELECT 1 /*! UNION SELECT 2 */"
    root = _parse_one(sql, _mysql_dialect())
    assert type(root) is exp.Select
    assert not any(isinstance(node, _EXECUTABLE_AST_TYPES) for node in root.walk()), (
        f"SQLGlot {sqlglot.__version__} exposed executable-comment body as AST in {sql!r}: "
        f"{sorted(t.__name__ for t in _walk_types(root))}"
    )
    comment_blobs = [
        comment
        for node in root.walk()
        for comment in (getattr(node, "comments", None) or [])
    ]
    assert any("UNION SELECT 2" in comment for comment in comment_blobs), comment_blobs


def test_sqlglot_whole_query_mysql_executable_comment_has_no_statement():
    parsed = sqlglot.parse("/*! SELECT 1 */", dialect=_mysql_dialect())
    assert parsed == [None], (
        f"SQLGlot {sqlglot.__version__} unexpectedly parsed a whole-query "
        f"MySQL executable comment as {parsed!r}"
    )


def test_sqlglot_replace_function_is_not_the_same_node_as_replace_into():
    function_root = _parse_one("SELECT REPLACE(name, 'a', 'b') FROM users", _mysql_dialect())
    replaces = [node for node in function_root.walk() if isinstance(node, exp.Replace)]
    assert type(function_root) is exp.Select
    assert len(replaces) == 1
    assert isinstance(replaces[0], exp.Func)
    assert not isinstance(replaces[0], (exp.Insert, exp.Command))
    assert exp.Replace not in _FORBIDDEN_NODES

    into_root = _parse_one("REPLACE INTO users(id) VALUES (1)", _mysql_dialect())
    assert type(into_root) is exp.Command, (
        f"SQLGlot {sqlglot.__version__} parsed REPLACE INTO as {type(into_root).__name__}, "
        "not Command; do not forbid exp.Replace (the string function) as a substitute."
    )
    assert not any(isinstance(node, exp.Replace) for node in into_root.walk())
    assert exp.Command in _FORBIDDEN_NODES


def test_sqlglot_select_into_is_both_into_node_and_select_arg():
    sql = "SELECT * INTO new_users FROM users"
    root = _parse_one(sql, "postgres")
    assert type(root) is exp.Select
    into_nodes = [node for node in root.walk() if isinstance(node, exp.Into)]
    assert len(into_nodes) == 1, (
        f"SQLGlot {sqlglot.__version__} INTO representation changed for {sql!r}: {into_nodes!r}"
    )
    assert root.args.get("into") is into_nodes[0]


def test_sqlglot_select_lock_is_both_lock_node_and_select_arg():
    sql = "SELECT * FROM users FOR UPDATE"
    root = _parse_one(sql, "postgres")
    assert type(root) is exp.Select
    lock_nodes = [node for node in root.walk() if isinstance(node, exp.Lock)]
    assert len(lock_nodes) == 1, (
        f"SQLGlot {sqlglot.__version__} lock representation changed for {sql!r}: {lock_nodes!r}"
    )
    locks_arg = root.args.get("locks")
    assert locks_arg == lock_nodes
