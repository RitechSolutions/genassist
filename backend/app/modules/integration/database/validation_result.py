from dataclasses import dataclass
from typing import List, Optional, Set


@dataclass
class ValidationResult:
    """Result of query validation."""

    is_valid: bool
    error_message: Optional[str] = None
    warnings: List[str] = None
    query_type: Optional[str] = None
    tables_used: Set[str] = None
    columns_used: Set[str] = None
