from typing import Dict, Tuple, Optional, Set, List
import re
import sqlparse
from sqlparse import sql, tokens as T
from dataclasses import dataclass
from app.modules.agents.db_utils.database_manager import DatabaseManager


@dataclass
class ValidationResult:
    """Result of query validation."""
    is_valid: bool
    error_message: Optional[str] = None
    warnings: List[str] = None
    query_type: Optional[str] = None
    tables_used: Set[str] = None
    columns_used: Set[str] = None

class AdvancedQueryValidator:
    """Advanced SQL query validator with better parsing."""
    
    def __init__(self, db_manager: DatabaseManager, schema: Dict = None):
        self.db_manager = db_manager
        self.schema = schema or db_manager.get_schema()
        self.schema_tables = {table["name"].lower() for table in self.schema.get("tables", [])}
        self.schema_columns = self._build_column_mapping()
        
    def _build_column_mapping(self) -> Dict[str, Set[str]]:
        """Build mapping of table -> columns."""
        columns = {}
        for table in self.schema.get("tables", []):
            table_name = table["name"].lower()
            columns[table_name] = {col["name"].lower() for col in table.get("columns", [])}
        return columns
    
    def validate_query(self, query: str) -> ValidationResult:
        """
        Comprehensive query validation.
        
        Args:
            query: SQL query to validate
            
        Returns:
            ValidationResult with detailed validation info
        """
        try:
            # Handle dict input
            query_text = query.get('formatted_query') if isinstance(query, dict) else query
            
            # Parse with sqlparse
            parsed = sqlparse.parse(query_text)
            if not parsed:
                return ValidationResult(False, "Could not parse SQL query")
            
            statement = parsed[0]
            query_type = statement.get_type()
            
            # Extract tables and columns
            tables_used, table_aliases = self._extract_tables(statement)
            columns_used = self._extract_columns(statement, table_aliases)
            
            # Perform validations
            validation_checks = [
                self._validate_syntax(statement),
                self._validate_tables(tables_used),
                self._validate_columns(columns_used, tables_used, table_aliases),
                self._validate_query_type(statement, query_type),
                self._validate_security(query_text),
                self._validate_performance(statement, query_text)
            ]
            
            # Collect results
            errors = []
            warnings = []
            
            for check_result in validation_checks:
                if not check_result.is_valid:
                    errors.append(check_result.error_message)
                if check_result.warnings:
                    warnings.extend(check_result.warnings)
            
            if errors:
                return ValidationResult(
                    False, 
                    "; ".join(errors), 
                    warnings, 
                    query_type, 
                    tables_used, 
                    columns_used
                )
            
            return ValidationResult(
                True, 
                None, 
                warnings, 
                query_type, 
                tables_used, 
                columns_used
            )
            
        except Exception as e:
            return ValidationResult(False, f"Validation error: {str(e)}")
    
    def _extract_tables(self, statement) -> Tuple[Set[str], Dict[str, str]]:
        """Extract table names and aliases from parsed statement."""
        tables = set()
        aliases = {}
        
        def extract_from_token(token):
            if token.ttype is T.Keyword and token.normalized in ('FROM', 'JOIN', 'UPDATE', 'INTO'):
                # Get next non-whitespace token
                next_token = self._get_next_token(statement, token)
                if next_token:
                    table_info = self._parse_table_reference(next_token)
                    if table_info:
                        table_name, alias = table_info
                        tables.add(table_name.lower())
                        if alias:
                            aliases[alias.lower()] = table_name.lower()
        
        # Traverse all tokens
        for token in statement.flatten():
            extract_from_token(token)
        
        return tables, aliases
    
    def _extract_columns(self, statement, table_aliases: Dict[str, str]) -> Set[str]:
        """Extract column references from parsed statement."""
        columns = set()
        
        def is_column_context(prev_tokens):
            """Check if we're in a context where columns are expected."""
            keywords = {'SELECT', 'WHERE', 'ORDER', 'GROUP', 'HAVING', 'ON', 'SET'}
            return any(token.normalized in keywords for token in prev_tokens[-3:] 
                      if hasattr(token, 'normalized'))
        
        tokens_list = list(statement.flatten())
        for i, token in enumerate(tokens_list):
            if token.ttype is T.Name:
                # Check context
                prev_tokens = tokens_list[max(0, i-3):i]
                if is_column_context(prev_tokens):
                    # Check for qualified column (table.column)
                    if i + 2 < len(tokens_list) and tokens_list[i + 1].match(T.Punctuation, '.'):
                        table_part = token.value.lower()
                        column_part = tokens_list[i + 2].value.lower()
                        columns.add(f"{table_part}.{column_part}")
                    else:
                        columns.add(token.value.lower())
        
        return columns
    
    def _validate_syntax(self, statement) -> ValidationResult:
        """Validate basic SQL syntax."""
        try:
            # Check for balanced parentheses
            query_str = str(statement)
            if query_str.count('(') != query_str.count(')'):
                return ValidationResult(False, "Unbalanced parentheses in query")
            
            # Check for basic SQL structure
            query_type = statement.get_type()
            if not query_type:
                return ValidationResult(False, "Unable to determine query type")
            
            return ValidationResult(True)
        except Exception as e:
            return ValidationResult(False, f"Syntax validation failed: {str(e)}")
    
    def _validate_tables(self, tables_used: Set[str]) -> ValidationResult:
        """Validate that all referenced tables exist."""
        missing_tables = tables_used - self.schema_tables
        if missing_tables:
            return ValidationResult(
                False, 
                f"Referenced tables not found in schema: {', '.join(missing_tables)}"
            )
        return ValidationResult(True)
    
    def _validate_columns(self, columns_used: Set[str], tables_used: Set[str], 
                         table_aliases: Dict[str, str]) -> ValidationResult:
        """Validate that all referenced columns exist."""
        errors = []
        warnings = []
        
        for column_ref in columns_used:
            if '.' in column_ref:
                # Qualified column reference
                table_part, column_part = column_ref.split('.', 1)
                
                # Resolve alias if present
                actual_table = table_aliases.get(table_part, table_part)
                
                if actual_table not in self.schema_columns:
                    errors.append(f"Table '{table_part}' not found for column '{column_ref}'")
                elif column_part not in self.schema_columns[actual_table]:
                    errors.append(f"Column '{column_part}' not found in table '{actual_table}'")
            else:
                # Unqualified column reference
                found_in_tables = []
                for table in tables_used:
                    if column_ref in self.schema_columns.get(table, set()):
                        found_in_tables.append(table)
                
                if not found_in_tables:
                    # Check if it's a function or special keyword
                    if not self._is_sql_function_or_keyword(column_ref):
                        errors.append(f"Column '{column_ref}' not found in any referenced table")
                elif len(found_in_tables) > 1:
                    warnings.append(f"Ambiguous column '{column_ref}' found in multiple tables: {found_in_tables}")
        
        if errors:
            return ValidationResult(False, "; ".join(errors), warnings)
        return ValidationResult(True, warnings=warnings)
    
    def _validate_query_type(self, statement, query_type: str) -> ValidationResult:
        """Validate query type specific rules."""
        warnings = []
        
        if query_type == 'INSERT':
            # Check for INSERT without explicit columns
            query_str = str(statement).upper()
            if 'INSERT INTO' in query_str and '(' not in query_str.split('VALUES')[0]:
                warnings.append("INSERT without explicit column list - consider specifying columns")
        
        elif query_type == 'UPDATE':
            # Check for UPDATE without WHERE clause
            query_str = str(statement).upper()
            if 'WHERE' not in query_str:
                warnings.append("UPDATE without WHERE clause - this will update all rows")
        
        elif query_type == 'DELETE':
            # Check for DELETE without WHERE clause
            query_str = str(statement).upper()
            if 'WHERE' not in query_str:
                return ValidationResult(False, "DELETE without WHERE clause is not allowed")
        
        return ValidationResult(True, warnings=warnings)
    
    def _validate_security(self, query_text: str) -> ValidationResult:
        """Validate against SQL injection and other security issues."""
        # Improved SQL injection detection
        suspicious_patterns = [
            (r";\s*DROP\s+", "Potential DROP statement injection"),
            (r";\s*DELETE\s+FROM\s+(?!.*WHERE)", "Potential mass DELETE injection"),
            (r";\s*TRUNCATE\s+", "Potential TRUNCATE injection"),
            (r";\s*ALTER\s+", "Potential schema modification"),
            (r"UNION\s+(?:ALL\s+)?SELECT.*--", "Potential UNION injection with comment"),
            (r"'.*OR.*'.*='.*'", "Potential OR injection"),
            (r"1\s*=\s*1", "Potential always-true condition"),
            (r"'.*;\s*--", "Potential comment injection"),
            (r"EXEC\s*\(", "Potential dynamic execution"),
            (r"xp_cmdshell", "Potential command execution"),
        ]
        
        for pattern, description in suspicious_patterns:
            if re.search(pattern, query_text, re.IGNORECASE | re.DOTALL):
                return ValidationResult(False, f"Security violation: {description}")
        
        return ValidationResult(True)
    
    def _validate_performance(self, statement, query_text: str) -> ValidationResult:
        """Check for potential performance issues."""
        warnings = []
        
        # Check for SELECT * with potential large result sets
        if re.search(r"SELECT\s+\*", query_text, re.IGNORECASE):
            if not re.search(r"LIMIT\s+\d+", query_text, re.IGNORECASE):
                warnings.append("SELECT * without LIMIT may return large result sets")
        
        # Check for missing WHERE clause in SELECT
        query_upper = query_text.upper()
        if query_upper.startswith('SELECT') and 'WHERE' not in query_upper and 'LIMIT' not in query_upper:
            warnings.append("SELECT without WHERE or LIMIT clause may scan entire table")
        
        # Check for LIKE patterns starting with wildcard
        if re.search(r"LIKE\s+['\"]%", query_text, re.IGNORECASE):
            warnings.append("LIKE pattern starting with % cannot use indexes efficiently")
        
        return ValidationResult(True, warnings=warnings)
    
    def _is_sql_function_or_keyword(self, name: str) -> bool:
        """Check if name is a SQL function or keyword."""
        sql_functions = {
            'count', 'sum', 'avg', 'max', 'min', 'now', 'current_date', 
            'current_time', 'current_timestamp', 'length', 'upper', 'lower',
            'substring', 'concat', 'coalesce', 'nullif', 'case', 'when', 'then',
            'else', 'end', 'distinct', 'all', 'exists'
        }
        return name.lower() in sql_functions
    
    def _get_next_token(self, statement, current_token):
        """Get next non-whitespace token."""
        tokens = list(statement.flatten())
        try:
            current_index = tokens.index(current_token)
            for i in range(current_index + 1, len(tokens)):
                if not tokens[i].is_whitespace:
                    return tokens[i]
        except ValueError:
            pass
        return None
    
    def _parse_table_reference(self, token) -> Optional[Tuple[str, Optional[str]]]:
        """Parse table reference to extract table name and alias."""
        if hasattr(token, 'value'):
            # Simple case: just table name
            return token.value, None
        return None

