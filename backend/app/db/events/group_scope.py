from sqlalchemy import event, select
from sqlalchemy.orm import Session, with_loader_criteria
from starlette_context import context
from starlette_context.errors import ContextDoesNotExistError

from app.auth.utils import is_current_user_supervisor_or_admin

GROUP_SCOPE_BYPASS_FLAG = "bypass_group_scope"


class GroupScopedMixin:
    """
    Marker mixin — models that inherit this are subject to group-scoped row
    filtering on every SELECT.  No columns are added; filtering uses the
    existing ``created_by`` column (from AuditMixin) to restrict rows to
    those created by members of the requesting user's group.

    To opt a model in, simply add GroupScopedMixin to its base classes::

        class AgentModel(Base, GroupScopedMixin):
            ...

    To bypass for a specific query::

        session.execute(stmt, execution_options={GROUP_SCOPE_BYPASS_FLAG: True})
    """
    pass


def get_group_scope_clause(model_cls):
    """
    Return a SQLAlchemy WHERE clause for group-based row filtering, or ``None``
    if no filtering should be applied (supervisor/admin, no auth context, etc.).

    Use this for queries that select individual columns or aggregates rather than
    full ORM entities, since ``with_loader_criteria`` only fires for entity selects::

        clause = get_group_scope_clause(AgentModel)
        if clause is not None:
            stmt = stmt.where(clause)
    """
    try:
        group_id = context.get("group_id")
        user_id = context.get("user_id")
    except (LookupError, ContextDoesNotExistError):
        return None

    if not user_id:
        return None

    try:
        if is_current_user_supervisor_or_admin():
            return None
    except Exception:
        return None

    from app.db.models.user import UserModel

    if group_id:
        return model_cls.created_by.in_(
            select(UserModel.id).where(UserModel.group_id == group_id)
        )
    return model_cls.created_by == user_id


@event.listens_for(Session, "do_orm_execute")
def _group_scope_filter(execute_state):
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get(GROUP_SCOPE_BYPASS_FLAG):
        return

    try:
        group_id = context.get("group_id")
        user_id = context.get("user_id")
    except (LookupError, ContextDoesNotExistError):
        # No request context — background tasks, startup, permission sync, etc.
        return

    if not user_id:
        # Unauthenticated or system context — skip filtering
        return

    try:
        if is_current_user_supervisor_or_admin():
            return
    except Exception:
        # If role check fails for any reason, don't apply filter
        return

    # Lazy import to avoid circular dependency at module load time
    from app.db.models.user import UserModel

    if group_id:
        # User belongs to a group: show records created by any member of that group
        criteria = lambda cls: cls.created_by.in_(
            select(UserModel.id).where(UserModel.group_id == group_id)
        )
    else:
        # User has no group: show only their own records
        criteria = lambda cls: cls.created_by == user_id

    # Apply filter to each concrete model that opted in via GroupScopedMixin.
    # We use __subclasses__() instead of with_loader_criteria(GroupScopedMixin, ...)
    # because GroupScopedMixin has no columns of its own — the lambda inspection
    # requires `created_by` to be present on the target class, which it is on
    # every concrete model (via AuditMixin / Base).
    for scoped_cls in GroupScopedMixin.__subclasses__():
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(scoped_cls, criteria, include_aliases=True)
        )