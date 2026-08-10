"""Evaluation-only local NLI scoring.

This module owns the claim splitting, evidence chunking, model state, and
inference lock used by the NLI evaluation method. Workflow guardrails do not
import it and keep their independent production scoring path.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from app.constants import DEFAULT_NLI_MODEL, NLI_MODELS

logger = logging.getLogger(__name__)

NLI_MAX_SEQUENCE_LENGTH = 256
NLI_CHUNK_OVERLAP = 32
NLI_MAX_EVIDENCE_CHUNKS = 32
NLI_INFERENCE_BATCH_SIZE = 4
NLI_MAX_CLAIM_TOKENS = 96
NLI_MAX_ANSWER_CLAIMS = 8


@dataclass(frozen=True)
class NLIClaimResult:
    """NLI outcome for one bounded section of an answer."""

    text: str
    entail_score: float
    contradiction_score: float
    verdict: str


@dataclass(frozen=True)
class NLIScoreResult:
    """Detailed NLI outcome used by the evaluation result formatter."""

    entail_score: float
    contradiction_score: float
    verdict: str
    model_name: Optional[str]
    chunks_evaluated: int = 0
    evidence_truncated: bool = False
    claims_evaluated: int = 0
    total_claims: int = 0
    pairs_evaluated: int = 0
    coverage_complete: bool = True
    claim_results: tuple[NLIClaimResult, ...] = ()


class EvaluationNLIModel:
    """Local NLI model used only by the evaluation worker."""

    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None
        self._loaded_model_name: Optional[str] = None
        # A timed-out to_thread call continues running. Serialize evaluation
        # inference so it cannot race with a following evaluation call.
        self._lock = threading.Lock()

    def _lazy_init(self, model_name: str) -> bool:
        """Load the requested NLI model once for this evaluation process."""
        if self._loaded_model_name == model_name and self._model is not None:
            return True

        try:
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )  # type: ignore

            logger.info("Loading evaluation NLI model: %s", model_name)
            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
            )
            self._loaded_model_name = model_name
            return True
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "EvaluationNLIModel: transformers model unavailable. Error: %s",
                exc,
            )
            self._model = None
            self._tokenizer = None
            self._loaded_model_name = None
            return False

    @staticmethod
    def _resolve_model_name(model_name: Optional[str]) -> str:
        """Normalize a requested model name against the supported NLI models."""
        selected_model = model_name or DEFAULT_NLI_MODEL
        allowed_values = {model["value"] for model in NLI_MODELS}
        if selected_model not in allowed_values:
            logger.warning(
                "EvaluationNLIModel: requested model '%s' is unsupported; "
                "using default '%s'",
                selected_model,
                DEFAULT_NLI_MODEL,
            )
            selected_model = DEFAULT_NLI_MODEL
        return selected_model

    @staticmethod
    def _entail_contradict_indices(
        id2label: Any,
        label_count: int,
    ) -> Tuple[int, int]:
        """Find entailment and contradiction output indices."""
        label_map = {
            int(index): str(label).lower()
            for index, label in (id2label or {}).items()
        }
        entail_index = None
        contradiction_index = None
        for index, label in label_map.items():
            if entail_index is None and "entail" in label:
                entail_index = index
            if contradiction_index is None and "contradict" in label:
                contradiction_index = index

        if entail_index is None:
            entail_index = 2 if label_count > 2 else 0
        if contradiction_index is None:
            contradiction_index = 0
        return entail_index, contradiction_index

    def score_evidence(
        self,
        answer: str,
        evidence: str,
        model_name: Optional[str] = None,
    ) -> NLIScoreResult:
        """Score every bounded answer claim against bounded evidence chunks."""
        if not answer.strip() or not evidence.strip():
            return NLIScoreResult(
                entail_score=0.0,
                contradiction_score=0.0,
                verdict="unknown",
                model_name=None,
            )

        selected_model = self._resolve_model_name(model_name)
        with self._lock:
            loaded = self._lazy_init(selected_model)
            if loaded and self._model is not None and self._tokenizer is not None:
                try:
                    return self._score_evidence_with_model(
                        answer,
                        evidence,
                        selected_model,
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    logger.warning(
                        "EvaluationNLIModel: inference failed. Error: %s",
                        exc,
                    )

        # The evaluator treats model_name=None as an evaluator error. Returning
        # heuristic numbers preserves diagnostic information without grading on it.
        entail_score, contradiction_score, verdict = self._heuristic_nli(
            answer,
            evidence,
        )
        return NLIScoreResult(
            entail_score=entail_score,
            contradiction_score=contradiction_score,
            verdict=verdict,
            model_name=None,
        )

    def _score_evidence_with_model(
        self,
        answer: str,
        evidence: str,
        selected_model: str,
    ) -> NLIScoreResult:
        """Run chunked inference while the evaluation-only lock is held."""
        import torch  # type: ignore
        from torch.nn.functional import softmax  # type: ignore

        claim_token_chunks, total_claims = self._answer_claim_token_ids(answer)
        if not claim_token_chunks:
            return NLIScoreResult(
                entail_score=0.0,
                contradiction_score=0.0,
                verdict="unknown",
                model_name=None,
            )
        if total_claims > NLI_MAX_ANSWER_CLAIMS:
            return NLIScoreResult(
                entail_score=0.0,
                contradiction_score=0.0,
                verdict="unknown",
                model_name=None,
                total_claims=total_claims,
                coverage_complete=False,
            )

        claim_texts = [
            self._tokenizer.decode(chunk, skip_special_tokens=True)
            for chunk in claim_token_chunks
        ]
        special_tokens = self._tokenizer.num_special_tokens_to_add(pair=True)
        evidence_window = max(
            32,
            NLI_MAX_SEQUENCE_LENGTH
            - max(len(chunk) for chunk in claim_token_chunks)
            - special_tokens,
        )
        evidence_ids = self._tokenizer.encode(
            evidence,
            add_special_tokens=False,
        )
        evidence_chunks, evidence_truncated = self._chunk_token_ids(
            evidence_ids,
            evidence_window,
            NLI_CHUNK_OVERLAP,
            NLI_MAX_EVIDENCE_CHUNKS,
        )
        chunk_texts = [
            self._tokenizer.decode(chunk, skip_special_tokens=True)
            for chunk in evidence_chunks
        ]

        pair_evidence_texts = chunk_texts * len(claim_texts)
        pair_claim_texts = [
            claim_text
            for claim_text in claim_texts
            for _ in chunk_texts
        ]
        probabilities = []
        for batch_start in range(
            0,
            len(pair_evidence_texts),
            NLI_INFERENCE_BATCH_SIZE,
        ):
            evidence_batch = pair_evidence_texts[
                batch_start : batch_start + NLI_INFERENCE_BATCH_SIZE
            ]
            claim_batch = pair_claim_texts[
                batch_start : batch_start + NLI_INFERENCE_BATCH_SIZE
            ]
            inputs = self._tokenizer(
                evidence_batch,
                claim_batch,
                return_tensors="pt",
                padding=True,
                truncation="only_first",
                max_length=NLI_MAX_SEQUENCE_LENGTH,
            )
            with torch.no_grad():
                logits = self._model(**inputs).logits
            probabilities.extend(softmax(logits, dim=-1).tolist())

        entail_index, contradiction_index = self._entail_contradict_indices(
            getattr(self._model.config, "id2label", {}),
            len(probabilities[0]),
        )

        claim_results = []
        evidence_chunk_count = len(chunk_texts)
        for claim_index, claim_text in enumerate(claim_texts):
            first_pair = claim_index * evidence_chunk_count
            claim_probabilities = probabilities[
                first_pair : first_pair + evidence_chunk_count
            ]
            claim_entail_score = max(
                float(probability[entail_index])
                for probability in claim_probabilities
            )
            claim_contradiction_score = max(
                float(probability[contradiction_index])
                for probability in claim_probabilities
            )
            if claim_entail_score >= 0.5:
                claim_verdict = "entails"
            elif claim_contradiction_score >= 0.5:
                claim_verdict = "contradicts"
            else:
                claim_verdict = "unknown"
            claim_results.append(
                NLIClaimResult(
                    text=claim_text,
                    entail_score=claim_entail_score,
                    contradiction_score=claim_contradiction_score,
                    verdict=claim_verdict,
                )
            )

        entail_score = min(result.entail_score for result in claim_results)
        contradiction_score = max(
            result.contradiction_score for result in claim_results
        )
        if all(result.entail_score >= 0.5 for result in claim_results):
            verdict = "entails"
        elif any(
            result.contradiction_score >= 0.5 for result in claim_results
        ):
            verdict = "contradicts"
        else:
            verdict = "unknown"

        return NLIScoreResult(
            entail_score=entail_score,
            contradiction_score=contradiction_score,
            verdict=verdict,
            model_name=selected_model,
            chunks_evaluated=len(evidence_chunks),
            evidence_truncated=evidence_truncated,
            claims_evaluated=len(claim_results),
            total_claims=total_claims,
            pairs_evaluated=len(probabilities),
            claim_results=tuple(claim_results),
        )

    def _answer_claim_token_ids(
        self,
        answer: str,
    ) -> tuple[list[list[int]], int]:
        """Group complete sentences into bounded claim-sized token windows."""
        sentence_parts = re.split(r"(?<=[.!?])\s+|\n+", answer)
        claim_chunks: list[list[int]] = []
        current_chunk: list[int] = []

        for sentence in sentence_parts:
            sentence = sentence.strip()
            if not sentence:
                continue
            sentence_ids = self._tokenizer.encode(
                sentence,
                add_special_tokens=False,
            )
            if not sentence_ids:
                continue

            if len(sentence_ids) > NLI_MAX_CLAIM_TOKENS:
                if current_chunk:
                    claim_chunks.append(current_chunk)
                    current_chunk = []
                claim_chunks.extend(
                    sentence_ids[start : start + NLI_MAX_CLAIM_TOKENS]
                    for start in range(
                        0,
                        len(sentence_ids),
                        NLI_MAX_CLAIM_TOKENS,
                    )
                )
                continue

            if (
                current_chunk
                and len(current_chunk) + len(sentence_ids)
                > NLI_MAX_CLAIM_TOKENS
            ):
                claim_chunks.append(current_chunk)
                current_chunk = []
            current_chunk.extend(sentence_ids)

        if current_chunk:
            claim_chunks.append(current_chunk)

        return claim_chunks, len(claim_chunks)

    @staticmethod
    def _chunk_token_ids(
        token_ids: list[int],
        window_size: int,
        overlap: int,
        max_chunks: int,
    ) -> tuple[list[list[int]], bool]:
        """Split evidence into bounded overlapping chunks, including its end."""
        if not token_ids:
            return [[]], False

        window_size = max(1, window_size)
        overlap = max(0, min(overlap, window_size - 1))
        step = max(1, window_size - overlap)
        final_start = max(0, len(token_ids) - window_size)
        starts = list(range(0, final_start + 1, step))
        if starts[-1] != final_start:
            starts.append(final_start)

        was_bounded = len(starts) > max_chunks
        if was_bounded:
            if max_chunks <= 1:
                starts = [final_start]
            else:
                last_index = len(starts) - 1
                starts = [
                    starts[round(index * last_index / (max_chunks - 1))]
                    for index in range(max_chunks)
                ]

        chunks = [token_ids[start : start + window_size] for start in starts]
        return chunks, was_bounded

    @staticmethod
    def _heuristic_nli(
        answer: str,
        evidence: str,
    ) -> Tuple[float, float, str]:
        """Return diagnostic overlap scores when the real model is unavailable."""
        if not answer or not evidence:
            return 0.0, 0.0, "unknown"

        answer_tokens = {token.lower() for token in answer.split() if len(token) > 3}
        evidence_tokens = {
            token.lower() for token in evidence.split() if len(token) > 3
        }
        if not answer_tokens:
            return 0.0, 0.0, "unknown"

        overlap = answer_tokens & evidence_tokens
        entail_score = len(overlap) / float(len(answer_tokens))
        contradiction_cues = {"not", "no", "never", "none", "cannot", "n't"}
        has_negation = any(
            cue in answer.lower() for cue in contradiction_cues
        ) or any(cue in evidence.lower() for cue in contradiction_cues)

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


evaluation_nli_model = EvaluationNLIModel()
