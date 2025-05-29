from dataclasses import dataclass
<<<<<<< HEAD
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional
=======
>>>>>>> development
from datetime import datetime
from typing import List, Optional
from uuid import UUID

<<<<<<< HEAD

=======
from pydantic import BaseModel, ConfigDict


>>>>>>> development
# class TranscriptSegment(BaseModel):
#     start_time: float
#     speaker: str
#     text: str
#     end_time: float = 0.0
@dataclass
class TranscriptSegment:
    start_time: float
    speaker: str
    text: str
    end_time: float = 0.0
    
class TranscriptSegmentInput(BaseModel):
    create_time: Optional[datetime] = None
    start_time: float
    end_time: float
    speaker: str
    text: str
<<<<<<< HEAD
=======
    type: Optional[str] = "message"

    model_config = ConfigDict(
            from_attributes=True,
            )
>>>>>>> development
    


class ConversationTranscriptBase(BaseModel):
    messages: List[TranscriptSegmentInput]
    operator_id: UUID
    data_source_id: UUID
    customer_id: Optional[UUID] = None
    llm_analyst_id: Optional[UUID] = None
    recorded_at: Optional[datetime]

class ConversationTranscriptCreate(ConversationTranscriptBase):
    operator_id: Optional[UUID] = None

class InProgConvTranscrUpdate(BaseModel):
    """
    Model for updating an existing in-progress conversation
    by adding more transcript chunks.
    """
    messages: List[TranscriptSegmentInput]
    llm_analyst_id: Optional[UUID] = None

class InProgressConversationTranscriptFinalize(BaseModel):
    llm_analyst_id: Optional[UUID] = None


