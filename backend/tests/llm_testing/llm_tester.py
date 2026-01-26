import os
from dotenv import load_dotenv
load_dotenv()
import asyncio
import json
import re
import uuid
from json import JSONDecodeError
from logging import getLogger
from pathlib import Path
import requests
import pandas as pd
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time
import argparse
from fastapi_injector import RequestScopeFactory
from app.dependencies.injector import injector
from app.services.auth import AuthService


logger = getLogger(__name__)


class ValidationResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"


class TestDataSource(Enum):
    """Enum to specify the test data source type"""
    CSV = "csv"
    JSON = "json"
    MANUAL = "manual"


@dataclass
class TestCase:
    prompt: str
    workflow_id: str  # UUID of the workflow to test
    expected_tool_calls: List[str]
    expected_keywords: List[str]
    expected_output: Optional[str] = None
    thread_id: Optional[str] = None  # Optional thread ID


@dataclass
class TestResult:
    test_id: int
    prompt: str
    actual_output: str
    actual_tool_calls: List[str]
    expected_tool_calls: List[str]
    expected_keywords: List[str]
    tool_calls_result: ValidationResult
    keywords_result: ValidationResult
    overall_result: ValidationResult
    error_message: Optional[str] = None
    response_time: float = 0.0


class EndpointTester:
    def __init__(self, endpoint_url: str, headers: Optional[Dict] = None):
        self.endpoint_url = endpoint_url
        self.headers = headers or {"Content-Type": "application/json"}
        self.test_results: List[TestResult] = []

    def _get_safe_path_components(self, user_input: str) -> tuple:
        """
        Extract and validate path components from user input.
        Returns (directory, filename) tuple after sanitization.
        """
        import os

        # Reject path traversal patterns
        if '..' in user_input:
            raise ValueError(f"Path traversal pattern detected: {user_input}")

        # Normalize and split into components
        normalized = os.path.normpath(user_input)
        directory = os.path.dirname(normalized)
        filename = os.path.basename(normalized)

        # Validate filename doesn't contain traversal
        if not filename or '..' in filename:
            raise ValueError(f"Invalid filename: {user_input}")

        return (directory, filename)

    def _validate_file_path(self, file_path: str) -> Path:
        """
        Validate and sanitize a file path to prevent path traversal attacks.
        Resolves the path and ensures it's within the allowed directory.
        Returns a Path object for safe file operations.
        """
        # Extract sanitized components - this breaks the taint chain
        directory, filename = self._get_safe_path_components(file_path)

        # Get allowed base directories
        base_dir = Path.cwd().resolve()
        project_root = Path(__file__).parent.parent.parent.resolve()

        # Construct path from validated components using safe base
        if directory:
            # For paths with directories, construct from cwd
            safe_dir = base_dir / directory
        else:
            safe_dir = base_dir

        # Build the final path from known-safe directory + validated filename
        safe_path = (safe_dir / filename).resolve()

        # Verify the resolved path is within allowed directories
        path_str = str(safe_path)
        project_str = str(project_root)
        cwd_str = str(base_dir)

        if not (path_str.startswith(project_str) or path_str.startswith(cwd_str)):
            raise ValueError(f"Path outside allowed directory: {file_path}")

        # Check file existence
        if not safe_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        return safe_path

    def load_dataset_from_csv(self, csv_path: str) -> List[TestCase]:
        """
        Load test cases from CSV file.
        Expected columns: prompt, workflow_id, expected_tool_calls, expected_keywords
        """
        # Validate and sanitize the file path to prevent path traversal
        validated_path = self._validate_file_path(csv_path)
        df = pd.read_csv(validated_path)
        test_cases = []

        for _, row in df.iterrows():
            # Parse comma-separated tool calls and keywords
            tool_calls = [tc.strip() for tc in str(row['expected_tool_calls']).split(',')]
            keywords = [kw.strip() for kw in str(row['expected_keywords']).split(',')]

            test_cases.append(TestCase(
                    prompt=row['prompt'],
                    workflow_id=row['workflow_id'],
                    expected_tool_calls=tool_calls,
                    expected_keywords=keywords,
                    expected_output=row.get('expected_output', None),
                    thread_id=row.get('thread_id', None)
                    ))

        return test_cases


    def load_dataset_from_json(self, json_path: str) -> List[TestCase]:
        """
        Load test cases from JSON file.
        Expected format:
        [
            {
                "prompt": "...",
                "workflow_id": "...",
                "expected_tool_calls": ["tool1", "tool2"],
                "expected_keywords": ["keyword1", "keyword2"],
                "expected_output": "..." (optional),
                "thread_id": "..." (optional)
            }
        ]
        """
        # Validate and sanitize the file path to prevent path traversal
        # Path is validated by _validate_file_path() which checks for traversal attempts
        # and ensures the path is within allowed directories
        validated_path = self._validate_file_path(json_path)
        # Use Path.read_text() for safe file reading after validation
        data = json.loads(validated_path.read_text(encoding='utf-8'))

        test_cases = []
        for item in data:
            test_cases.append(TestCase(
                    prompt=item['prompt'],
                    workflow_id=item['workflow_id'],
                    expected_tool_calls=item['expected_tool_calls'],
                    expected_keywords=item['expected_keywords'],
                    expected_output=item.get('expected_output', None),
                    thread_id=item.get('thread_id', None)
                    ))

        return test_cases


    def get_manual_test_cases(self, workflow_id: str) -> List[TestCase]:
        """
        Define test cases manually in code.
        Override this method or pass custom test cases.
        """
        return [
            TestCase(
                    prompt="Give me the product documentation?",
                    expected_tool_calls=["get_product"],
                    expected_keywords=["ram"],
                    workflow_id=workflow_id
                    ),
            TestCase(
                    prompt="Send an email to john@example.com",
                    expected_tool_calls=["send_email"],
                    expected_keywords=["email", "sent"],
                    workflow_id=workflow_id
                    ),
            TestCase(
                    prompt="Calculate 15% of 250",
                    expected_tool_calls=["calculator"],
                    expected_keywords=["37.5", "result"],
                    workflow_id=workflow_id
                    )
            ]


    def call_endpoint(self, test_case: TestCase) -> tuple[str, Any]:
        """
        Make API call to  endpoint.
        """
        payload = {
            "input_data": {
                "message": test_case.prompt,
                "thread_id": test_case.thread_id or str(uuid.uuid4())
                }
            }
        params = {"workflow_id": test_case.workflow_id}

        start_time = time.time()
        response = requests.post(
                self.endpoint_url,
                json=payload,
                params=params,
                headers=self.headers,
                timeout=30
                )
        response_time = time.time() - start_time

        response.raise_for_status()
        return response.json(), response_time


    def extract_tool_calls(self, response: Dict[str, Any]) -> List[str]:
        """
        Extract tool call names from the API response.
        Adjust this method based on your response format.
        """
        tool_calls = []

        # Check if output and steps exist
        if 'output' not in response:
            return tool_calls

        if 'steps' not in response['output']:
            return tool_calls

        for step in response['output']['steps']:
            # Ensure step is a dict and has 'response' key
            if not isinstance(step, dict) or 'response' not in step:
                continue

            step_response = step['response']

            # Handle both string and dict responses
            if isinstance(step_response, str):
                try:
                    parsed_response = load_json_string(step_response)
                except JSONDecodeError as e:
                    print(f"Warning: Failed to parse response: {e}")
                    continue
            elif isinstance(step_response, dict):
                parsed_response = step_response
            else:
                continue

            # Check if it's a tool call and has tool_name
            if (isinstance(parsed_response, dict) and
                    parsed_response.get('action') == 'tool_call' and
                    'tool_name' in parsed_response):
                tool_calls.append(parsed_response['tool_name'])

        return tool_calls


    def extract_output_text(self, response: Dict[str, Any]) -> str:
        """
        Extract the output text from the API response.
        """
        # Common response formats:
        if 'output' in response:
            return str(response['output']['message'])
        else:
            # Return the entire response as string if structure is unknown
            return str(response)


    def validate_tool_calls(self, actual: List[str], expected: List[str]) -> ValidationResult:
        """Check if actual tool calls match expected ones."""
        if not expected:  # No tool calls expected
            return ValidationResult.PASS if not actual else ValidationResult.FAIL

        if not actual:  # Tool calls expected but none found
            return ValidationResult.FAIL

        # Check if all expected tool calls are present
        expected_set = set(expected)
        actual_set = set(actual)

        if expected_set == actual_set:
            return ValidationResult.PASS
        elif expected_set.intersection(actual_set):
            return ValidationResult.PARTIAL
        else:
            return ValidationResult.FAIL


    def validate_keywords(self, output: str, expected_keywords: List[str]) -> ValidationResult:
        """Check if output contains expected keywords."""
        if not expected_keywords:
            return ValidationResult.PASS

        output_lower = output.lower()
        found_keywords = [kw for kw in expected_keywords if kw.lower() in output_lower]

        if len(found_keywords) == len(expected_keywords):
            return ValidationResult.PASS
        elif found_keywords:
            return ValidationResult.PARTIAL
        else:
            return ValidationResult.FAIL


    def run_single_test(self, test_case: TestCase, test_id: int) -> TestResult:
        """Run a single test case."""
        try:
            # Call the endpoint
            response, response_time = self.call_endpoint(test_case)

            # Extract tool calls and output
            actual_tool_calls = self.extract_tool_calls(response)
            actual_output = self.extract_output_text(response)

            # Validate results
            tool_calls_result = self.validate_tool_calls(actual_tool_calls, test_case.expected_tool_calls)
            keywords_result = self.validate_keywords(actual_output, test_case.expected_keywords)

            # Determine overall result
            if tool_calls_result == ValidationResult.PASS and keywords_result == ValidationResult.PASS:
                overall_result = ValidationResult.PASS
            elif tool_calls_result == ValidationResult.FAIL and keywords_result == ValidationResult.FAIL:
                overall_result = ValidationResult.FAIL
            else:
                overall_result = ValidationResult.PARTIAL

            return TestResult(
                    test_id=test_id,
                    prompt=test_case.prompt,
                    actual_output=actual_output,
                    actual_tool_calls=actual_tool_calls,
                    expected_tool_calls=test_case.expected_tool_calls,
                    expected_keywords=test_case.expected_keywords,
                    tool_calls_result=tool_calls_result,
                    keywords_result=keywords_result,
                    overall_result=overall_result,
                    response_time=response_time
                    )

        except Exception as e:
            return TestResult(
                    test_id=test_id,
                    prompt=test_case.prompt,
                    actual_output="",
                    actual_tool_calls=[],
                    expected_tool_calls=test_case.expected_tool_calls,
                    expected_keywords=test_case.expected_keywords,
                    tool_calls_result=ValidationResult.FAIL,
                    keywords_result=ValidationResult.FAIL,
                    overall_result=ValidationResult.FAIL,
                    error_message=str(e),
                    response_time=0.0
                    )


    def run_tests(self, test_cases: List[TestCase], verbose: bool = True) -> List[TestResult]:
        """Run all test cases."""
        self.test_results = []

        for i, test_case in enumerate(test_cases):
            if verbose:
                print(f"Running test {i + 1}/{len(test_cases)}...")

            result = self.run_single_test(test_case, i + 1)
            self.test_results.append(result)

            if verbose:
                status = "✅" if result.overall_result == ValidationResult.PASS else "❌"
                print(f"  {status} Test {i + 1}: {result.overall_result.value}")
                if result.error_message:
                    print(f"error occurred: {result.error_message}")

        return self.test_results


    def generate_report(self) -> Dict[str, Any]:
        """Generate a summary report of test results."""
        if not self.test_results:
            return {"error": "No test results available"}

        total_tests = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.overall_result == ValidationResult.PASS)
        failed = sum(1 for r in self.test_results if r.overall_result == ValidationResult.FAIL)
        partial = sum(1 for r in self.test_results if r.overall_result == ValidationResult.PARTIAL)

        tool_calls_passed = sum(1 for r in self.test_results if r.tool_calls_result == ValidationResult.PASS)
        keywords_passed = sum(1 for r in self.test_results if r.keywords_result == ValidationResult.PASS)

        avg_response_time = sum(r.response_time for r in self.test_results) / total_tests

        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "partial": partial,
                "pass_rate": f"{(passed / total_tests) * 100:.1f}%"
                },
            "detailed_metrics": {
                "tool_calls_accuracy": f"{(tool_calls_passed / total_tests) * 100:.1f}%",
                "keywords_accuracy": f"{(keywords_passed / total_tests) * 100:.1f}%",
                "average_response_time": f"{avg_response_time:.2f}s"
                }
            }


    def save_results_to_csv(self, filename: str):
        """Save test results to CSV file."""
        data = []
        for result in self.test_results:
            data.append({
                "test_id": result.test_id,
                "prompt": result.prompt,
                "expected_tool_calls": ",".join(result.expected_tool_calls),
                "actual_tool_calls": ",".join(result.actual_tool_calls),
                "expected_keywords": ",".join(result.expected_keywords),
                "tool_calls_result": result.tool_calls_result.value,
                "keywords_result": result.keywords_result.value,
                "overall_result": result.overall_result.value,
                "response_time": result.response_time,
                "error_message": result.error_message or "",
                "actual_output": result.actual_output
                })

        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        print(f"Results saved to {filename}")