def validate_with_sqlglot(query: str, schema: Dict) -> ValidationResult:
    """
    SQLGlot is much more accurate for parsing and validation.
    """
    try:
        import sqlglot
        from sqlglot import parse_one, transpile
        from sqlglot.errors import ParseError, TokenError
        
        # Parse the query
        try:
            parsed = parse_one(query)
        except (ParseError, TokenError) as e:
            return ValidationResult(False, f"SQL syntax error: {str(e)}")
        
        # Extract tables and columns
        tables = set()
        columns = set()
        
        for table in parsed.find_all(sqlglot.exp.Table):
            tables.add(table.name.lower())
        
        for column in parsed.find_all(sqlglot.exp.Column):
            if column.table:
                columns.add(f"{column.table.lower()}.{column.name.lower()}")
            else:
                columns.add(column.name.lower())
        
        # Validate against schema
        schema_tables = {table["name"].lower() for table in schema.get("tables", [])}
        missing_tables = tables - schema_tables
        
        if missing_tables:
            return ValidationResult(
                False, 
                f"Tables not found: {', '.join(missing_tables)}",
                query_type=str(parsed.__class__.__name__),
                tables_used=tables,
                columns_used=columns
            )
        
        return ValidationResult(
            True, 
            query_type=str(parsed.__class__.__name__),
            tables_used=tables,
            columns_used=columns
        )
        
    except ImportError:
        return ValidationResult(False, "SQLGlot library not installed")
    except Exception as e:
        return ValidationResult(False, f"Validation error: {str(e)}")