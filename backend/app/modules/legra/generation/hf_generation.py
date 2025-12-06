from typing import Any

from transformers import AutoModelForCausalLM, AutoTokenizer

from .base import Generator

__all__ = [
    'HuggingFaceGenerator',
]


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

        # Tokenize
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.truncate_context_size or self.tokenizer.model_max_length,
        ).to(self.device)

        # Generate
        out = self.model.generate(
            **inputs,
            max_length=inputs["input_ids"].shape[1] + kwargs.get("max_new_tokens", 50),
            temperature=temperature,
            top_p=top_p,
            do_sample=do_sample,
            pad_token_id=self.tokenizer.eos_token_id,
        )

        generated = self.tokenizer.decode(out[0], skip_special_tokens=True)

        # Strip the prompt from the output
        return generated.strip()