async def run_test(
        source_type: TestDataSource = TestDataSource.MANUAL,
        source_path: Optional[str] = None,
        workflow_id: Optional[str] = None
        ):
    """
    Run tests with specified data source.

    Args:
        source_type: Type of test data source (CSV, JSON, or MANUAL)
        source_path: Path to CSV or JSON file (required for CSV and JSON types)
        workflow_id: Workflow ID (required for MANUAL type)
    """
    request_scope_factory = injector.get(RequestScopeFactory)

    logger.info("Creating request scope...")
    async with request_scope_factory.create_scope():
        logger.info("Request scope created successfully.")
        auth_service: AuthService = injector.get(AuthService)
        user = await auth_service.authenticate_user(os.getenv("TEST_USERNAME"), os.getenv("TEST_PASSWORD"))
        token_data = {"sub": user.username, "user_id": str(user.id)}
        access_token = auth_service.create_access_token(data=token_data)

    # Initialize the tester
    tester = EndpointTester(
            endpoint_url="http://localhost:8000/api/genagent/workflow/test",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            )

    # Load test cases based on source type
    print(f"\n{'=' * 50}")
    print(f"Loading test cases from: {source_type.value.upper()}")
    print(f"{'=' * 50}\n")

    if source_type == TestDataSource.CSV:
        if not source_path:
            raise ValueError("source_path is required for CSV data source")
        test_cases = tester.load_dataset_from_csv(source_path)
        print(f"Loaded {len(test_cases)} test cases from CSV: {source_path}\n")

    elif source_type == TestDataSource.JSON:
        if not source_path:
            raise ValueError("source_path is required for JSON data source")
        test_cases = tester.load_dataset_from_json(source_path)
        print(f"Loaded {len(test_cases)} test cases from JSON: {source_path}\n")

    elif source_type == TestDataSource.MANUAL:
        if not workflow_id:
            raise ValueError("workflow_id is required for MANUAL data source")
        test_cases = tester.get_manual_test_cases(workflow_id)
        print(f"Using {len(test_cases)} manually defined test cases\n")

    else:
        raise ValueError(f"Unknown source type: {source_type}")

    # Run tests
    results = tester.run_tests(test_cases, verbose=True)

    # Generate and print report
    report = tester.generate_report()
    print("\n" + "=" * 50)
    print("TEST REPORT")
    print("=" * 50)
    print(json.dumps(report, indent=2))

    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_filename = f"test_results_{source_type.value}_{timestamp}.csv"
    tester.save_results_to_csv(output_filename)


