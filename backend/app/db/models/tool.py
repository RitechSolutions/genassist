from sqlalchemy.orm import relationship
from app.db.base import Base, Mapped, mapped_column
from sqlalchemy import String
from typing import Optional
from sqlalchemy.dialects.postgresql import JSONB


class ToolModel(Base):
    __tablename__ = "tools"

    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String)
    api_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    function_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    parameters_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)