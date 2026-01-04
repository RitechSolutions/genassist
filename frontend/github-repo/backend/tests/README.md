To run all tests"
python -m pytest tests/


To run single test:
 pytest . -k 'test_list_operators'
 PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python pytest . -k 'test_agent_with_resources'

To runtests with coverage:
coverage run --source=app -m pytest -v tests && coverage report -m

python -m pytest tests/ -v --cov=app --cov-report xml --junitxml="test-results.xml" --cov-report=html

clean test files and dirs:
rm -rf .pytest_cache/
rm -rf htmlcov/
rm coverage.xml
rm .coverage
rm .coverage.*
rm test-results.xml