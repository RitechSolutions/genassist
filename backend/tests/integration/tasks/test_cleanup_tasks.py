import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import json
from sqlalchemy import text

from app.core.utils.enums.conversation_type_enum import ConversationType
from app.core.utils.enums.transcript_message_type import TranscriptMessageType
from app.db.models.conversation import ConversationAnalysisModel, ConversationModel
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.db.session import get_db
from app.tasks.tasks import cleanup_stale_conversations_async
from app.db.seed.seed_data_config import seed_test_data
from sqlalchemy.ext.asyncio import AsyncSession


async def create_test_conversations(db_session: AsyncSession):
    """Create test conversations in different states."""
    conversations = []
    
    # Create a conversation that should be deleted (less than 3 messages)
    short_conv = ConversationModel(
        id=uuid4(),
        operator_id=seed_test_data.operator_id,
        data_source_id=seed_test_data.data_source_id,
        status=ConversationStatus.IN_PROGRESS.value,
        conversation_type=ConversationType.PROGRESSIVE.value,
        transcription=json.dumps([
            {"speaker": "agent", "text": "Hello", "type": TranscriptMessageType.MESSAGE.value},
            {"speaker": "customer", "text": "Hi", "type": TranscriptMessageType.MESSAGE.value}
        ]),
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=10)
    )
    db_session.add(short_conv)
    conversations.append(short_conv)
    
    # Create a conversation that should be finalized (more than 3 messages)
    long_conv = ConversationModel(
        id=uuid4(),
        operator_id=seed_test_data.operator_id,
        data_source_id=seed_test_data.data_source_id,
        status=ConversationStatus.IN_PROGRESS.value,
        conversation_type=ConversationType.PROGRESSIVE.value,
        transcription=json.dumps([
            {"speaker": "agent", "text": "Hello", "type": TranscriptMessageType.MESSAGE.value},
            {"speaker": "customer", "text": "Hi", "type": TranscriptMessageType.MESSAGE.value},
            {"speaker": "agent", "text": "How can I help?", "type": TranscriptMessageType.MESSAGE.value},
            {"speaker": "customer", "text": "I have a question", "type": TranscriptMessageType.MESSAGE.value}
        ]),
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=10)
    )
    db_session.add(long_conv)
    conversations.append(long_conv)
    
    # Create a conversation that should not be affected (recently updated)
    recent_conv = ConversationModel(
        id=uuid4(),
        operator_id=seed_test_data.operator_id,
        data_source_id=seed_test_data.data_source_id,
        status=ConversationStatus.IN_PROGRESS.value,
        conversation_type=ConversationType.PROGRESSIVE.value,
        transcription=json.dumps([
            {"speaker": "agent", "text": "Hello", "type": TranscriptMessageType.MESSAGE.value},
            {"speaker": "customer", "text": "Hi", "type": TranscriptMessageType.MESSAGE.value}
        ]),
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=2)
    )
    db_session.add(recent_conv)
    conversations.append(recent_conv)
    
    # Create a conversation that should not be affected (already finalized)
    finalized_conv = ConversationModel(
        id=uuid4(),
        operator_id=seed_test_data.operator_id,
        data_source_id=seed_test_data.data_source_id,
        status=ConversationStatus.FINALIZED.value,
        conversation_type=ConversationType.PROGRESSIVE.value,
        transcription=json.dumps([
            {"speaker": "agent", "text": "Hello", "type": TranscriptMessageType.MESSAGE.value},
            {"speaker": "customer", "text": "Hi", "type": TranscriptMessageType.MESSAGE.value}
        ]),
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=10)
    )
    db_session.add(finalized_conv)
    conversations.append(finalized_conv)
    print(f"Conversations added: {conversations}")
    await db_session.commit()
    
    return conversations

@pytest.mark.asyncio(scope="session")
async def test_cleanup_stale_conversations(async_db_session: AsyncSession):
    """Test the cleanup_stale_conversations task."""
    
    test_conversations = await create_test_conversations(async_db_session)
    
    # Run the cleanup task
    result = await cleanup_stale_conversations_async(async_db_session)
    
    # Verify the results
    assert result["deleted_count"] >= 1  # Only the short conversation should be deleted
    assert result["finalized_count"] >= 1  # The long conversation should be finalized
    assert "failed_count" in result
    
    await verify_conversation_cleanup(async_db_session, test_conversations)
    
    print(f"Test completed with result: {result}")

async def verify_conversation_cleanup(db: AsyncSession, test_conversations):
    # For the short conversation that should be deleted, verify it's gone
    print(f"Test short conversation deleted: {test_conversations[0].id}")
    short_conv = await db.get(ConversationModel, test_conversations[0].id)
    assert short_conv is None
    
    # For the long conversation that should be finalized
    print(f"Test long conversation not deleted: {test_conversations[1].id}")
    long_conv = await db.get(ConversationModel, test_conversations[1].id)
    assert long_conv is not None
    assert long_conv.status == ConversationStatus.FINALIZED.value
    
    # Delete analysis records first
    await db.execute(
        text("DELETE FROM conversation_analysis WHERE conversation_id = :conv_id"),
        {"conv_id": str(long_conv.id)}
    )
    await db.delete(long_conv)
    await db.commit()

    # For the recent conversation that should be unchanged
    print(f"Test recent conversation not deleted: {test_conversations[2].id}")
    recent_conv = await db.get(ConversationModel, test_conversations[2].id)
    assert recent_conv is not None
    assert recent_conv.status == ConversationStatus.IN_PROGRESS.value
    await db.delete(recent_conv)
    await db.commit()
    
    # For the finalized conversation that should be unchanged
    print(f"Test finalized conversation not deleted: {test_conversations[3].id}")
    finalized_conv = await db.get(ConversationModel, test_conversations[3].id)
    assert finalized_conv is not None
    assert finalized_conv.status == ConversationStatus.FINALIZED.value 

    # Delete analysis records first
    await db.execute(
        text("DELETE FROM conversation_analysis WHERE conversation_id = :conv_id"),
        {"conv_id": str(finalized_conv.id)}
    )
    await db.delete(finalized_conv)
    await db.commit()