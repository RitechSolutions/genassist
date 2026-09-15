"""Unit tests for the AST-based read-only SQL policy.

Matrix and dialect behavior come from the sqlglot 26.33.0 spike. Tests do not
execute SQL against a database.
"""

from unittest.mock import patch

import pytest

from app.modules.integration.database.query_validator import validate_with_sqlglot
from app.modules.integration.database.read_only_sql import (
    SQLGLOT_DIALECTS,
    validate_read_only_sql,
)

ALL_DB_TYPES = tuple(SQLGLOT_DIALECTS.keys())


def _assert_valid(result) -> None:
    assert result.is_valid is True
    assert result.error_message is None


def _assert_invalid(result, *fragments: str) -> None:
    assert result.is_valid is False
    assert result.error_message
    message = result.error_message.lower()
    for fragment in fragments:
        assert fragment.lower() in message, result.error_message


@pytest.mark.parametrize("db_type", ALL_DB_TYPES)
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "SELECT 1;",
        "/* comment */ SELECT 1",
        "SELECT id, name FROM users WHERE active = 1",
        "SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id",
        "SELECT * FROM (SELECT id FROM users) t",
        "WITH c AS (SELECT id FROM users) SELECT * FROM c",
        """
        WITH a AS (SELECT id FROM users),
             b AS (SELECT id FROM a)
        SELECT * FROM b
        """,
        "SELECT 1 UNION SELECT 2",
        "SELECT 1 UNION ALL SELECT 2",
        "SELECT dept, COUNT(*) FROM emp GROUP BY dept HAVING COUNT(*) > 1",
        "SELECT id, ROW_NUMBER() OVER (ORDER BY id) FROM users",
        "SELECT * FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.id = t.id)",
        "SELECT * FROM t WHERE id IN (SELECT id FROM u)",
        "SELECT * FROM users LIMIT 10 OFFSET 5",
        "SELECT public.users.id FROM public.users",
        "SELECT 'INSERT INTO users VALUES (1)'",
        "SELECT 'DELETE FROM users'",
        "SELECT REPLACE(name, 'a', 'b') FROM users",
        "(SELECT 1)",
    ],
)
def test_valid_read_only_queries(db_type, sql):
    _assert_valid(validate_read_only_sql(sql, db_type))


@pytest.mark.parametrize(
    "sql, db_type",
    [
        ("SELECT TOP 10 * FROM users", "mssql"),
        (
            "SELECT * FROM users QUALIFY ROW_NUMBER() OVER (ORDER BY id) = 1",
            "snowflake",
        ),
        ("SELECT 1;;", "postgresql"),
    ],
)
def test_valid_dialect_specific_read_only_queries(sql, db_type):
    _assert_valid(validate_read_only_sql(sql, db_type))


@pytest.mark.parametrize("db_type", ALL_DB_TYPES)
@pytest.mark.parametrize(
    "sql, fragment",
    [
        ("INSERT INTO users(id) VALUES (1)", "Insert"),
        ("INSERT INTO users SELECT * FROM other_users", "Insert"),
        ("UPDATE users SET active = 0", "Update"),
        ("DELETE FROM users", "Delete"),
        (
            "MERGE INTO target USING source ON target.id = source.id WHEN MATCHED THEN UPDATE SET target.x = source.x",
            "Merge",
        ),
        ("CREATE TABLE test(id INT)", "Create"),
        ("CREATE TABLE t AS SELECT 1", "Create"),
        ("DROP TABLE users", "Drop"),
        ("TRUNCATE TABLE users", "TruncateTable"),
        ("GRANT SELECT ON users TO some_role", "Grant"),
        ("SELECT 1; SELECT 2", "Multiple SQL statements"),
        ("SELECT 1; DROP TABLE users", "Multiple SQL statements"),
        ("COMMIT", "Commit"),
        ("ROLLBACK", "Rollback"),
        ("SET x = 1", "Set"),
        ("DESCRIBE users", "Describe"),
    ],
)
def test_invalid_queries_all_dialects(db_type, sql, fragment):
    _assert_invalid(validate_read_only_sql(sql, db_type), fragment)


