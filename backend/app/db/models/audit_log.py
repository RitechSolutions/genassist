import json
<<<<<<< HEAD
import datetime
=======
>>>>>>> development
from sqlalchemy import UUID, Column, String, DateTime, event, Integer
from sqlalchemy.orm import attributes, Session
from sqlalchemy.ext.declarative import DeclarativeMeta
from app.auth.utils import get_current_user_id
<<<<<<< HEAD
from app.db.base import Base
=======
from app.core.utils.date_time_utils import utc_now
from app.db.base import Base
from sqlalchemy.inspection import inspect
import uuid



>>>>>>> development
# TODO recheck the limit and logic
audit_json_limit = 4000
# Define the AuditLog model
class AuditLogModel(Base):
    __tablename__ = 'audit_log'
    id = Column(Integer, primary_key=True)  #Autoincrementing integer ID
    table_name = Column(String(255), nullable=False)
    record_id = Column(UUID(as_uuid=True), nullable=False)
    action_name = Column(String(255), nullable=False)
    json_changes = Column(String(audit_json_limit))
    modified_at = Column(DateTime(timezone=True), default=utc_now())
    modified_by = Column(UUID(as_uuid=True))  # Optional: User who made the change.

class AlchemyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            # Convert SQLAlchemy model to dictionary
            fields = {}
            for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
                data = obj.__getattribute__(field)
                try:
                    #print(f"Field: {field}, dump Data: {data}")  # Debugging line
                    json.dumps(data)
                    fields[field] = data
                except TypeError:
                    val = str(data)
                    #print(f"Field: {field}, str Data: {data}")  # Debugging line
                    if not val.startswith('<sqlalchemy.orm') and not val.startswith('<app.models') and not val.startswith('[<app.models'):
                        fields[field] = val

            return fields
        
        try:
            return json.JSONEncoder.default(self, obj)
        except:
            return str(obj)
    
def stringify_value(value):
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value.__class__, DeclarativeMeta):
        return {c.key: stringify_value(getattr(value, c.key))
                for c in inspect(value).mapper.column_attrs}
    if isinstance(value, (list, tuple)):
        return [stringify_value(v) for v in value]
    try:
        json.dumps(value)          # scalars & built-ins
        return value
    except TypeError:
        return str(value)

def model_to_dict(obj) -> dict:
    """Return a dict with only column attributes, JSON-safe."""
    return {
        c.key: stringify_value(getattr(obj, c.key))
        for c in inspect(obj).mapper.column_attrs
    }

# Event listener for logging changes
@event.listens_for(Session, 'before_flush')
def before_flush(session, flush_context, instances):
    for instance in session.new:

        if isinstance(instance, (AuditLogModel)):  # Skip logging of AuditLog changes themselves
            continue

        tablename = instance.__tablename__
        setattr(instance, 'created_by', get_current_user_id())

    for instance in session.dirty:
        if isinstance(instance, (AuditLogModel)):  # Skip logging of AuditLog changes themselves
            continue

        tablename = instance.__tablename__
        state = attributes.instance_state(instance)
        record_id = getattr(instance, 'id') # Get record ID
        setattr(instance, 'updated_by', get_current_user_id())

        changes = {}
        for key in state.attrs:
            history = attributes.get_history(instance, key.key)
            if history.has_changes():
                old_value = stringify_value(history.deleted[0] if history.deleted else None)
                new_value = stringify_value(history.added[0] if history.added else None)

                if old_value != new_value:  #Only log if there's an actual change.
                    changes[key.key] = {'old': old_value, 'new': new_value}

        audit_log = AuditLogModel(
            table_name=tablename,
            record_id=record_id,
            action_name='Update',
            json_changes=json.dumps(changes, cls=AlchemyEncoder)[:audit_json_limit],
            modified_at=utc_now(),
            modified_by=get_current_user_id()
        )
        session.add(audit_log)

    for instance in session.deleted:
        if isinstance(instance, (AuditLogModel)):  #Avoid infinite recursion if you're deleting audit logs.
            continue

        tablename = instance.__tablename__
        record_id = getattr(instance, 'id') # Get record ID
        state = attributes.instance_state(instance)

        changes = {}
        for key in state.attrs:
            history = attributes.get_history(instance, key.key)
            if history.has_changes():
                old_value = stringify_value(history.deleted[0] if history.deleted else None)
                new_value = stringify_value(history.added[0] if history.added else None)

                if old_value != new_value:  #Only log if there's an actual change.
                    changes[key.key] = {'old': old_value, 'new': new_value}

        # Log the deletion of the record
        audit_log = AuditLogModel(
            table_name=tablename,
            record_id=record_id,
            action_name='Delete',  # Special column to mark deletion
            json_changes=json.dumps(instance, cls=AlchemyEncoder)[:audit_json_limit], #str(changes),  # Store representation of the deleted object
            modified_at=utc_now(),
            modified_by=get_current_user_id()
        )
        session.add(audit_log)

@event.listens_for(Session, 'after_flush')
def after_flush(session, flush_context):
    for instance in session.new:

        if isinstance(instance, (AuditLogModel)):  # Skip logging of AuditLog changes themselves
            continue

        tablename = instance.__tablename__
        record_id = getattr(instance, 'id')  # Get record ID
        state = attributes.instance_state(instance)

        changes = {}
        for key in state.attrs:
            history = attributes.get_history(instance, key.key)
            if history.has_changes():
                old_value = stringify_value(history.deleted[0] if history.deleted else None)
                new_value = stringify_value(history.added[0] if history.added else None)

                if old_value != new_value:  #Only log if there's an actual change.
                    changes[key.key] = {'old': old_value, 'new': new_value}

        audit_log = AuditLogModel(
            table_name=tablename,
            record_id=record_id,
            action_name='Insert',
            json_changes=json.dumps(model_to_dict(instance))[:audit_json_limit], #str(changes),
            modified_at=utc_now(),
            modified_by=get_current_user_id()
        )
        session.add(audit_log)
