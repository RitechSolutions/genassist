from typing import Optional
from sqlalchemy import PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TranslationModel(Base):
    __tablename__ = "translations"
    __table_args__ = (PrimaryKeyConstraint("id", name="translations_pk"),)

    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    default: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    en: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    es: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fr: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    de: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pt: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    zh: Mapped[Optional[str]] = mapped_column(String, nullable=True)
