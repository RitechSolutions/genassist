from sqlalchemy import event
from sqlalchemy.orm import Mapper

from app.auth.utils import get_current_user_id


def register_updated_by_event(model: type):
    """
    Registers a before_update hook for any model that has an `updated_by` field.
    """
    @event.listens_for(model, "before_update", propagate=True)
    def set_updated_by(mapper: Mapper, connection, target):
        user_id = get_current_user_id()
        if user_id:
            setattr(target, "updated_by", user_id)


def auto_register_updated_by(models: list[type]):
    """
    Automatically registers the event for all models that inherit from AuditMixin.
    """
    for model in models:
        if hasattr(model, "updated_by"):
            register_updated_by_event(model)
