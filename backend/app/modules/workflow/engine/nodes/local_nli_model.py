"""
Lightweight local NLI model used by GuardrailNliNode.

This module avoids calling provider LLMs by loading a small,
dedicated NLI classifier (e.g. a HuggingFace model) locally.

If the transformers stack is not available at runtime, the model
falls back to a simple heuristic implementation.
"""

from __future__ import annotations

from typing import Tuple, Optional
import logging

from app.constants import NLI_MODELS, DEFAULT_NLI_MODEL

logger = logging.getLogger(__name__)


class LocalNLIModel:
    """
    Local NLI model wrapper.

    Prefer to keep this class self-contained so it can be replaced later
    with a more efficient or project-specific implementation without
    changing node logic.
    """

    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None
        self._loaded_model_name: Optional[str] = None

    def _lazy_init(self, model_name: str) -> None:
        """Lazily load a small NLI model if transformers is available."""
        if self._loaded_model_name == model_name and self._model is not None:
            return

        try:
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )  # type: ignore

            logger.info("Loading local NLI model: %s", model_name)
            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
            )
            self._loaded_model_name = model_name
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "LocalNLIModel: transformers-based model unavailable, "
                "falling back to heuristic NLI. Error: %s",
                exc,
            )
            self._model = None
            self._tokenizer = None
            self._loaded_model_name = None

    def score(
        self,
        answer: str,
        evidence: str,
        model_name: Optional[str] = None,
    ) -> Tuple[float, float, str]:
        """
        Compute entailment and contradiction scores and a discrete verdict.

        Returns:
            (entail_score, contradiction_score, verdict)
        """
        # Normalize/validate model_name against known options
        selected_model = model_name or DEFAULT_NLI_MODEL
        allowed_values = {m["value"] for m in NLI_MODELS}
        if selected_model not in allowed_values:
            logger.warning(
                "LocalNLIModel: requested model '%s' is not in allowed NLI_MODELS, "
                "falling back to default '%s'",
                selected_model,
                DEFAULT_NLI_MODEL,
            )
            selected_model = DEFAULT_NLI_MODEL

        # Try to use a real model first
        self._lazy_init(selected_model)

        if self._model is not None and self._tokenizer is not None:
            try:
                from torch.nn.functional import softmax  # type: ignore
                import torch  # type: ignore

                inputs = self._tokenizer(
                    evidence,
                    answer,
                    return_tensors="pt",
                    truncation=True,
                    max_length=256,
                )
                with torch.no_grad():
                    logits = self._model(**inputs).logits[0]
                probs = softmax(logits, dim=-1).tolist()

                # Map logits to labels using the model's id2label mapping
                id2label = getattr(self._model.config, "id2label", {})
                label_map = {
                    idx: str(label).lower() for idx, label in id2label.items()
                }

                entail_idx = None
                contradict_idx = None
                for idx, label in label_map.items():
                    if entail_idx is None and "entail" in label:
                        entail_idx = idx
                    if contradict_idx is None and "contradict" in label:
                        contradict_idx = idx

                # Fallback to a common order if labels are missing
                if entail_idx is None:
                    entail_idx = 2 if len(probs) > 2 else 0
                if contradict_idx is None:
                    contradict_idx = 0

                entail_score = float(probs[entail_idx])
                contradiction_score = float(probs[contradict_idx])

                if entail_score >= 0.5:
                    verdict = "entails"
                elif contradiction_score >= 0.5:
                    verdict = "contradicts"
                else:
                    verdict = "unknown"

                return entail_score, contradiction_score, verdict

            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "LocalNLIModel: model inference failed, "
                    "falling back to heuristic NLI. Error: %s",
                    exc,
                )

        # Fallback: heuristic overlap-based NLI
        return self._heuristic_nli(answer, evidence)

    def _heuristic_nli(
        self,
        answer: str,
        evidence: str,
    ) -> Tuple[float, float, str]:
        """
        Very small heuristic NLI:
        - entailment proportional to token overlap
        - contradiction boosted when negation cues appear.
        """
        if not answer or not evidence:
            return 0.0, 0.0, "unknown"

        answer_tokens = {t.lower() for t in answer.split() if len(t) > 3}
        evidence_tokens = {t.lower() for t in evidence.split() if len(t) > 3}

        if not answer_tokens:
            return 0.0, 0.0, "unknown"

        overlap = answer_tokens & evidence_tokens
        entail_score = len(overlap) / float(len(answer_tokens))

        contradiction_cues = {"not", "no", "never", "none", "cannot", "n't"}
        has_negation = any(cue in answer.lower() for cue in contradiction_cues) or any(
            cue in evidence.lower() for cue in contradiction_cues
        )

        contradiction_score = 0.0
        if has_negation and entail_score < 0.5:
            contradiction_score = min(1.0, 0.5 + (0.5 - entail_score))

        if entail_score >= 0.5:
            verdict = "entails"
        elif contradiction_score >= 0.5:
            verdict = "contradicts"
        else:
            verdict = "unknown"

        return entail_score, contradiction_score, verdict


# Singleton instance reused across node executions
local_nli_model = LocalNLIModel()
