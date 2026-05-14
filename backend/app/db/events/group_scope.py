from sqlalchemy import and_, event, or_, select
from sqlalchemy.orm import Session, with_loader_criteria
from starlette_context import context
from starlette_context.errors import ContextDoesNotExistError

from app.auth.utils import current_user_is_admin

GROUP_SCOPE_BYPASS_FLAG = "bypass_group_scope"


class GroupScopedMixin:
    """
    Marker mixin — models that inherit this are subject to group-scoped row
    filtering on every SELECT. By default filtering uses the existing
    ``created_by`` column (from AuditMixin) to restrict rows to those created
    by members of the requesting user's group.

    ``ConversationModel`` additionally uses an optional ``group_id`` column
    (agent owner's group) combined with the same ``created_by`` rules for rows
    where ``group_id`` is null.

    To opt a model in, simply add GroupScopedMixin to its base classes::

        class AgentModel(Base, GroupScopedMixin):
            ...

    To bypass for a specific query::

        session.execute(stmt, execution_options={GROUP_SCOPE_BYPASS_FLAG: True})
    """
    pass


def _build_criteria(model_cls, group_id, supervised_group_ids, user_id):
    """Build the WHERE clause for a given user context."""
    from app.db.models.user import UserModel

    if supervised_group_ids:
        # Supervisor: records created by users in any of their supervised groups
        return model_cls.created_by.in_(
            select(UserModel.id).where(UserModel.group_id.in_(supervised_group_ids))
        )
    if group_id:
        # Regular user in a group: records created by anyone in same group
        return model_cls.created_by.in_(
            select(UserModel.id).where(UserModel.group_id == group_id)
        )
    # No group: own records only
    return model_cls.created_by == user_id


def _build_conversation_criteria(model_cls, group_id, supervised_group_ids, user_id):
    """
    Conversations may carry an explicit ``group_id`` (agent owner's group).
    Visible rows: match ``group_id`` to the viewer's group / supervised groups,
    or fall back to ``created_by`` rules when ``group_id`` is null (legacy rows).
    """
    from app.db.models.user import UserModel

    if supervised_group_ids:
        legacy = model_cls.created_by.in_(
            select(UserModel.id).where(UserModel.group_id.in_(supervised_group_ids))
        )
        return or_(
            model_cls.group_id.in_(supervised_group_ids),
            and_(model_cls.group_id.is_(None), legacy),
        )
    if group_id:
        legacy = model_cls.created_by.in_(
            select(UserModel.id).where(UserModel.group_id == group_id)
        )
        return or_(
            model_cls.group_id == group_id,
            and_(model_cls.group_id.is_(None), legacy),
        )
    legacy = model_cls.created_by == user_id
    return and_(model_cls.group_id.is_(None), legacy)


def get_group_scope_clause(model_cls):
    """
    Return a SQLAlchemy WHERE clause for group-based row filtering, or ``None``
    if no filtering should be applied (admin, no auth context, etc.).

    Use this for queries that select individual columns or aggregates rather than
    full ORM entities, since ``with_loader_criteria`` only fires for entity selects::

        clause = get_group_scope_clause(AgentModel)
        if clause is not None:
            stmt = stmt.where(clause)
    """
    try:
        group_id = context.get("group_id")
        user_id = context.get("user_id")
        supervised_group_ids = context.get("supervised_group_ids") or []
    except (LookupError, ContextDoesNotExistError):
        return None

    if not user_id:
        return None

    try:
        if current_user_is_admin():
            return None
    except Exception:
        return None

    from app.db.models.conversation import ConversationModel

    if model_cls is ConversationModel:
        return _build_conversation_criteria(
            model_cls, group_id, supervised_group_ids, user_id
        )
    return _build_criteria(model_cls, group_id, supervised_group_ids, user_id)


@event.listens_for(Session, "do_orm_execute")
def _group_scope_filter(execute_state):
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get(GROUP_SCOPE_BYPASS_FLAG):
        return

    try:
        group_id = context.get("group_id")
        user_id = context.get("user_id")
        supervised_group_ids = context.get("supervised_group_ids") or []
    except (LookupError, ContextDoesNotExistError):
        # No request context — background tasks, startup, permission sync, etc.
        return

    if not user_id:
        # Unauthenticated or system context — skip filtering
        return

    try:
        if current_user_is_admin():
            return
    except Exception:
        # If role check fails for any reason, don't apply filter
        return

    # Build criteria using a lambda so SQLAlchemy can substitute the concrete
    # model class. We use __subclasses__() because GroupScopedMixin has no
    # columns — the lambda inspection requires `created_by` on the target class.
    from app.db.models.user import UserModel

    if supervised_group_ids:
        _ids = tuple(supervised_group_ids)  # capture for closure

        def default_criteria(cls):
            return cls.created_by.in_(
                select(UserModel.id).where(UserModel.group_id.in_(_ids))
            )

        def conversation_criteria(cls):
            legacy = cls.created_by.in_(
                select(UserModel.id).where(UserModel.group_id.in_(_ids))
            )
            return or_(cls.group_id.in_(_ids), and_(cls.group_id.is_(None), legacy))

    elif group_id:
        _gid = group_id

        def default_criteria(cls):
            return cls.created_by.in_(
                select(UserModel.id).where(UserModel.group_id == _gid)
            )

        def conversation_criteria(cls):
            legacy = cls.created_by.in_(
                select(UserModel.id).where(UserModel.group_id == _gid)
            )
            return or_(cls.group_id == _gid, and_(cls.group_id.is_(None), legacy))

    else:
        _uid = user_id

        def default_criteria(cls):
            return cls.created_by == _uid

        def conversation_criteria(cls):
            legacy = cls.created_by == _uid
            return and_(cls.group_id.is_(None), legacy)

    for scoped_cls in GroupScopedMixin.__subclasses__():
        if scoped_cls.__name__ == "ConversationModel":
            crit = conversation_criteria
        else:
            crit = default_criteria
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(scoped_cls, crit, include_aliases=True)
        )