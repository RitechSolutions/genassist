#!/bin/bash

# Function to display usage information
function show_usage {
    echo "Usage: $0 [OPTION]"
    echo "Manage Tests for GenAgent"
    echo ""
    echo "Options:"
    echo "  test-all       Run all tests"
    echo "  test-unit      Run unit tests"
    echo "  test-integration Run integration tests"
    echo "  test-clean     Clean up test artifacts"
    echo "  test-help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 test-all"
    echo "  $0 test-unit"
    echo "  $0 test-integration"
    echo "  $0 test-clean"
    echo "  $0 test-help"
}       

# Function to clean up test artifacts
function cleanup_test_artifacts {
    echo "Cleaning test outputs..."
    rm -rf .pytest_cache/
    rm -rf htmlcov/
    rm coverage.xml
    rm .coverage
    rm .coverage.*
    rm test-results.xml
}

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed"
    exit 1
fi

# Process command line arguments
case "$1" in
    test-all)
        echo "Running all tests..."
        cleanup_test_artifacts

        # Start the necessary services for integration tests
        "$SCRIPT_DIR/manage-services.sh" start-db
        "$SCRIPT_DIR/manage-services.sh" start-chroma
        "$SCRIPT_DIR/manage-services.sh" start-neo4j
        sleep 5
        python -m pytest tests/ -v --cov=app --cov-report xml --junitxml="test-results.xml" --cov-report=html
        "$SCRIPT_DIR/manage-services.sh" stop-db
        "$SCRIPT_DIR/manage-services.sh" stop-chroma
        "$SCRIPT_DIR/manage-services.sh" stop-neo4j
        rm .coverage.*
        ;;
    test-unit)
        echo "Running unit tests..."
        cleanup_test_artifacts

        python -m pytest tests/unit -v --cov=app --cov-report xml --junitxml="test-results.xml" --cov-report=html
        rm .coverage.*
        ;;
    test-integration)
        echo "Running integration tests..."
        cleanup_test_artifacts
        # Start the necessary services for integration tests
        "$SCRIPT_DIR/manage-services.sh" start-db
        "$SCRIPT_DIR/manage-services.sh" start-chroma
        "$SCRIPT_DIR/manage-services.sh" start-neo4j
        sleep 5
        python -m pytest tests/integration/ -v --cov=app --cov-report xml --junitxml="test-results.xml" --cov-report=html
        "$SCRIPT_DIR/manage-services.sh" stop-db
        "$SCRIPT_DIR/manage-services.sh" stop-chroma
        "$SCRIPT_DIR/manage-services.sh" stop-neo4j
        rm .coverage.*
        ;;
    test-clean)
        cleanup_test_artifacts
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

exit 0 