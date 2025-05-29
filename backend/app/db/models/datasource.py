<<<<<<< HEAD
from typing import Optional
from sqlalchemy import Integer, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column
=======
from typing import Optional, List
from sqlalchemy import Integer, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
>>>>>>> development

from app.db.base import Base


class DataSourceModel(Base):
    __tablename__ = 'data_sources'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='data_sources_pk'),
    )

    name: Mapped[Optional[str]] = mapped_column(String(255))
    source_type: Mapped[Optional[str]] = mapped_column(String(255))
<<<<<<< HEAD
    connection_data: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[Optional[int]] = mapped_column(Integer)

=======
    connection_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[Optional[int]] = mapped_column(Integer)

    # Relationship to KnowledgeBaseModel
    knowledge_bases = relationship("KnowledgeBaseModel", back_populates="sync_source")

>>>>>>> development