@pytest.mark.parametrize("db_type", ["postgresql", "mysql", "sqlite", "snowflake"])
def test_alter_table_rejected(db_type):
    result = validate_read_only_sql("ALTER TABLE users ADD COLUMN x INT", db_type)
    _assert_invalid(result, "Alter")


def test_alter_table_mssql_is_command():
    result = validate_read_only_sql("ALTER TABLE users ADD COLUMN x INT", "mssql")
    _assert_invalid(result, "Command")


@pytest.mark.parametrize(
    "sql, db_type, fragment",
    [
        (
            """
            WITH deleted AS (
                DELETE FROM users
                RETURNING *
            )
            SELECT * FROM deleted
            """,
            "postgresql",
            "Delete",
        ),
        (
            "WITH c AS (SELECT 1 AS id) INSERT INTO users SELECT * FROM c",
            "postgresql",
            "Insert",
        ),
        ("SELECT * INTO new_users FROM users", "postgresql", "SELECT INTO"),
        ("SELECT * INTO new_users FROM users", "mssql", "SELECT INTO"),
        ("SELECT id INTO @x FROM users LIMIT 1", "mysql", "SELECT INTO"),
        ("SELECT * FROM users FOR UPDATE", "postgresql", "Row-locking"),
        ("SELECT * FROM users FOR UPDATE", "mysql", "Row-locking"),
        ("SELECT * FROM users FOR UPDATE", "sqlite", "Row-locking"),
        ("SELECT * FROM users FOR UPDATE", "snowflake", "Row-locking"),
        ("SELECT * FROM users FOR UPDATE", "mssql", "could not be safely parsed"),
        ("SELECT * FROM users FOR SHARE", "postgresql", "Row-locking"),
        ("COPY users TO '/tmp/users.csv'", "postgresql", "Copy"),
        ("REFRESH MATERIALIZED VIEW mv_users", "postgresql", "Command"),
        ("REPLACE INTO users(id) VALUES (1)", "mysql", "Command"),
        ("LOAD DATA INFILE '/tmp/users.csv' INTO TABLE users", "mysql", "could not be safely parsed"),
        (
            "LOAD DATA INPATH '/tmp/users.csv' INTO TABLE users",
            "mysql",
            "LoadData",
        ),
        ("EXEC sp_help", "mssql", "Command"),
        ("EXECUTE sp_help", "mssql", "Command"),
        ("PRAGMA table_info(users)", "sqlite", "Pragma"),
        ("ATTACH DATABASE 'other.db' AS other", "sqlite", "could not be safely parsed"),
        ("DETACH DATABASE other", "sqlite", "could not be safely parsed"),
        ("DETACH other", "sqlite", "Alias"),
        ("VACUUM", "sqlite", "Command"),
        ("COPY INTO target_table FROM @my_stage", "snowflake", "Copy"),
        ("CALL my_procedure()", "snowflake", "Command"),
        ("USE WAREHOUSE my_wh", "snowflake", "Use"),
        ("USE mydb", "mysql", "Use"),
        ("ALTER SESSION SET QUERY_TAG = 'test'", "snowflake", "Command"),
        ("REVOKE SELECT ON users FROM some_role", "postgresql", "Command"),
        ("REVOKE SELECT ON users FROM some_role", "mysql", "could not be safely parsed"),
        ("REVOKE SELECT ON users FROM some_role", "mssql", "could not be safely parsed"),
        ("REVOKE SELECT ON users FROM some_role", "sqlite", "could not be safely parsed"),
        ("REVOKE SELECT ON users FROM some_role", "snowflake", "could not be safely parsed"),
        ("BEGIN", "mysql", "Transaction"),
        ("BEGIN", "sqlite", "Transaction"),
        ("BEGIN", "snowflake", "Transaction"),
        ("BEGIN", "postgresql", "Command"),
        ("BEGIN", "mssql", "Command"),
        ("EXPLAIN SELECT * FROM users", "mysql", "Describe"),
        ("EXPLAIN SELECT * FROM users", "postgresql", "Command"),
        ("EXPLAIN SELECT * FROM users", "mssql", "Command"),
        ("EXPLAIN SELECT * FROM users", "sqlite", "Command"),
        ("EXPLAIN SELECT * FROM users", "snowflake", "Command"),
        ("SHOW TABLES", "mysql", "Show"),
        ("SHOW TABLES", "snowflake", "Show"),
        ("SHOW TABLES", "postgresql", "Command"),
        ("SHOW TABLES", "mssql", "Command"),
        ("SHOW TABLES", "sqlite", "Command"),
        ("COMMENT ON TABLE users IS 'x'", "postgresql", "Comment"),
        ("VALUES (1), (2)", "postgresql", "Values"),
    ],
)
def test_invalid_dialect_specific_queries(sql, db_type, fragment):
    _assert_invalid(validate_read_only_sql(sql, db_type), fragment)


