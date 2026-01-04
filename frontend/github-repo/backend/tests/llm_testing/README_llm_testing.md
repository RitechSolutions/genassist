# LLM Testing Tool

A simple tool for testing workflow endpoints with different test data sources.

## Usage

### 1. Manual Testing (Hardcoded Test Cases)

Use manually defined test cases in the code:

```bash
python -m tests.llm_testing.llm_tester --source manual --workflow-id "019932f0-9b11-7058-8726-893193265cf6"
```

### 2. CSV Testing

Load test cases from a CSV file:

```bash
python -m tests.llm_testing.llm_tester --source csv --path "test_dataset.csv"
```

**Expected CSV format:**

```csv
prompt,workflow_id,expected_tool_calls,expected_keywords,expected_output,thread_id
"Give me product docs",019932f0-9b11-7058-8726-893193265cf6,"get_product","ram",,
```

```bash
python -m tests.llm_testing.llm_tester --source csv --path "test_dataset.csv"
```

### 3. JSON Testing

Load test cases from a JSON file:

```bash
python -m tests.llm_testing.llm_tester --source json --path "test_dataset.json"
```

**Expected JSON format:**

```json
[
  {
    "prompt": "Give me the product documentation?",
    "workflow_id": "019932f0-9b11-7058-8726-893193265cf6",
    "expected_tool_calls": ["get_product"],
    "expected_keywords": ["ram"],
    "expected_output": "",
    "thread_id": ""
  }
]
```

## Output

Test results are saved to a CSV file: `test_results_{source_type}_{timestamp}.csv`

A summary report is printed to the console showing:
- Pass/fail statistics
- Tool call accuracy
- Keyword accuracy
- Average response time