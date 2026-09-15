"""Which evaluator techniques an isolated prompt check may run, the exact
configuration each one receives, and what each makes of a case's expectation"""

from typing import Any, Dict, List

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.prompt_editor import PromptTechniqueConfigs

PROMPT_CHECK_TECHNIQUES: tuple[str, ...] = (
    "exact_match",
    "contains",
    "not_contains",
    "json_match",
    "field_equals",
    "nli_eval",
)

# Graded from an execution trace the isolated check never produces
_TRACE_TECHNIQUES = ("no_errors", "tool_used", "route_taken", "action_taken")

# Real evaluators, held back until the editor can bound and meter their own model calls
_DEFERRED_TECHNIQUES = ("llm_judge", "provenance_eval")

_NLI_CONFIG = {"evidence_source": "expected_output"}

# Techniques whose configuration the request may carry, in PromptTechniqueConfigs order
_CONFIGURABLE = ("not_contains", "field_equals")

# Per-technique expected_output semantics for optimizer (so not all treated as ideal).
# Follows PROMPT_CHECK_TECHNIQUES order. Omits not_contains and field_equals
_EXPECTATION_RULES: Dict[str, str] = {
    "exact_match": (
        "the reply must be exactly the expected text, same characters and same case. "
        "Only leading and trailing whitespace is ignored"
    ),
    "contains": (
        "the expected text must appear somewhere in the reply, case-insensitively. "
        "It is a required fragment, not the whole reply, and the rest is unconstrained"
    ),
    "json_match": (
        "the whole reply must be one JSON object that is deep-equal to the expected "
        "object: same keys, same values, nothing extra"
    ),
    "nli_eval": (
        "the expected text is evidence, not a target reply: every claim the reply "
        "makes must be supported by it. Say nothing the expected text does not back up"
    ),
}


def _unsupported(detail: str) -> AppException:
    return AppException(
        status_code=400,
        error_key=ErrorKey.PROMPT_EVAL_TECHNIQUE_UNSUPPORTED,
        error_detail=detail,
    )


def reject_unsupported_techniques(techniques: List[str]) -> None:
    """Allow-list gate shared by the check and the rewrite. Ids reaching the rewrite
    are rendered into a prompt, so nothing outside this list may pass"""
    for technique in techniques:
        if technique in _TRACE_TECHNIQUES:
            raise _unsupported(
                f"'{technique}' needs an execution trace, which the isolated check does "
                "not produce. Run it from a test suite instead."
            )
        if technique in _DEFERRED_TECHNIQUES:
            raise _unsupported(f"'{technique}' is not available in prompt checks yet.")
        if technique not in PROMPT_CHECK_TECHNIQUES:
            raise _unsupported(f"'{technique}' is not a matching technique this check knows.")


def describe_expectations(techniques: List[str]) -> str:
    """One line per technique with a settled reading, allow-list ordered (reorder-stable).
    Empty if none have one"""
    selected = set(techniques)
    lines = [f"- {technique}: {rule}" for technique, rule in _EXPECTATION_RULES.items() if technique in selected]
    return "\n".join(lines)


def validate_prompt_check_techniques(
    techniques: List[str], configs: PromptTechniqueConfigs
) -> Dict[str, Dict[str, Any]]:
    """Filter unsupported techniques, then build config dicts for the registry"""
    reject_unsupported_techniques(techniques)

    selected = set(techniques)
    for name in _CONFIGURABLE:
        if getattr(configs, name) is not None and name not in selected:
            raise _unsupported(f"Configuration was sent for '{name}', which is not selected.")

    # No expectation fallback. Empty config fails all cases
    if "not_contains" in selected and configs.not_contains is None:
        raise _unsupported(
            "'not_contains' needs at least one forbidden phrase. Add one or clear the check."
        )

    built: Dict[str, Dict[str, Any]] = {}
    for technique in techniques:
        if technique == "not_contains":
            built[technique] = {"phrases": list(configs.not_contains.phrases)}
        elif technique == "field_equals" and configs.field_equals is not None:
            config: Dict[str, Any] = {"field": configs.field_equals.field}
            if configs.field_equals.expected is not None:
                config["expected"] = configs.field_equals.expected
            built[technique] = config
        elif technique == "nli_eval":
            built[technique] = dict(_NLI_CONFIG)
        else:
            built[technique] = {}
    return built
