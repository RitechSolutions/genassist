from sqlalchemy import inspect


def null_unloaded_attributes(obj):
    """Prevent lazy_loading errors Missing Greenlet"""
    if isinstance(obj, list):
        for item in obj:
            null_unloaded_attributes(item)
    else:
        _null_attributes_for_object(obj)


def _null_attributes_for_object(obj):
    state = inspect(obj)

    for attr_name in state.mapper.relationships.keys():
        if attr_name in state.unloaded:
            relationship = state.mapper.relationships[attr_name]

            if relationship.uselist:
                obj.__dict__[attr_name] = []
                # Mark as loaded in SQLAlchemy's state
                state.committed_state[attr_name] = []
            else:
                obj.__dict__[attr_name] = None
                state.committed_state[attr_name] = None


def is_loaded(obj, attr_name: str) -> bool:
    """Check if an attribute is loaded without triggering lazy load"""
    state = inspect(obj)
    return attr_name not in state.unloaded