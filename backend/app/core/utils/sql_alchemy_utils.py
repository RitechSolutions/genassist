from typing import Type

from sqlalchemy import asc, desc
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute

from app.core.utils.enums.sort_direction_enum import SortDirection
from app.core.utils.enums.sort_field_enum import SortField
from app.db.base import Base
from app.schemas.filter import BaseFilterModel


def resolve_sort_column(
    model: Type[DeclarativeBase], field: SortField
) -> InstrumentedAttribute:
    """
    Return the SQLAlchemy column attribute that corresponds to `field`
    for the given model. Raise if the model doesn't have it.
    """
    try:
        column = getattr(model, field.value)
    except AttributeError as exc:
        raise ValueError(
            f"{model.__name__} has no column named {field.value!r}"
        ) from exc
    return column


def add_dynamic_ordering(model: Base, filter: BaseFilterModel, query):
    column = resolve_sort_column(model, filter.order_by)
    order_clause = (
        desc(column) if filter.sort_direction == SortDirection.DESC else asc(column)
    )
    query = query.order_by(order_clause)
    return query


def add_pagination(filter: BaseFilterModel, query):
    query = query.offset(filter.skip).limit(filter.limit)
    return query
