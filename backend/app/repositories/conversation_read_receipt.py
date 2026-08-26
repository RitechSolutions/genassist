from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from injector import inject
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.base import generate_sequential_uuid
from app.db.models.conversation_read_receipt import ConversationReadReceiptModel
from app.repositories.db_repository import DbRepository


@inject
class ConversationReadReceiptRepository(DbRepository[ConversationReadReceiptModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(ConversationReadReceiptModel, db)

    async def get_by_conversation(
        self, conversation_id: UUID
    ) -> List[ConversationReadReceiptModel]:
        """All read markers for a conversation (at most one per reader role)."""
        result = await self.db.execute(
            select(ConversationReadReceiptModel).where(
                ConversationReadReceiptModel.conversation_id == conversation_id
            )
        )
        return list(result.scalars().all())

    async def advance_read_marker(
        self,
        *,
        conversation_id: UUID,
        reader_role: str,
        reader_user_id: Optional[UUID],
        last_read_sequence: int,
    ) -> None:
        """Upsert the ``(conversation, reader_role)`` marker, advancing only.

        Implemented as a single Postgres ``INSERT ... ON CONFLICT DO UPDATE`` so
        concurrent reads for the same reader can't violate the unique constraint,
        and the ``WHERE`` clause enforces monotonicity: the stored sequence is
        never moved backwards. Caller re-reads the state afterwards.
        """
        now = datetime.now(timezone.utc)
        table = ConversationReadReceiptModel.__table__
        stmt = (
            pg_insert(table)
            .values(
                id=generate_sequential_uuid(),
                conversation_id=conversation_id,
                reader_role=reader_role,
                reader_user_id=reader_user_id,
                last_read_sequence=last_read_sequence,
                last_read_at=now,
                is_deleted=0,
            )
            .on_conflict_do_update(
                constraint="uq_conversation_read_receipts_conversation_role",
                set_={
                    "last_read_sequence": last_read_sequence,
                    "last_read_at": now,
                    "reader_user_id": reader_user_id,
                    "updated_at": now,
                },
                where=table.c.last_read_sequence < last_read_sequence,
            )
        )
        await self.db.execute(stmt)
        await self.db.flush()
