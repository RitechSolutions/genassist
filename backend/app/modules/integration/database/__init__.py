from .validation_result import ValidationResult

__all__ = ["DatabaseManager", "AdvancedQueryValidator", "ValidationResult",
           "validate_with_sqlglot", "DBProviderManager", "translate_to_query", "db_provider_manager"]


def __getattr__(name):
    if name == "DatabaseManager":
        from .database_manager import DatabaseManager
        globals()[name] = DatabaseManager
        return DatabaseManager
    if name == "AdvancedQueryValidator":
        from .query_validator import AdvancedQueryValidator
        globals()[name] = AdvancedQueryValidator
        return AdvancedQueryValidator
    if name == "validate_with_sqlglot":
        from .query_validator import validate_with_sqlglot
        globals()[name] = validate_with_sqlglot
        return validate_with_sqlglot
    if name == "DBProviderManager":
        from .provider_manager import DBProviderManager
        globals()[name] = DBProviderManager
        return DBProviderManager
    if name == "translate_to_query":
        from .query_translator import translate_to_query
        globals()[name] = translate_to_query
        return translate_to_query
    if name == "db_provider_manager":
        from .provider_manager import DBProviderManager
        value = DBProviderManager.get_instance()
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
