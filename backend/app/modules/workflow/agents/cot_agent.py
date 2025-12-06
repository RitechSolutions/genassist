from typing import Optional, List, Dict, Any
from langchain_core.language_models import BaseChatModel
from app.modules.workflow.agents.memory import ConversationMemory

from app.modules.workflow.agents.agent_utils import (
    create_error_response,
    extract_thought,
    create_success_response,
)

from app.modules.workflow.agents.agent_prompts import (
    create_chain_of_thought_prompt,
    create_conversation_context as build_conversation_context,
)

import logging

logger = logging.getLogger(__name__)


class ChainOfThoughtAgent:
    def __init__(
        self,
        llm_model: BaseChatModel,
        system_prompt: str,
        memory: Optional[ConversationMemory] = None,
        verbose: bool = False,
        max_iterations: int = 5,
    ):
        """Initialize a Chain-of-Thought agent

        Args:
            llm_model: The language model to use for reasoning and decision making
            system_prompt: System prompt that defines the agent's behavior and role
            memory: Optional memory for conversation state management
            verbose: Whether to enable verbose logging of reasoning cycles
            max_iterations: Maximum number of reasoning/action cycles
        """
        self.llm_model = llm_model
        self.system_prompt = system_prompt
        self.memory = memory
        self.verbose = verbose
        self.max_iterations = max_iterations

        logger.info("Chain-of-Thought Agent initialized.")

    async def invoke(
        self, query: str, chat_history: Optional[List] = None
    ) -> Dict[str, Any]:
        """Execute a query using available tools"""
        chat_history = chat_history or []
        result = await self._run_chain_of_thought(query, chat_history)
        return result

    async def stream(self, query: str, chat_history: Optional[List] = None):
        """Stream the agent's tool selection and execution process"""
        try:
            result = await self.invoke(query, chat_history)
            yield result
        except Exception as e:
            logger.error(f"Error streaming Chain-of-Thought query: {str(e)}")
            yield create_error_response(str(e), "ChainOfThoughtAgent")

    async def _run_chain_of_thought(
        self, query: str, chat_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Run the chain-of-thought reasoning cycle with enhanced workflow"""
        logger.info(f"Running Chain-of-Thought for query: {query}")
        context = build_conversation_context(chat_history)
        examples = (
            create_task_specific_cot_examples()
            + create_commonsense_cot_examples()
            + create_math_cot_examples()
        )
        current_prompt = create_chain_of_thought_prompt("", context, query, examples)

        reasoning_steps = []

        for iteration in range(self.max_iterations):
            try:
                response = await self.llm_model.ainvoke(
                    [{"role": "user", "content": current_prompt}]
                )
                response_content = (
                    response.content if hasattr(response, "content") else str(response)
                )

                if self.verbose:
                    logger.info(
                        f"Chain-of-Thought iteration {iteration + 1}: {response_content}"
                    )

                # Record reasoning step
                thought = extract_thought(response_content)
                logger.info(f"Thought extracted: {thought}")
                reasoning_steps.append(
                    {
                        "iteration": iteration + 1,
                        "thought": thought,
                        "full_response": response_content,
                    }
                )

                # Check for Final Answer
                final_answer = response_content
                if final_answer:
                    logger.info(f"Final answer found: {final_answer}")

                    return create_success_response(
                        final_answer,
                        "ChainOfThoughtAgent",
                        iterations=iteration + 1,
                        reasoning_steps=reasoning_steps,
                    )

            except Exception as e:
                logger.error(
                    f"Error in Chain-of-Thought cycle iteration {iteration}: {str(e)}"
                )
                return create_error_response(
                    f"Error in iteration {iteration}: {str(e)}",
                    "ChainOfThoughtAgent",
                    reasoning_steps=reasoning_steps,
                )
        # Max iterations reached
        return create_error_response(
            f"Max iterations ({self.max_iterations}) reached without final answer",
            "ChainOfThoughtAgent",
            reasoning_steps=reasoning_steps,
        )

    def _build_context_from_search_results(
        self, search_results: List[Dict], max_length: int
    ) -> str:
        """
        Build context string from RAG search results.

        Args:
            search_results: List of dicts with 'content' and 'metadata' keys
            max_length: Maximum length of context string

        Returns:
            Formatted context string
        """
        context_parts = []
        current_length = 0
        seen_sources = set()

        for result in search_results:
            content = result["content"]
            metadata = result["metadata"]

            # Extract source information from metadata
            source_name = self._extract_source_name(metadata)

            # Create source header if this is a new source
            if source_name and source_name not in seen_sources:
                doc_info = f"\n--- From: {source_name} ---\n"
                logger.info(f"Adding source header: {doc_info.strip()}")

                # Check if we have room for the header
                if current_length + len(doc_info) > max_length:
                    break

                context_parts.append(doc_info)
                current_length += len(doc_info)
                seen_sources.add(source_name)

            # Add the content with some formatting
            content_text = self._format_content(content, metadata)

            # Check if we have room for this content
            if current_length + len(content_text) > max_length:
                # Try to add a truncated version
                remaining_space = (
                    max_length - current_length - 20
                )  # Leave space for "..."
                if remaining_space > 100:  # Only if we have meaningful space
                    truncated_content = content_text[:remaining_space] + "...\n"
                    context_parts.append(truncated_content)
                break

            context_parts.append(content_text)
            current_length += len(content_text)

            if current_length >= max_length:
                break

        return "".join(context_parts)

    def _extract_source_name(self, metadata: Dict) -> str:
        """Extract a readable source name from metadata."""
        # Check for file name in different possible keys
        logger.info(f"Extracting source name from metadata: {metadata}")
        if "filename" in metadata:
            return metadata["filename"]

        # For chunked messages, try to extract from original message ID
        original_id = metadata.get("original_message_id", "")
        if original_id.startswith("file_"):
            # Extract file ID and create a readable name
            file_id = original_id.replace("file_", "")
            return f"File {file_id}"

        # For regular messages
        if original_id:
            return f"Message {original_id}"

        # Fallback
        return "Unknown Source"

    def _format_content(self, content: str, metadata: Dict) -> str:
        """Format content based on metadata."""
        formatted_content = content.strip()

        # Add chunk information if this is a chunked result
        if metadata.get("is_chunked", False):
            chunk_index = metadata.get("chunk_index", 0)
            total_chunks = metadata.get("total_chunks", 1)
            formatted_content = (
                f"[Chunk {chunk_index + 1}/{total_chunks}] {formatted_content}"
            )

        return f"{formatted_content}\n\n"


# Example usage with few-shot examples
def create_math_cot_examples() -> List[Dict[str, str]]:
    """Create examples for math word problems"""
    return [
        {
            "question": "Roger has 5 tennis balls. He buys 2 more cans of tennis balls. Each can has 3 tennis balls. How many tennis balls does he have now?",
            "reasoning": "Roger started with 5 balls. 2 cans of 3 tennis balls each is 6 tennis balls. 5 + 6 = 11.",
            "answer": "The answer is 11.",
        },
        {
            "question": "How many keystrokes are needed to type the numbers from 1 to 500?",
            "reasoning": "There are 9 one-digit numbers from 1 to 9. There are 90 two-digit numbers from 10 to 99. There are 401 three-digit numbers from 100 to 500. 9 + 90(2) + 401(3) = 1392.",
            "answer": "The answer is 1392.",
        },
    ]


def create_commonsense_cot_examples() -> List[Dict[str, str]]:
    """Create examples for commonsense reasoning"""
    return [
        {
            "question": "Sammy wanted to go to where the people were \n"
            "Options: (a) race track (b) populated areas \n"
            "(c) desert (d) apartment (e) roadblock. Where might he go?",
            "reasoning": "The answer must be a place with a lot of people. Race tracks, desert, apartments, and roadblocks don't have a lot of people, but populated areas do.",
            "answer": "So the answer is (b) populated areas.",
        },
        {
            "question": "Would a pear sink in water?",
            "reasoning": "The density of a pear is about 0.6 g/cm³, which is less than water. Thus, a pear would float.",
            "answer": "So the answer is no.",
        },
    ]


def create_task_specific_cot_examples() -> List[Dict[str, str]]:
    """Create examples for instruction-following tasks"""
    return [
        {
            "question": "Take the last letters of the words in 'Lady Gaga' and concatenate them.",
            "reasoning": "The last letter of 'Lady' is 'y'. The last letter of 'Gaga' is 'a'. Concatenating them is 'ya'.",
            "answer": "So the answer is ya.",
        },
        {
            "question": "A coin is heads up. Maybelle flips the coin. Shalonda does not flip the coin. Is the coin still heads up?",
            "reasoning": "The coin was flipped by Maybelle. So the coin was flipped 1 time, which is an odd number. The coin started heads up, so after an odd number of flips, it will be tails up.",
            "answer": "So the answer is no.",
        },
    ]
