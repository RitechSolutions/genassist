import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, Optional

from langchain.schema import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel

from .database_manager import DatabaseManager
from .query_validator import validate_with_sqlglot

logger = logging.getLogger(__name__)



# ==============================================================
#  MAIN FUNCTION
# ==============================================================

async def translate_to_query(
    db_manager: DatabaseManager,
    llm_model: BaseChatModel,
    natural_language_query: str,
    system_prompt: Optional[str] = None,
    **_: Any
) -> Dict[str, Any]:
    """
    Schema-strict text-to-SQL translator that converts natural language
    queries into valid SQL using database schema and LLM.
    """
    logger.info(f"Starting text-to-SQL translation: {natural_language_query}")

    # Load schema (DatabaseManager handles caching internally)
    try:
        schema = await asyncio.wait_for(db_manager.get_schema(), timeout=30)
        logger.info("Schema loaded")
    except asyncio.TimeoutError:
        raise TimeoutError("Schema loading timed out (30s limit).")
    except Exception as e:
        raise Exception(f"Failed to load schema: {e}")

    # Build strict LLM prompt
    logger.info(f"Using system_prompt: {system_prompt is not None}")
    prompt = _build_prompt(schema, system_prompt)

    # Ask the model
    try:
        response = await asyncio.wait_for(
            llm_model.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content=natural_language_query)
            ]),
            timeout=60
        )
        raw_output = getattr(response, "content", str(response)).strip()
    except asyncio.TimeoutError:
        raise TimeoutError("Model translation timed out (60s).")
    except Exception as e:
        raise Exception(f"Model translation failed: {e}")

    # Parse and sanitize
    query_info = _parse_response(raw_output)

    # Post-process values (restore exact string literals where needed)
    query_info["formatted_query"] = _restore_exact_values(
        query_info["formatted_query"], schema
    )

    # Ensure we actually produced a query
    if not query_info["formatted_query"] or query_info["formatted_query"].strip() == "":
        raise ValueError(
            "No valid SQL query could be generated from the input. "
            "Please ask a specific question about the data."
        )

    # Validate SQL
    db_type = db_manager.get_db_type()
    validation = validate_with_sqlglot(query_info["formatted_query"], schema, db_type)
    if not validation.is_valid:
        logger.error(f"SQL validation failed: {validation.error_message}")
        logger.error(f"Generated query: {query_info['formatted_query']}")
        raise ValueError(f"Invalid SQL: {validation.error_message}")

    logger.info("Translation completed")
    logger.debug(f"Generated query: {query_info['formatted_query']}")

    # Attach debugging artifacts
    query_info["full_prompt"] = prompt
    query_info["raw_output"] = raw_output

    return query_info
# ==============================================================
#  PROMPT CONSTRUCTION
# ==============================================================

def _build_prompt(schema: Dict[str, Any], system_prompt: Optional[str] = None) -> str:
    """
    Build a schema-strict prompt with table-selection rule.
    """
    schema_text = _summarize_schema(schema)
    
    # Always include base prompt, and add custom prompt if provided
    combined_prompt = _get_combined_prompt(system_prompt)
    
    return f"""{combined_prompt}

DATABASE SCHEMA:
{schema_text}

Output ONLY JSON in this exact format:
{{
  "formatted_query": "<SQL query>",
  "parameters": [],
  "query_type": "read",
  "raw_output": "<raw output>",
  "full_prompt": "<full prompt>"

}}
"""


# ==============================================================
#  FULL-SCHEMA SUMMARIZATION
# ==============================================================

def _summarize_schema(schema: Dict[str, Any]) -> str:
    """
    Render structured schema summary with examples for all columns.
    """
    sections = []
    for table in schema.get("tables", []):
        table_name = table["name"]
        col_lines = []

        for col in table.get("columns", []):
            col_name = col["name"]
            data_type = col.get("type", "")
            example_values = ""

            # Get unique values count and examples (support both keys)
            examples = col.get("possible_values", []) or col.get("categorical_values", [])
            total_distinct = col.get("total_distinct_count", 0)
            
            if examples:
                clean_examples = [str(v) for v in examples if v is not None]
                
                # Determine if categorical based on unique values count
                if total_distinct > 0 and total_distinct <= 20:
                    # Categorical column - show all unique values
                    example_values = f" ({total_distinct} unique values - categorical: {', '.join(clean_examples)})"
                elif total_distinct > 20:
                    # Non-categorical column with many unique values
                    example_values = f" ({total_distinct} unique values - examples: {', '.join(clean_examples[:4])})"
                else:
                    # Fallback when total_distinct is not available
                    example_values = f" (examples: {', '.join(clean_examples[:4])})"

            default = col.get("default")
            if default:
                example_values += f" [default: {default}]"

            col_lines.append(f"  - {col_name} ({data_type}){example_values}\n")

        table_block = f"TABLE: {table_name}\n" + "".join(col_lines)
        sections.append(table_block)

    return "\n".join(sections)


