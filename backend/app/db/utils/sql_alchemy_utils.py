from sqlalchemy import inspect

def null_unloaded_attributes(obj):
    """Prevent lazy_loading errors Missing Greenlet"""
    state = inspect(obj)

    # Only attempt setting attributes that are not already loaded
    for attr_name in state.mapper.relationships.keys():
        if attr_name in state.unloaded:
            # Set to None to avoid triggering lazy load
            object.__setattr__(obj, attr_name, None)