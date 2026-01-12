#!/bin/bash

# Exit on error
set -e

# Function to check if a command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 is not installed. Please install it first."
        exit 1
    fi
}

# Global variables for container names
DB_CONTAINER_NAME=""
TEST_CONTAINER_NAME=""
TEST_RESULT=0
ECR_REPO="474668385577.dkr.ecr.us-east-1.amazonaws.com"

# Function to cleanup containers
cleanup_containers() {
    echo "🧹 Cleaning up containers..."
    if [ ! -z "$TEST_CONTAINER_NAME" ]; then
        echo "Stopping and removing test container: $TEST_CONTAINER_NAME"
        docker stop "$TEST_CONTAINER_NAME" 2>/dev/null || true
        docker rm "$TEST_CONTAINER_NAME" 2>/dev/null || true
    fi
    if [ ! -z "$DB_CONTAINER_NAME" ]; then
        echo "Stopping and removing database container: $DB_CONTAINER_NAME"
        docker stop "$DB_CONTAINER_NAME" 2>/dev/null || true
        docker rm "$DB_CONTAINER_NAME" 2>/dev/null || true
    fi
}

# Function to create test database
create_test_database() {
    DB_CONTAINER_NAME="genassist-test-db-$(openssl rand -hex 4)"
    
    echo "🗄️ Creating test database container..."
    docker run -d --name "$DB_CONTAINER_NAME" \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASSWORD=postgres \
        -e POSTGRES_DB=core_db \
        -p 5433:5432 \
        postgres:17

    # Wait for database to be ready
    echo "⏳ Waiting for database to be ready..."
    sleep 10

    # Check if database is running
    local db_status=$(docker inspect -f '{{.State.Status}}' "$DB_CONTAINER_NAME")
    if [ "$db_status" != "running" ]; then
        echo "❌ Database container failed to start"
        docker logs "$DB_CONTAINER_NAME"
        cleanup_containers
        exit 1
    fi
}

# Function to run tests
run_tests() {
    echo "🧪 Running tests..."
    
    # Create test database
    create_test_database
    
    # Create a temporary test container
    TEST_CONTAINER_NAME="genassist-test-$(openssl rand -hex 4)"
    
    # Set up trap for cleanup
    trap cleanup_containers EXIT INT TERM
    
    # Run the container in detached mode with test environment variables
    echo "🚀 Starting test container..."
    docker run -d --name "$TEST_CONTAINER_NAME" \
        -e DB_HOST="host.docker.internal" \
        -e ENVIRONMENT="test" \
        -e LOG_LEVEL="DEBUG" \
        -e CREATE_DB="true" \
        -e DB_PORT="5433" \
        -e TESTING="true" \
        -p 8000:8000 \
        genassist-app:latest

    # Wait for the container to be healthy
    echo "⏳ Waiting for container to be healthy..."
    sleep 10

    # Check if container is running
    local container_status=$(docker inspect -f '{{.State.Status}}' "$TEST_CONTAINER_NAME")
    if [ "$container_status" != "running" ]; then
        echo "❌ Container failed to start properly"
        docker logs "$TEST_CONTAINER_NAME"
        cleanup_containers
        exit 1
    fi

    # Start following container logs in the background
    echo "📝 Following container logs..."
    docker logs -f "$TEST_CONTAINER_NAME" &
    LOG_PID=$!

    # Run pytest inside the container with test environment
    echo "📊 Running pytest..."
    if ! docker exec "$TEST_CONTAINER_NAME" python -m pytest tests/ -v; then
        echo "❌ Tests failed"
        TEST_RESULT=1
    else
        echo "✅ Tests passed successfully!"
        TEST_RESULT=0
    fi

    # Stop following logs
    kill $LOG_PID 2>/dev/null || true
}

# Check prerequisites
echo "🔍 Checking prerequisites..."

# Check AWS CLI
check_command aws

# Check Docker
check_command docker

# Check Terraform
check_command terraform

# Get Terraform outputs
echo "📡 Getting Terraform outputs..."
cd ../infra
ECR_REPO=$(terraform output -raw ecr_repository_url)
ECS_CLUSTER=$(terraform output -raw ecs_cluster_name)
ECS_SERVICE=$(terraform output -raw ecs_service_name)

if [ -z "$ECR_REPO" ] || [ -z "$ECS_CLUSTER" ] || [ -z "$ECS_SERVICE" ]; then
    echo "❌ Failed to get required Terraform outputs. Make sure you're in the correct directory and Terraform is initialized."
    exit 1
fi

echo "🚀 Starting deployment process..."

cd ..

cp -r ~/.cache/whisper/ ./models/whisper/

# Build the image
echo "🏗️ Building Docker image..."
docker build -t genassist-app -f ./app/Dockerfile .
if [ $? -ne 0 ]; then
    echo "❌ Docker build failed"
    exit 1
fi

# Run tests and wait for results
# run_tests

# Check test results before proceeding with deployment
if [ $TEST_RESULT -ne 0 ]; then
    echo "❌ Deployment aborted due to test failures"
    exit 1
fi

# Login to ECR
echo "🔑 Logging into ECR..."
echo $ECR_REPO
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "${ECR_REPO}"
#aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 474668385577.dkr.ecr.us-east-1.amazonaws.com

# Tag the image
echo "🏷️ Tagging image..."
docker tag genassist-app:latest "$ECR_REPO:latest"

# Push to ECR
echo "⬆️ Pushing image to ECR..."
docker push "${ECR_REPO}:latest"
if [ $? -ne 0 ]; then
    echo "❌ Docker push failed"
    exit 1
fi

# Force new deployment
echo "🔄 Forcing new ECS deployment..."
aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$ECS_SERVICE" \
    --force-new-deployment

if [ $? -ne 0 ]; then
    echo "❌ ECS deployment failed"
    exit 1
fi

echo "✅ Deployment initiated successfully!"
echo "📊 You can monitor the deployment using:"
echo "aws ecs describe-services --cluster $ECS_CLUSTER --services $ECS_SERVICE"

# Optional: Show deployment status
echo -e "\n🔍 Checking deployment status..."
aws ecs describe-services \
    --cluster "$ECS_CLUSTER" \
    --services "$ECS_SERVICE" \
    --query 'services[0].deployments[*].[status,desiredCount,runningCount]' \
    --output table 