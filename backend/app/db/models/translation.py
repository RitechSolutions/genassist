from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LanguageModel(Base):
    __tablename__ = "languages"
    __table_args__ = (PrimaryKeyConstraint("id", name="languages_pk"),)

    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    translation_values: Mapped[list["TranslationValueModel"]] = relationship(
        back_populates="language", cascade="all, delete-orphan"
    )


class TranslationKeyModel(Base):
    __tablename__ = "translation_keys"
    __table_args__ = (PrimaryKeyConstraint("id", name="translation_keys_pk"),)

    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    default_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    values: Mapped[list["TranslationValueModel"]] = relationship(
        back_populates="translation_key", cascade="all, delete-orphan"
    )


class TranslationValueModel(Base):
    __tablename__ = "translation_values"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="translation_values_pk"),
        UniqueConstraint("translation_key_id", "language_id", name="uq_translation_key_language"),
    )

    translation_key_id: Mapped[UUID] = mapped_column(
        ForeignKey("translation_keys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language_id: Mapped[UUID] = mapped_column(
        ForeignKey("languages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)

    translation_key: Mapped["TranslationKeyModel"] = relationship(back_populates="values")
    language: Mapped["LanguageModel"] = relationship(back_populates="translation_values")
