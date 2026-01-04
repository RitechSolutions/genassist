from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria
from app.db.base import SoftDeleteMixin


SOFT_DELETE_FLAG = "include_deleted"

@event.listens_for(Session, "do_orm_execute")
def _soft_delete_filter(execute_state):
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get(SOFT_DELETE_FLAG):
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.is_deleted == 0,
            include_aliases=True,
        )
    )