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
            "Reply in {{session.language}}.",
            "Greet {{session.customer_name}}.",
            "Greet {{customer_name}}.",
            "{{thread_id}}",
            "{{workflow_id}}",
        ],
        ids=repr,
    )
    def test_any_template_var_is_treated_as_volatile(self, template):
        assert has_volatile_template_vars(template) is True

    @pytest.mark.parametrize(
        "template",
        [
            "You are a helpful assistant.",
            "{{ source }}",
            "",
            None,
            {"systemPrompt": "{{source}}"},
        ],
        ids=repr,
    )
    def test_var_free_or_unresolvable_templates_are_not_volatile(self, template):
        assert has_volatile_template_vars(template) is False

    def test_unrecognized_var_is_over_blocked_by_design(self):
        assert has_volatile_template_vars("{{some_future_state_field}}") is True
