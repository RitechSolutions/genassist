from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
<<<<<<< HEAD
from app.db.models import Tool
=======
from app.db.models import ToolModel
>>>>>>> development
from app.db.session import get_db
from app.repositories.db_repository import DbRepository


<<<<<<< HEAD
class ToolRepository(DbRepository[Tool]):
    def __init__(self, db: AsyncSession = Depends(get_db)):
        super().__init__(Tool, db)
=======
class ToolRepository(DbRepository[ToolModel]):
    def __init__(self, db: AsyncSession = Depends(get_db)):
        super().__init__(ToolModel, db)
>>>>>>> development