# ==============================================================
#  RESPONSE PARSING
# ==============================================================

def _parse_response(response: str) -> Dict[str, Any]:
    """
    Parse and sanitize the model's response into a structured dict.
    """
    try:
        cleaned = re.sub(r"```(?:json)?", "", response)
        cleaned = re.sub(r"```", "", cleaned)
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)

        parsed = json.loads(cleaned)
    except Exception:
        sql_match = re.search(r"SELECT.*", response, re.IGNORECASE | re.DOTALL)
        sql = sql_match.group(0).strip() if sql_match else "SELECT 1"
        parsed = {
            "formatted_query": sql,
            "parameters": [],
            "query_type": "read"
        }

    sql = parsed.get("formatted_query", "SELECT 1").replace("\\n", " ").strip()

    return {
        "formatted_query": sql,
        "parameters": parsed.get("parameters", []),
        "query_type": parsed.get("query_type", "read")
    }


# ==============================================================
#  VALUE RESTORATION
# ==============================================================

def _restore_exact_values(query: str, schema: Dict[str, Any]) -> str:
    """
    Restore literal values to exact forms from schema examples
    (e.g., preserve case, spaces, or parentheses).
    """
    if not query:
        return query
    try:
        for table in schema.get("tables", []):
            for col in table.get("columns", []):
                examples = col.get("possible_values", []) or col.get("categorical_values", [])
                if not examples:
                    continue

                for val in examples:
                    if not isinstance(val, str):
                        continue

                    # Only correct when parentheses, spaces, or case matter
                    if "(" in val or " " in val or val != val.upper():
                        base = val.split("(")[0].strip()
                        pattern = rf"{col['name']}\s*=\s*['\"]{re.escape(base)}['\"]"
                        replacement = f"{col['name']} = '{val}'"
                        query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)
        return query
    except Exception as e:
        logger.debug(f"Value restoration skipped: {e}")
        return query


# ==============================================================
#  PROMPT TEMPLATES
# ==============================================================

def _get_base_prompt() -> str:
    """
    Get the default base prompt for text-to-SQL translation.
    """
    return """You are a text-to-SQL query translator.

Translate the user's natural-language question into a valid SQL query
for the database described below.

RULES:
1. Use only tables and columns that appear in the schema.
   Never invent or assume a column not listed.
2. If multiple tables contain columns with the same name,
   choose the table that includes all needed columns for the question.
3. **If all referenced columns exist in a single table, always use that table.**
4. Do not mix columns from different tables unless a clear JOIN relationship is explicitly required.
5. Use string values exactly as shown in the schema examples
   (preserve case, spaces, and parentheses).
6. If a concept (like "process" or "status") is mentioned but no matching column exists,
   use the column that most closely represents that concept — but only if it actually appears in the schema.
7. Never use or reference columns not explicitly listed.
8. Based on the following schema, translate the natural language query to a valid SQL query.
9. If asked to never use a column, find an alternative column that is related to the concept.
10. If multiple tables could answer the question, prefer the one most directly related to the entity mentioned.
11. **CRITICAL**: Node parameters take absolute priority over user's question.
    If node parameters specify values, use those exact values even if they conflict with the user's question.
12. **IMPORTANT**: For relative dates like "last year", "this month", "yesterday", etc., calculate the correct year/month/date dynamically.
    - "last year" = YEAR(NOW()) - 1
    - "this year" = YEAR(NOW())
    - "this month" = MONTH(NOW())
    - Always use dynamic date calculations, never hardcoded years.
"""


def _get_combined_prompt(system_prompt: Optional[str] = None) -> str:
    """
    Combine a custom system prompt with the base rules.
    """
    base_prompt = _get_base_prompt()
    if system_prompt:
        return f"""CRITICAL non-negotiable requirements: {system_prompt}

Basic rules:
{base_prompt}"""
    else:
        return base_prompt
