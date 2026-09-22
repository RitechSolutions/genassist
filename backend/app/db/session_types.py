from typing import NewType

from sqlalchemy.ext.asyncio import AsyncSession

# Request-scoped session bound to the read replica. Resolves to the request's
# write session when DB_READ_HOST is not configured. A NewType keeps it a separate
# injector key: injector drops Annotated metadata from constructor parameters.
ReadOnlySession = NewType("ReadOnlySession", AsyncSession)
