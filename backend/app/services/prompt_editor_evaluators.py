"""Which evaluator techniques an isolated prompt check may run, and the exact
configuration each one receives"""

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


def _unsupported(detail: str) -> AppException:
    return AppException(
        status_code=400,
        error_key=ErrorKey.PROMPT_EVAL_TECHNIQUE_UNSUPPORTED,
        error_detail=detail,
    )


def validate_prompt_check_techniques(
    techniques: List[str], configs: PromptTechniqueConfigs
) -> Dict[str, Dict[str, Any]]:
    """Reject what an isolated check cannot grade, then build the configuration
    dictionaries the registry receives"""
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