@pytest.mark.parametrize(
    "query",
    [None, "", "   ", "\n\t", 123, ["SELECT 1"]],
)
def test_empty_or_non_string_query_rejected(query):
    _assert_invalid(validate_read_only_sql(query, "postgresql"), "empty")


@pytest.mark.parametrize("db_type", [None, "", "   ", "oracle", "postgres", "tsql", 1])
def test_unsupported_db_type_rejected(db_type):
    result = validate_read_only_sql("SELECT 1", db_type)
    _assert_invalid(result, "Unsupported database type")


def test_malformed_sql_rejected():
    result = validate_read_only_sql("SELCT 1 FROM", "postgresql")
    _assert_invalid(result, "could not be safely parsed")
    assert result.error_message == "SQL query could not be safely parsed."


def test_unexpected_parser_exception_fails_closed():
    with patch(
        "app.modules.integration.database.read_only_sql.sqlglot.parse",
        side_effect=RuntimeError("boom"),
    ):
        result = validate_read_only_sql("SELECT 1", "postgresql")
    _assert_invalid(result, "could not be safely parsed")
    assert result.error_message == "SQL query could not be safely parsed."


def test_select_into_rejected_with_specific_message_and_query_type():
    result = validate_read_only_sql("SELECT * INTO new_users FROM users", "postgresql")
    assert result.is_valid is False
    assert result.error_message == "SELECT INTO is not allowed in read-only SQL."
    assert result.query_type == "Select"
    assert result.warnings is None
    assert result.tables_used is None
    assert result.columns_used is None


def test_locking_select_rejected_with_specific_message_and_query_type():
    result = validate_read_only_sql("SELECT * FROM users FOR UPDATE", "postgresql")
    assert result.is_valid is False
    assert result.error_message == "Row-locking SELECT statements are not allowed."
    assert result.query_type == "Select"
    assert result.warnings is None
    assert result.tables_used is None
    assert result.columns_used is None


def test_valid_select_sets_query_type_without_mutating_other_fields():
    result = validate_read_only_sql("SELECT 1", "postgresql")
    _assert_valid(result)
    assert result.query_type == "Select"
    assert result.warnings is None
    assert result.tables_used is None
    assert result.columns_used is None


def test_sql_alias_maps_to_mysql():
    _assert_valid(validate_read_only_sql("SELECT 1", "sql"))


def test_db_type_is_case_insensitive():
    _assert_valid(validate_read_only_sql("SELECT 1", "PostgreSQL"))


@pytest.mark.parametrize("db_type", ["timescaledb", "timedb"])
def test_postgres_compatible_training_datasources_are_supported(db_type):
    _assert_valid(validate_read_only_sql("SELECT 1", db_type))


@pytest.mark.parametrize("db_type", ["timescaledb", "timedb"])
def test_existing_sqlglot_validator_supports_training_datasource_aliases(db_type):
    _assert_valid(validate_with_sqlglot("SELECT 1", {"tables": []}, db_type))


