from pydantic import BaseModel


class TopicOption(BaseModel):
    name: str
    subtopics: list[str]


class TopicOptionsRead(BaseModel):
    topics: list[TopicOption]
