"""Which evaluator techniques an isolated prompt check may run, the exact
configuration each one receives, and what each makes of a case's expectation"""

from typing import Any, Dict, List, Optional
from uuid import UUID

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

_JUDGE_TECHNIQUE = "llm_judge"

# Techniques whose configuration the request may carry, in PromptTechniqueConfigs order
_CONFIGURABLE = ("not_contains", "field_equals", "nli_eval", _JUDGE_TECHNIQUE)

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


def _configured_rule(technique: str, config: Optional[Dict[str, Any]]) -> Optional[str]:
    """Technique's config interpretation. None if absent/empty (allows not_contains without values)"""
    if not config:
        return None
    if technique == "not_contains":
        phrases = config.get("phrases") or []
        if not phrases:
            return None
        return (
            "the reply must not contain any of these phrases, case-insensitively: "
            + ", ".join(f'"{phrase}"' for phrase in phrases)
        )
    if technique == "field_equals":
        field = config.get("field")
        if not field:
            return None
        target = f'"{config["expected"]}"' if "expected" in config else "the expected output"
        return f"the reply field '{field}' must equal {target}"
    if technique == "nli_eval":
        score = config.get("min_entail_score")
        if score is None:
            return None
        return (
            f"{_EXPECTATION_RULES['nli_eval']}. Support is judged per claim, and a claim "
            f"counts as supported at an entailment score of {score} or higher"
        )
    return None


def describe_expectations(
    techniques: List[str], configs: Optional[Dict[str, Dict[str, Any]]] = None
) -> str:
    """Entry per technique, allow-list ordered (stable). Omitted if no reading/config"""
    selected = set(techniques)
    built = configs or {}
    lines = []
    for technique in PROMPT_CHECK_TECHNIQUES:
        if technique not in selected:
            continue
        rule = _configured_rule(technique, built.get(technique)) or _EXPECTATION_RULES.get(technique)
        if rule:
            lines.append(f"- {technique}: {rule}")
    return "\n".join(lines)


def build_technique_configs(
    techniques: List[str],
    configs: PromptTechniqueConfigs,
    *,
    judge_provider_id: Optional[UUID] = None,
) -> Dict[str, Dict[str, Any]]:
    """Config dicts for the registry. Rejects configuration for techniques that are not
    selected; requires none except the judge's rubric, which both routes need: a
    rubric-less judge grades nothing and tells the rewrite nothing"""
    reject_unsupported_techniques(techniques)

    selected = set(techniques)
    for name in _CONFIGURABLE:
        if getattr(configs, name, None) is not None and name not in selected:
            raise _unsupported(f"Configuration was sent for '{name}', which is not selected.")
    if _JUDGE_TECHNIQUE in selected and configs.llm_judge is None:
        raise _unsupported("'llm_judge' needs a rubric. Add one or clear the check.")

    built: Dict[str, Dict[str, Any]] = {}
    for technique in techniques:
        if technique == "not_contains":
            built[technique] = (
                {"phrases": list(configs.not_contains.phrases)} if configs.not_contains is not None else {}
            )
        elif technique == "field_equals" and configs.field_equals is not None:
            config: Dict[str, Any] = {"field": configs.field_equals.field}
            if configs.field_equals.expected is not None:
                config["expected"] = configs.field_equals.expected
            built[technique] = config
        elif technique == "nli_eval":
            built[technique] = dict(_NLI_CONFIG)
            if configs.nli_eval is not None:
                built[technique]["min_entail_score"] = configs.nli_eval.min_entail_score
        elif technique == _JUDGE_TECHNIQUE:
            judge_config: Dict[str, Any] = {
                "rules": [
                    {"rubric": rule.rubric, "min_score": rule.min_score, "source_type": rule.source_type}
                    for rule in configs.llm_judge.rules
                ]
            }
            if judge_provider_id is not None:
                judge_config["llm_provider_id"] = str(judge_provider_id)
            built[technique] = judge_config
        else:
            built[technique] = {}
    return built


def validate_prompt_check_techniques(
    techniques: List[str],
    configs: PromptTechniqueConfigs,
    *,
    judge_provider_id: Optional[UUID] = None,
) -> Dict[str, Dict[str, Any]]:
    """Reject unsupported techniques, then build config dicts for the registry"""
    built = build_technique_configs(techniques, configs, judge_provider_id=judge_provider_id)
    if "not_contains" in techniques and configs.not_contains is None:
        raise _unsupported(
            "'not_contains' needs at least one forbidden phrase. Add one or clear the check."
        )
    return built
