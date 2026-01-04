from typing import Annotated, Any, TypeVar, Generic
from pydantic import BeforeValidator,  TypeAdapter
from pydantic_core import PydanticUseDefault, CoreSchema

# 1. Define a TypeVar
T = TypeVar("T")

# 2. Define a reusable validator


def use_default_if_none_validator(v: Any) -> Any:
    if v is None:
        raise PydanticUseDefault()
    return v

# 3. Create a generic TypeAdapter to handle the validation


class UseDefaultIfNone(Generic[T]):
    """
    A generic type that uses the field's default value if None is passed.
    """

    def __init__(self, type_hint: Any):
        self.type_adapter = TypeAdapter(
            Annotated[type_hint, BeforeValidator(
                use_default_if_none_validator)]
        )

    def __get_pydantic_core_schema__(self, *args) -> CoreSchema:
        return self.type_adapter.core_schema

    def __class_getitem__(cls, item):
        return UseDefaultIfNone(item)
