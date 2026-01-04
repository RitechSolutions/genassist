from typing import Any
import logging
from transformers import AutoModelForCausalLM, AutoTokenizer

from .base import Generator

__all__ = [
    'HuggingFaceGenerator',
]
logger = logging.getLogger(__name__)

class HuggingFaceGenerator(Generator):
    """
    Text generation using a HuggingFace-transformers causal model.
    """

    def __init__(
        self,
        model_name: str = "gpt2",
        device: str = "cpu",
        truncate_context_size: int | None = None,
    ) -> None:
        """
        Args:
            - model_name: Name of HF model (e.g., 'gpt2', 'EleutherAI/gpt-j-6B',
              etc.)
            - device: 'cpu' or 'cuda'
            - truncate_context_size: If not None, truncate context to this many
              tokens.
        """
        self.model_name = model_name
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name).to(device)
        self.truncate_context_size = truncate_context_size


    def generate(
            self,
            query: str,
            context: str | None = None,
            temperature: float = 0.7,
            top_p: float = 0.9,
            do_sample: bool = True,
            **kwargs: Any,
            ) -> str:
        """
        Concatenate context + query, pass through LM, and return generated text.
        """
        # Build prompt
        if context is not None:
            prompt = f"Address the user query: '{query}', given the context: {context}."
        else:
            prompt = query

        # Get model's ACTUAL limit
        model_max_length = self.model.config.max_position_embeddings
        max_new_tokens = kwargs.get("max_new_tokens", 50)
        safe_input_length = model_max_length - max_new_tokens - 10

        # Check if truncation will occur
        original_tokens = self.tokenizer.encode(prompt, add_special_tokens=True)
        original_length = len(original_tokens)

        if original_length > safe_input_length:
            tokens_removed = original_length - safe_input_length
            logger.warning(
                    f"Context truncated: {original_length} → {safe_input_length} tokens "
                    f"({tokens_removed} tokens removed, {tokens_removed / original_length * 100:.1f}%)"
                    )

        # Force truncation to safe length
        inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=safe_input_length,
                ).to(self.device)

        input_length = inputs["input_ids"].shape[1]

        # Generate
        out = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=do_sample,
                pad_token_id=self.tokenizer.eos_token_id,
                )

        generated = self.tokenizer.decode(
                out[0][input_length:],
                skip_special_tokens=True
                )

        return generated.strip()
