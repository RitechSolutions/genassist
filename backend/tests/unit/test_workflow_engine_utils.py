import pytest

from app.modules.workflow.engine.utils import (
    PARAM_STYLE_PYFORMAT,
    QueryVariableError,
    bind_config_vars,
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


class TestBindConfigVars:
    @staticmethod
    def _state(initial_values=None):
        return WorkflowState(
            workflow={"nodes": []},
            initial_values=initial_values or {},
        )

    def test_binds_value_without_inlining_it(self):
        payload = "x' OR '1'='1"
        statement, parameters = bind_config_vars(
            "SELECT * FROM lots WHERE city = {{chat.input}}",
            self._state({"chat.input": payload}),
            source_output=None,
        )

        assert statement == "SELECT * FROM lots WHERE city = :wf_0_chat_input"
        assert payload not in statement
        assert parameters == {"wf_0_chat_input": payload}

    def test_strips_single_quotes_around_a_bound_value(self):
        statement, parameters = bind_config_vars(
            "SELECT * FROM lots WHERE city = '{{chat.input}}'",
            self._state({"chat.input": "O'Brien"}),
            source_output=None,
        )

        assert statement == "SELECT * FROM lots WHERE city = :wf_0_chat_input"
        assert parameters == {"wf_0_chat_input": "O'Brien"}

    def test_mysql_strips_double_quotes_around_a_bound_value(self):
        statement, parameters = bind_config_vars(
            'SELECT * FROM lots WHERE city = "{{chat.input}}"',
            self._state({"chat.input": "Tirana"}),
            source_output=None,
            db_type="mysql",
        )

        assert statement == "SELECT * FROM lots WHERE city = :wf_0_chat_input"
        assert parameters == {"wf_0_chat_input": "Tirana"}

    def test_non_mysql_double_quoted_variable_is_rejected(self):
        with pytest.raises(QueryVariableError, match="column names"):
            bind_config_vars(
                'SELECT * FROM lots WHERE city = "{{chat.input}}"',
                self._state({"chat.input": "Tirana"}),
                source_output=None,
                db_type="postgresql",
            )

    def test_snowflake_uses_pyformat_placeholders(self):
        statement, parameters = bind_config_vars(
            "SELECT * FROM lots WHERE city = {{chat.input}}",
            self._state({"chat.input": "Tirana"}),
            source_output=None,
            param_style=PARAM_STYLE_PYFORMAT,
        )

        assert statement == "SELECT * FROM lots WHERE city = %(wf_0_chat_input)s"
        assert parameters == {"wf_0_chat_input": "Tirana"}

    def test_snowflake_escapes_literal_percent_when_binding(self):
        statement, parameters = bind_config_vars(
            "SELECT * FROM lots WHERE code LIKE 'T%' AND n > {{n}}",
            self._state({"n": 2}),
            source_output=None,
            param_style=PARAM_STYLE_PYFORMAT,
            db_type="snowflake",
        )

        assert statement == ("SELECT * FROM lots WHERE code LIKE 'T%%' AND n > %(wf_0_n)s")
        assert statement % parameters == ("SELECT * FROM lots WHERE code LIKE 'T%' AND n > 2")

    def test_snowflake_does_not_escape_percent_without_parameters(self):
        statement, parameters = bind_config_vars(
            "SELECT * FROM lots WHERE code LIKE 'T%'",
            self._state(),
            source_output=None,
            param_style=PARAM_STYLE_PYFORMAT,
            db_type="snowflake",
        )

        assert statement == "SELECT * FROM lots WHERE code LIKE 'T%'"
        assert parameters == {}

    def test_repeated_variable_reuses_one_parameter(self):
        statement, parameters = bind_config_vars(
            "SELECT * FROM lots WHERE city = {{chat.input}} OR backup = {{chat.input}}",
            self._state({"chat.input": "Tirana"}),
            source_output=None,
        )

        assert statement.count(":wf_0_chat_input") == 2
        assert parameters == {"wf_0_chat_input": "Tirana"}

    def test_source_and_direct_input_values_are_supported(self):
        statement, parameters = bind_config_vars(
            "SELECT * FROM lots WHERE city = {{source.city}} AND hour = {{direct_input.hour}}",
            self._state(),
            source_output={"city": "Tirana"},
            direct_input={"hour": 8},
        )

        assert statement == ("SELECT * FROM lots WHERE city = :wf_0_source_city AND hour = :wf_1_direct_input_hour")
        assert parameters == {
            "wf_0_source_city": "Tirana",
            "wf_1_direct_input_hour": 8,
        }

    def test_source_list_values_use_existing_resolution(self):
        statement, parameters = bind_config_vars(
            "SELECT * FROM lots WHERE city = {{source[1]}}",
            self._state(),
            source_output=["Durres", "Tirana"],
        )

        assert statement == "SELECT * FROM lots WHERE city = :wf_0_source_1_"
        assert parameters == {"wf_0_source_1_": "Tirana"}

    def test_unresolved_variable_is_bound_as_null(self, caplog):
        statement, parameters = bind_config_vars(
            "SELECT * FROM lots WHERE city = {{missing.value}}",
            self._state(),
            source_output=None,
        )

        assert statement == "SELECT * FROM lots WHERE city = :wf_0_missing_value"
        assert parameters == {"wf_0_missing_value": None}
        assert "missing.value did not resolve; bound as NULL" in caplog.text

    def test_variable_in_comment_does_not_create_a_parameter(self):
        statement, parameters = bind_config_vars(
            "SELECT 1 -- {{ignored}}\n/* {{also_ignored}} */",
            self._state(),
            source_output=None,
        )

        assert statement == "SELECT 1 -- {{ignored}}\n/* {{also_ignored}} */"
        assert parameters == {}

    def test_mysql_double_minus_without_whitespace_is_not_a_comment(self):
        statement, parameters = bind_config_vars(
            "SELECT 5--1, {{value}}",
            self._state({"value": 2}),
            source_output=None,
            db_type="mysql",
        )

        assert statement == "SELECT 5--1, :wf_0_value"
        assert parameters == {"wf_0_value": 2}

    def test_postgres_backslash_does_not_escape_closing_quote(self):
        statement, parameters = bind_config_vars(
            "SELECT * FROM lots WHERE city <> 'C:\\' AND city = {{city}}",
            self._state({"city": "Tirana"}),
            source_output=None,
            db_type="postgresql",
        )

        assert statement == "SELECT * FROM lots WHERE city <> 'C:\\' AND city = :wf_0_city"
        assert parameters == {"wf_0_city": "Tirana"}

    def test_postgres_backslash_before_quoted_variable_still_binds(self):
        statement, parameters = bind_config_vars(
            "SELECT * FROM lots WHERE city <> 'C:\\' AND city = '{{city}}'",
            self._state({"city": "Tirana"}),
            source_output=None,
            db_type="postgresql",
        )

        assert statement == "SELECT * FROM lots WHERE city <> 'C:\\' AND city = :wf_0_city"
        assert parameters == {"wf_0_city": "Tirana"}

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT * FROM lots WHERE city LIKE '%{{search}}%'",
            "SELECT * FROM lots WHERE city = 'prefix-{{search}}'",
        ],
    )
    def test_variable_embedded_in_quoted_literal_is_rejected(self, query):
        with pytest.raises(QueryVariableError, match="concatenation"):
            bind_config_vars(
                query,
                self._state({"search": "Tirana"}),
                source_output=None,
                db_type="postgresql",
            )

    def test_postgres_cast_wraps_the_named_parameter(self):
        statement, parameters = bind_config_vars(
            "SELECT {{day}}::date",
            self._state({"day": "2026-09-16"}),
            source_output=None,
            db_type="postgresql",
        )

        assert statement == "SELECT (:wf_0_day)::date"
        assert parameters == {"wf_0_day": "2026-09-16"}

    def test_bound_parameters_track_variable_names_only(self):
        _, parameters = bind_config_vars(
            "SELECT {{chat.input}}, {{direct_input.limit}}",
            self._state({"chat.input": "Tirana"}),
            source_output=None,
            direct_input={"limit": 5},
        )

        assert parameters.variable_names == {
            "wf_0_chat_input": "chat.input",
            "wf_1_direct_input_limit": "direct_input.limit",
        }

    def test_query_without_variables_is_unchanged(self):
        statement, parameters = bind_config_vars(
            "SELECT 1",
            self._state(),
            source_output=None,
        )

        assert statement == "SELECT 1"
        assert parameters == {}

    def test_unknown_parameter_style_is_rejected(self):
        with pytest.raises(ValueError, match="Unsupported SQL parameter style"):
            bind_config_vars(
                "SELECT {{chat.input}}",
                self._state({"chat.input": "Tirana"}),
                source_output=None,
                param_style="unknown",
            )
