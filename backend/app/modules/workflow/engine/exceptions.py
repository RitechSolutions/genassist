"""Custom exceptions for workflow execution."""


class WorkflowPausedException(Exception):
    """
    Raised by a node to pause workflow execution and wait for user input.

    Attributes:
        node_id: ID of the node that triggered the pause
        form_schema: Schema defining the form fields to present to the user
        message: Human-readable pause message
    """

    def __init__(
        self,
        node_id: str,
        form_schema: dict,
        message: str = "Workflow paused for user input",
    ):
        self.node_id = node_id
        self.form_schema = form_schema
        self.message = message
        super().__init__(message)
