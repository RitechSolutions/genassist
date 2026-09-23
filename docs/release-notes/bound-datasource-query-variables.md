# Bound datasource query variables

Training datasource queries now send workflow variable values to database
drivers separately from SQL text. This prevents values from changing the query
structure and keeps bound values out of database error messages.

## Behavior change

- Variables are supported only in value positions, including `WHERE` and
  `LIMIT`.
- Variables cannot replace table names, selected columns, `GROUP BY` columns,
  or `ORDER BY` columns.
- A variable must represent a complete value. Rewrite patterns such as
  `LIKE '%{{search}}%'` using the database's concatenation syntax.
- PostgreSQL-compatible datasources convert string workflow inputs to inferred
  integer, numeric, Boolean, date, and timestamp types before execution.
- PostgreSQL `time`, `interval`, and array values require an explicit cast
  through text, such as `CAST({{v}} AS text)::time` or
  `CAST({{v}} AS text)::interval`.

## Deployment audit

Before deployment, run this query against each application database and record
the result count. It finds training datasource nodes whose query contains a
workflow variable so their SQL can be reviewed for the behavior changes above.

```sql
SELECT COUNT(DISTINCT workflow.id) AS workflows_to_review
FROM workflows AS workflow
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(workflow.nodes, '[]'::jsonb)) AS node
WHERE node->>'type' = 'trainDataSourceNode'
  AND node->'data'->>'query' LIKE '%{{%}}%';
```

Review matching queries for variables inside quoted text and variables used as
identifiers. Update those queries before enabling the release, then run their
workflow tests against the configured datasource. The count is environment
specific and must be captured by the deployment owner; it is not available from
the source repository.
