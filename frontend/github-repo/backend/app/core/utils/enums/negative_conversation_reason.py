from enum import Enum


class NegativeConversationReason(Enum):
    BAD_COMMUNICATION = "Bad Communication"
    FRUSTRATED_CUSTOMER = "Frustrated Customer"
    BAD_WORDS_USED = "Bad Words Used"
    OTHER = "Other"


    @classmethod
    def as_csv(cls) -> str:
        return ", ".join(topic.value for topic in cls)