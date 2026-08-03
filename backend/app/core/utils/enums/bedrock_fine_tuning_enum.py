import enum


class BedrockJobStatus(str, enum.Enum):
    """Status of a Bedrock model customization (fine-tuning) job.

    Values mirror the states returned by Bedrock's
    GetModelCustomizationJob API (``status`` field).
    """

    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"
    FAILED = "Failed"
    STOPPING = "Stopping"
    STOPPED = "Stopped"


class BedrockDeploymentStatus(str, enum.Enum):
    """Status of an on-demand custom model deployment for Nova models.

    Mirrors the states returned by GetCustomModelDeployment (``status``).
    """

    NOT_DEPLOYED = "NotDeployed"
    CREATING = "Creating"
    ACTIVE = "Active"
    FAILED = "Failed"