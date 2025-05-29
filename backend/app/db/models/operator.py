import decimal
from typing import Optional
<<<<<<< HEAD
from sqlalchemy import UUID, BigInteger, ForeignKeyConstraint, Integer, LargeBinary, Numeric, PrimaryKeyConstraint, \
=======
from sqlalchemy import ForeignKey, UUID, BigInteger, ForeignKeyConstraint, Integer, LargeBinary, Numeric, \
    PrimaryKeyConstraint, \
>>>>>>> development
    String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OperatorModel(Base):
    __tablename__ = 'operators'
    __table_args__ = (
        ForeignKeyConstraint(['statistics_id'], ['operator_statistics.id'], name='statistics_id_fk'),
        PrimaryKeyConstraint('id', name='operators_pkey')
    )

    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    statistics_id: Mapped[UUID] = mapped_column(UUID)
    is_active: Mapped[Optional[int]] = mapped_column(Integer)
    avatar: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

<<<<<<< HEAD
    # One-to-one relationship instead of list
=======
    # relationships
>>>>>>> development
    operator_statistics = relationship(
        "OperatorStatisticsModel", back_populates='operator', uselist=False
    )
    conversations = relationship("ConversationModel", back_populates="operator")
<<<<<<< HEAD
=======
    user = relationship("UserModel", back_populates="operator", uselist=False, foreign_keys=[user_id])
    agent = relationship("AgentModel", back_populates="operator", uselist=False)
>>>>>>> development

class OperatorStatisticsModel(Base):
    __tablename__ = 'operator_statistics'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='operator_statistics_pkey'),
    )

    avg_positive_sentiment: Mapped[int] = mapped_column(Integer, server_default=text('0'))
    avg_negative_sentiment: Mapped[int] = mapped_column(Integer, server_default=text('0'))
    avg_neutral_sentiment: Mapped[int] = mapped_column(Integer, server_default=text('0'))
    total_duration: Mapped[int] = mapped_column(BigInteger, server_default=text('0'))
    call_count: Mapped[int] = mapped_column(BigInteger, server_default=text('0'))
    score: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 2), server_default=text('0.0'))
    avg_customer_satisfaction: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2),server_default=text('0.0'))
    avg_resolution_rate: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2),server_default=text('0.0'))
    avg_response_time: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2), server_default=text('0.0'))
    avg_quality_of_service: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2), server_default=text('0.0'))

    operator = relationship("OperatorModel", back_populates='operator_statistics', uselist=False)