def test_identifier_parameter_is_rejected_clearly():
    result = validate_read_only_sql(
        "SELECT * FROM :wf_0_table",
        "postgresql",
    )

    _assert_invalid(result, "parameters", "table names")


def test_value_parameter_remains_valid():
    _assert_valid(
        validate_read_only_sql(
            "SELECT * FROM lots WHERE city = :wf_0_city",
            "postgresql",
        )
    )


MYSQL_MAPPED_DB_TYPES = ("mysql", "sql")

MYSQL_EXECUTABLE_COMMENT_QUERIES = [
    "/*! SELECT 1 */",
    "/*!50000 SELECT 1 */",
    "SELECT 1 /*!50000 INTO OUTFILE '/tmp/x' */",
    "SELECT *\nFROM users\n/*!50000 INTO OUTFILE '/tmp/x' */",
    "SELECT 1 /*! DELETE FROM users */",
    "SELECT 1\n/*!50000 INTO OUTFILE '/tmp/x' */",
    "SELECT 1/*!50000 INTO OUTFILE '/tmp/x'*/",
    "  /*!50000 SELECT 1 */  ",
]


@pytest.mark.parametrize("db_type", MYSQL_MAPPED_DB_TYPES)
@pytest.mark.parametrize("sql", MYSQL_EXECUTABLE_COMMENT_QUERIES)
def test_mysql_executable_comments_rejected(db_type, sql):
    _assert_invalid(validate_read_only_sql(sql, db_type), "executable comment")


@pytest.mark.parametrize("db_type", MYSQL_MAPPED_DB_TYPES)
@pytest.mark.parametrize(
    "sql",
    [
        "/* ordinary comment */\nSELECT 1",
        "SELECT 1 /* ordinary comment */",
        "-- ordinary comment\nSELECT 1",
        "SELECT '/*!50000 DELETE FROM users */'",
        "SELECT 'text '' /*! not executable */'",
        'SELECT "/*!50000 DELETE FROM users */"',
        "SELECT `/*!weird*/`",
        "SELECT /* ! not an executable comment */ 1",
        "SELECT 1 # /*! not executable",
        "SELECT 1 # /*! not executable\r",
    ],
)
def test_mysql_ordinary_comments_and_literal_markers_remain_valid(db_type, sql):
    _assert_valid(validate_read_only_sql(sql, db_type))


def test_mysql_executable_comment_after_crlf_line_comment_is_still_detected():
    _assert_invalid(
        validate_read_only_sql(
            "SELECT 1 # ignored\r\nSELECT 2 /*! UNION SELECT 3 */",
            "mysql",
        ),
        "executable comment",
    )


@pytest.mark.parametrize("db_type", ["postgresql", "sqlite"])
def test_mysql_executable_comment_guard_is_not_applied_to_other_dialects(db_type):
    # PostgreSQL/SQLite treat /*! ... */ as an ordinary block comment; the
    # lexical guard must stay MySQL-mapping-only so this remains a Select.
    _assert_valid(validate_read_only_sql("SELECT 1 /*!50000 INTO OUTFILE '/tmp/x' */", db_type))


def test_blocked_message_uses_policy_reason():
    from app.modules.integration.database.read_only_sql import read_only_sql_blocked_message

    validation = validate_read_only_sql("DELETE FROM users", "postgresql")
    message = read_only_sql_blocked_message(validation)
    assert message.startswith("SQL execution blocked: ")
    assert validation.error_message in message


def test_blocked_message_uses_centralized_fallback_when_reason_missing():
    from app.modules.integration.database.read_only_sql import (
        READ_ONLY_SQL_FALLBACK_REASON,
        read_only_sql_blocked_message,
    )
    from app.modules.integration.database.validation_result import ValidationResult

    message = read_only_sql_blocked_message(ValidationResult(False))
    assert message == f"SQL execution blocked: {READ_ONLY_SQL_FALLBACK_REASON}"
    assert "Only read-only queries are permitted." in message
