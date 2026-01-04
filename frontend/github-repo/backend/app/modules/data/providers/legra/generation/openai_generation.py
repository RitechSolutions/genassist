from typing import Any

import openai

from .base import Generator

__all__ = [
    'OpenAIGenerator',
]


class OpenAIGenerator(Generator):
    """
    Text generation through the OpenAI ChatCompletion API.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
    ) -> None:
        openai.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature

    def generate(self, query: str, context: str = "", **kwargs: Any) -> str:
        """
        Send a ChatCompletion request with system prompt = context; user message
        = query.
        """
        messages = [
            {"role": "system", "content": context},
            {"role": "user", "content": query},
        ]

        response = openai.ChatCompletion.create(
            model=self.model_name,
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", 256),
        )

        return response.choices[0].message.content.strip()
