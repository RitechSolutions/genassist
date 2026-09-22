"""Safe errors raised while preparing bound database parameters."""


class BoundValueError(ValueError):
    """A workflow variable could not be converted to a database value type."""

    def __init__(self, variable_name: str, expected_type: str):
        self.variable_name = variable_name
        self.expected_type = expected_type
        super().__init__(f"Workflow variable '{variable_name}' must be a valid {expected_type} value.")
