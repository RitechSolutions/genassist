from app.modules.workflow.engine.utils import get_nested_value, replace_config_vars
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
