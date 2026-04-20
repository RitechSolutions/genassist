import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from injector import inject
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.prompt_editor import PromptConfigModel, PromptVersionModel
from app.db.models.test_suite import TestSuiteModel
from app.repositories.prompt_editor import PromptConfigRepository, PromptVersionRepository
from app.repositories.test_suite import TestCaseRepository, TestSuiteRepository
from app.schemas.prompt_editor import (
    PromptConfigRead,
    PromptEvalCaseResult,
    PromptEvalResponse,
    PromptEvalSummary,
    PromptOptimizeResponse,
    PromptVersionCreate,
    PromptVersionRead,
)

logger = logging.getLogger(__name__)


@inject
class PromptEditorService:
    def __init__(
        self,
        version_repo: PromptVersionRepository,
        config_repo: PromptConfigRepository,
        suite_repo: TestSuiteRepository,
        case_repo: TestCaseRepository,
        db: AsyncSession,
    ) -> None:
        self.version_repo = version_repo
        self.config_repo = config_repo
        self.suite_repo = suite_repo
        self.case_repo = case_repo
        self.db = db
        # Lazy import to avoid circular dependency (test_suite imports injector at module level)
        from app.services.test_suite import SimpleEvaluatorRegistry

        self.evaluators = SimpleEvaluatorRegistry()

    # ---- Versions ------------------------------------------------------------

    async def list_versions(
        self, workflow_id: UUID, node_id: str, prompt_field: str
    ) -> List[PromptVersionRead]:
        rows = await self.version_repo.get_versions_for_context(
            workflow_id, node_id, prompt_field
        )
        return [PromptVersionRead.model_validate(r, from_attributes=True) for r in rows]

    async def create_version(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
        data: PromptVersionCreate,
    ) -> PromptVersionRead:
        # Backward-compatible behavior: create a new version.
        #
        # Override behavior: if a version with the same label already exists in this
        # context, update (override) its content instead of creating a new version.
        #
        # This is especially useful when the UI re-saves a "named" version.
        existing: Optional[PromptVersionModel] = None
        if data.label:
            versions = await self.version_repo.get_versions_for_context(
                workflow_id, node_id, prompt_field
            )
            existing = next((v for v in versions if v.label == data.label), None)

        # Deactivate previous versions (we want exactly one active)
        await self.version_repo.deactivate_all_for_context(
            workflow_id, node_id, prompt_field
        )

        if existing:
            existing.content = data.content
            existing.label = data.label
            existing.is_active = True
            updated = await self.version_repo.update(existing)
            return PromptVersionRead.model_validate(updated, from_attributes=True)

        version_number = await self.version_repo.get_next_version_number(
            workflow_id, node_id, prompt_field
        )
        orm = PromptVersionModel(
            workflow_id=workflow_id,
            node_id=node_id,
            prompt_field=prompt_field,
            version_number=version_number,
            content=data.content,
            label=data.label,
            is_active=True,
        )
        created = await self.version_repo.create(orm)
        return PromptVersionRead.model_validate(created, from_attributes=True)

    async def restore_version(self, version_id: UUID) -> PromptVersionRead:
        version = await self.version_repo.get_by_id(version_id)
        if not version:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        await self.version_repo.deactivate_all_for_context(
            version.workflow_id, version.node_id, version.prompt_field
        )
        version.is_active = True
        await self.db.commit()
        return PromptVersionRead.model_validate(version, from_attributes=True)

    async def delete_version(self, version_id: UUID) -> None:
        version = await self.version_repo.get_by_id(version_id)
        if not version:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        await self.version_repo.soft_delete(version)

    async def hard_delete_version(self, version_id: UUID) -> None:
        version = await self.version_repo.get_by_id(version_id)
        if not version:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        await self.version_repo.delete(version)

    # ---- Config / Gold Suite -------------------------------------------------

    async def get_or_create_config(
        self, workflow_id: UUID, node_id: str, prompt_field: str
    ) -> PromptConfigRead:
        config = await self.config_repo.get_by_context(
            workflow_id, node_id, prompt_field
        )
        if not config:
            config = PromptConfigModel(
                workflow_id=workflow_id,
                node_id=node_id,
                prompt_field=prompt_field,
            )
            config = await self.config_repo.create(config)
        return PromptConfigRead.model_validate(config, from_attributes=True)

    async def link_gold_suite(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
        suite_id: Optional[UUID] = None,
        name: Optional[str] = None,
    ) -> PromptConfigRead:
        config = await self.config_repo.get_by_context(
            workflow_id, node_id, prompt_field
        )
        if not config:
            config = PromptConfigModel(
                workflow_id=workflow_id,
                node_id=node_id,
                prompt_field=prompt_field,
            )
            config = await self.config_repo.create(config)

        if suite_id:
            suite = await self.suite_repo.get_by_id(suite_id)
            if not suite:
                raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
            config.gold_suite_id = suite_id
        else:
            suite_name = name or f"Gold Dataset - {node_id}/{prompt_field}"
            suite = TestSuiteModel(name=suite_name, workflow_id=workflow_id)
            suite = await self.suite_repo.create(suite)
            config.gold_suite_id = suite.id

        await self.db.commit()
        return PromptConfigRead.model_validate(config, from_attributes=True)

    # ---- Evaluate ------------------------------------------------------------

    async def evaluate_prompt(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
        prompt_content: str,
        techniques: List[str],
        provider_id: UUID,
    ) -> PromptEvalResponse:
        config = await self.config_repo.get_by_context(
            workflow_id, node_id, prompt_field
        )
        if not config or not config.gold_suite_id:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail="No gold dataset linked to this prompt. Create one first.",
            )

        cases = await self.case_repo.get_all_for_suite(config.gold_suite_id)
        if not cases:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail="Gold dataset has no cases. Add test cases first.",
            )

        from app.dependencies.injector import injector
        from app.modules.workflow.llm.provider import LLMProvider

        llm_provider = injector.get(LLMProvider)
        llm = await llm_provider.get_model(str(provider_id))

        results: List[PromptEvalCaseResult] = []
        total_score = 0.0
        total_passed = 0

        for case in cases:
            input_text = case.input_data.get("message", str(case.input_data))
            expected_text = ""
            if case.expected_output:
                expected_text = case.expected_output.get(
                    "value", str(case.expected_output)
                )

            try:
                response = await llm.ainvoke(
                    [
                        SystemMessage(content=prompt_content),
                        HumanMessage(content=input_text),
                    ]
                )
                actual_text = getattr(response, "content", "")
                if isinstance(actual_text, list):
                    actual_text = " ".join(str(part) for part in actual_text)
            except Exception as exc:
                logger.exception("Error calling LLM for case %s: %s", case.id, exc)
                actual_text = f"[Error: {exc}]"

            metrics = await self.evaluators.evaluate(
                techniques,
                inputs=case.input_data,
                outputs=actual_text,
                reference_outputs=expected_text,
            )

            case_passed = all(m.get("passed", False) for m in metrics.values())
            case_score = 0.0
            if metrics:
                scores = [
                    float(m["score"])
                    for m in metrics.values()
                    if isinstance(m.get("score"), (int, float))
                ]
                case_score = sum(scores) / len(scores) if scores else 0.0

            total_score += case_score
            total_passed += 1 if case_passed else 0

            results.append(
                PromptEvalCaseResult(
                    case_id=case.id,
                    input=input_text,
                    expected=expected_text,
                    actual=actual_text,
                    metrics=metrics,
                    passed=case_passed,
                )
            )

        total = len(results)
        return PromptEvalResponse(
            results=results,
            summary=PromptEvalSummary(
                total=total,
                passed=total_passed,
                avg_score=total_score / total if total else 0.0,
            ),
        )

    # ---- Optimize ------------------------------------------------------------

    async def optimize_prompt(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
        current_prompt: str,
        provider_id: UUID,
        instructions: Optional[str] = None,
        failed_cases: Optional[List[Dict[str, Any]]] = None,
    ) -> PromptOptimizeResponse:
        # Load gold cases for context
        config = await self.config_repo.get_by_context(
            workflow_id, node_id, prompt_field
        )
        gold_examples = ""
        if config and config.gold_suite_id:
            cases = await self.case_repo.get_all_for_suite(config.gold_suite_id)
            if cases:
                examples = []
                for c in cases[:20]:  # Limit to 20 examples
                    inp = c.input_data.get("message", str(c.input_data))
                    exp = ""
                    if c.expected_output:
                        exp = c.expected_output.get("value", str(c.expected_output))
                    examples.append(f"Input: {inp}\nExpected: {exp}")
                gold_examples = "\n\n".join(examples)

        failed_section = ""
        if failed_cases:
            failed_items = []
            for fc in failed_cases[:10]:
                failed_items.append(
                    f"Input: {fc.get('input', '')}\n"
                    f"Expected: {fc.get('expected', '')}\n"
                    f"Got: {fc.get('actual', '')}"
                )
            failed_section = (
                "\n\n## FAILED CASES\n"
                "These cases failed evaluation with the current prompt:\n\n"
                + "\n\n---\n".join(failed_items)
            )

        user_instructions = ""
        if instructions:
            user_instructions = f"\n\n## ADDITIONAL INSTRUCTIONS\n{instructions}"

        system_prompt = (
            "You are an expert prompt engineer. Your task is to improve a system prompt "
            "so that when an LLM uses it, the LLM produces responses that match the "
            "gold dataset expected outputs as closely as possible.\n\n"
            "Rules:\n"
            "- Study each gold dataset pair carefully: the Input is what the user will say, "
            "and the Expected output is the ideal response the LLM should produce\n"
            "- Rewrite the system prompt so the LLM would naturally produce responses "
            "matching those expected outputs\n"
            "- If there are failed cases, pay special attention to fixing those patterns\n"
            "- Preserve the original intent and domain of the prompt\n"
            "- Be specific: add formatting instructions, tone guidance, or constraints "
            "that align with the gold examples\n"
            "- Return your response as JSON with two fields:\n"
            '  {"improved_prompt": "the full improved prompt text", '
            '"explanation": "brief explanation of what you changed and why"}\n'
            "- Return ONLY the JSON object, no other text"
        )

        human_message = (
            f"## CURRENT SYSTEM PROMPT\n{current_prompt}\n\n"
            f"## GOLD DATASET (Input → Expected Output)\n"
            f"The improved prompt must guide the LLM to produce outputs matching these:\n\n"
            f"{gold_examples}"
            f"{failed_section}"
            f"{user_instructions}"
        )

        from app.dependencies.injector import injector
        from app.modules.workflow.llm.provider import LLMProvider

        llm_provider = injector.get(LLMProvider)
        llm = await llm_provider.get_model(str(provider_id))

        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_message),
            ]
        )

        raw_content = getattr(response, "content", "")
        if isinstance(raw_content, list):
            raw_content = " ".join(str(part) for part in raw_content)

        try:
            parsed = json.loads(raw_content)
            return PromptOptimizeResponse(
                suggested_prompt=parsed.get("improved_prompt", raw_content),
                explanation=parsed.get("explanation", ""),
            )
        except (json.JSONDecodeError, ValueError):
            # If LLM didn't return valid JSON, treat entire response as the prompt
            return PromptOptimizeResponse(
                suggested_prompt=raw_content,
                explanation="The LLM response was returned as-is (JSON parsing failed).",
            )