def load_json_string(json_str):
    """
    Load JSON string, handling both plain JSON and markdown-wrapped JSON
    """
    # Remove leading/trailing whitespace
    json_str = json_str.strip()

    # Check if wrapped in Markdown code blocks
    if json_str.startswith('```'):
        # Remove code fence markers (```json or ``` at start and ``` at end)
        json_str = re.sub(r'^```(?:json)?\s*\n?', '', json_str)
        json_str = re.sub(r'\n?```\s*$', '', json_str)
        json_str = json_str.strip()

    # Parse the JSON
    return json.loads(json_str)


def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(description='Run endpoint tests with various data sources')
    parser.add_argument(
            '--source',
            type=str,
            choices=['csv', 'json', 'manual'],
            default='manual',
            help='Test data source type (default: manual)'
            )
    parser.add_argument(
            '--path',
            type=str,
            help='Path to CSV or JSON file (required for csv/json source types)'
            )
    parser.add_argument(
            '--workflow-id',
            type=str,
            default='019932f0-9b11-7058-8726-893193265cf6',
            help='Workflow ID (required for manual source type)'
            )

    args = parser.parse_args()

    # Convert string to enum
    source_type = TestDataSource(args.source)

    # Run tests
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_test(
            source_type=source_type,
            source_path=args.path,
            workflow_id=args.workflow_id
            ))


if __name__ == "__main__":
    # Option 1: Use command-line arguments
    main()

    # Option 2: Call directly in code (comment out main() above and uncomment below)
    # loop = asyncio.get_event_loop()

    # # For CSV
    # loop.run_until_complete(run_test(
    #     source_type=TestDataSource.CSV,
    #     source_path="test_dataset.csv"
    # ))

    # # For JSON
    # loop.run_until_complete(run_test(
    #     source_type=TestDataSource.JSON,
    #     source_path="test_dataset.json"
    # ))

    # # For Manual
    # loop.run_until_complete(run_test(
    #     source_type=TestDataSource.MANUAL,
    #     workflow_id="019932f0-9b11-7058-8726-893193265cf6"
    # ))