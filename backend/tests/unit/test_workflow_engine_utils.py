import pytest

from app.modules.workflow.engine.utils import (
    get_nested_value,
    has_volatile_template_vars,
    replace_config_vars,
)
from app.modules.workflow.engine.workflow_state import WorkflowState


class TestGetNestedValue:
    def test_prediction_result_path(self):
        source = {
            "prediction": [{"result": 3891, "label": "Not Available"}],
        }
        assert get_nested_value(source, "prediction[0].result") == 3891
        assert get_nested_value(source, "prediction[0].label") == "Not Available"


class TestReplaceConfigVars:
    def test_resolves_prediction_result_in_python_script(self):
        source_output = {
            "prediction": [{"result": 3891, "label": "Not Available"}],
        }
        config = {
            "pythonScript": (
                'result = {"prediction": {{source.prediction[0].result}}, '
                '"label": "{{source.prediction[0].label}}"}'
            )
        }

        resolved, replacements = replace_config_vars(
            config=config,
            state=WorkflowState(workflow={"nodes": [], "edges": []}),
            source_output=source_output,
        )

        assert replacements["source.prediction[0].result"] == 3891
        assert replacements["source.prediction[0].label"] == "Not Available"
        assert '"prediction": 3891' in resolved["pythonScript"]
        assert '"label": "Not Available"' in resolved["pythonScript"]


class TestHasVolatileTemplateVars:
    @pytest.mark.parametrize(
        "template",
        [
            "{{source}}",
            "Summarize {{source.text}}",
            "{{sourceLanguage}}",
            "{{direct_input}}",
            "{{direct_input.query}}",
            "{{node_outputs.node-1.result}}",
            "{{node_inputs.node-1}}",
            "{{node_execution_status.node-1.output}}",
            "Now: {{timestamp}}",
            "{{execution_id}}",
            "{{execution_path}}",
            "{{execution_path[0]}}",
            "{{execution_history}}",
            "{{execution_start_time}}",
            "{{execution_end_time}}",
            "{{session.message}}",
            "{{session}}",
            "{{initial_values}}",
            "{{message}}",
            "{{output}}",
            "{{current_step}}",
            "{{total_steps}}",
            "{{status}}",
            "{{is_executing}}",
            "{{time_taken}}",
            "{{performance_metrics.slowestNode}}",
            "{{errors}}",
            "{{llm_usage}}",
            "{{tool_events}}",
            "{{memory}}",
        ],
    )
    def test_per_request_vars_are_volatile(self, template):
        assert has_volatile_template_vars(template) is True

    @pytest.mark.parametrize(
        "template",
        [
            "You are a helpful assistant.",
            "Reply in {{session.language}}.",
            "Greet {{session.customer_name}}.",
            "Greet {{customer_name}}.",
            "{{thread_id}}",
            "{{workflow_id}}",
            "{{ source }}",
            "",
            None,
            {"systemPrompt": "{{source}}"},
        ],
        ids=repr,
    )
    def test_stable_or_unresolvable_templates_are_not_volatile(self, template):
        assert has_volatile_template_vars(template) is False

    def test_every_workflow_state_field_is_classified(self):
        """A field added to WorkflowState is volatile until it is listed as stable here"""
        stable_fields = {
            "registry_managed",
            "sub_agent_persistent_claimed",
            "target_edges",
            "thread_id",
            "workflow",
            "workflow_id",
        }
        state = WorkflowState(workflow={"nodes": [], "edges": []})

        unclassified = {
            name
            for name in vars(state)
            if not name.startswith("_")
            and name not in stable_fields
            and not has_volatile_template_vars("{{%s}}" % name)
        }

        assert unclassified == set()
