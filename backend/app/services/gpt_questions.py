import logging
from langchain.schema import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.config.settings import settings

import opik
# from opik.integrations.openai import track_openai
from opik import track
from opik.integrations.langchain import OpikTracer
import os
from dotenv import load_dotenv


logger = logging.getLogger(__name__)

load_dotenv()
USE_OPIK = os.getenv("USE_OPIK", "false").lower() == "true"

class QuestionAnswerer:
    def __init__(self, llm_model: str = settings.DEFAULT_OPEN_AI_GPT_MODEL, temperature: float = 0.0):
        self.llm_model = llm_model
        self.temperature = temperature
        if USE_OPIK:
            self.opik_tracer = OpikTracer()
            self.llm = ChatOpenAI(model=llm_model, temperature=temperature, stream_usage=True, callbacks=[self.opik_tracer])
        else:
            self.llm = ChatOpenAI(model=llm_model, temperature=temperature)
        logger.debug(f"Initialized TranscriptQuestionAnswerer with model: {llm_model}")
    
    def answer_question(self, transcript_json: str, question: str) -> str:

        prompt = f"""
        You are an AI assistant. You have been provided with a JSON transcript of a conversation between a customer and an agent.
        Use this transcript to answer the question accurately.

        Answer the question based on the transcript. If the question is not about the transcript or related to the 
        conversation, answer with this :'This question is not allowed, please contact an administrator'.
        The answer should always be in plain text and not as a json structure.

        Transcript:
        {transcript_json}

        Question:
        {question}

        Answer:
        """

        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a helpful assistant."),
                HumanMessage(content=prompt)
            ])
            return response.content.strip()
        except Exception as e:
            logger.error(f"Error while calling ChatGPT for question answering: {e}")
            raise AppException(error_key=ErrorKey.GPT_TRANSCRIPT_QUESTION_ERROR)


# Conditionally assign the method after class definition
if USE_OPIK:
    QuestionAnswerer.answer_question = track(QuestionAnswerer.answer_question)
else:
    QuestionAnswerer.answer_question = QuestionAnswerer.answer_question