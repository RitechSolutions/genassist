from torch.fx.immutable_collections import immutable_list

from app.core.exceptions.error_messages import ErrorKey


class AppException(Exception):
    """
        Custom exception class for handling application-specific exceptions.

        This exception takes an error key and an optional status code, retrieves
        the corresponding error message from the error messages module, and raises
        an exception with a formatted message.

        Attributes:
            message (str): The error message retrieved using the provided error key.
            status_code (int): The HTTP status code associated with the error (default: 400).

        Args:
            error_key (str): The key used to fetch the error message from the error messages module.
            status_code (int, optional): The HTTP status code for the error response (default: 400).

        Example:
            ```python
            raise AppException("invalid_sentiment_format", 422)
            ```

        Raises:
            AppException: When an application-specific error occurs.
        """
    def __init__(self, error_key: ErrorKey, status_code=400, error_detail="", error_obj= None,
                 error_variables: list[str] = immutable_list()):
        self.error_key: ErrorKey = error_key
        self.status_code = status_code
        self.error_detail = error_detail
        self.error_obj = error_obj
        self.error_variables = error_variables
        super().__init__(error_key.value)

