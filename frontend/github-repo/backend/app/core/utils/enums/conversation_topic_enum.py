from enum import Enum


class ConversationTopic(Enum):
    PRODUCT_INQUIRY = "Product Inquiry"
    TECHNICAL_SUPPORT = "Technical Support"
    BILLING_QUESTIONS = "Billing Questions"
    OTHER = "Other"


    @classmethod
    def as_csv(cls) -> str:
        return ", ".join(topic.value for topic in cls)