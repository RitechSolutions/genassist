# Exit on error
$ErrorActionPreference = "Stop"

# Function to check if a command exists
function Test-Command($Command) {
    return [bool](Get-Command -Name $Command -ErrorAction SilentlyContinue)
}

# Function to create test database
function New-TestDatabase {
    $dbContainerName = "genassist-test-db-$(Get-Random)"
    
    Write-Host "🗄️ Creating test database container..." -ForegroundColor Cyan
    docker run -d --name $dbContainerName `
        -e POSTGRES_USER=test_user `
        -e POSTGRES_PASSWORD=test_password `
        -e POSTGRES_DB=test_db `
        -p 5433:5432 `
        postgres:15

    # Wait for database to be ready
    Write-Host "⏳ Waiting for database to be ready..." -ForegroundColor Cyan
    Start-Sleep -Seconds 10

    # Check if database is running
    $dbStatus = docker inspect -f '{{.State.Status}}' $dbContainerName
    if ($dbStatus -ne "running") {
        Write-Host "❌ Database container failed to start" -ForegroundColor Red
        docker logs $dbContainerName
        throw "Database container failed to start"
    }

    return $dbContainerName
}

# Function to run tests
function Run-Tests {
    Write-Host "🧪 Running tests..." -ForegroundColor Cyan
    
    # Create test database
    $dbContainerName = New-TestDatabase
    
    # Create a temporary test container
    $containerName = "genassist-test-$(Get-Random)"
    
    try {
        # Run the container in detached mode with test environment variables
        Write-Host "🚀 Starting test container..." -ForegroundColor Cyan
        docker run -d --name $containerName `
            -e DATABASE_URL="postgresql://test_user:test_password@host.docker.internal:5433/test_db" `
            -e ENVIRONMENT="test" `
            -e LOG_LEVEL="DEBUG" `
            -e TESTING="true" `
            -e API_KEY="test_key" `
            -e SECRET_KEY="test_secret" `
            -p 8000:8000 `
            genassist-app:latest

        # Wait for the container to be healthy
        Write-Host "⏳ Waiting for container to be healthy..." -ForegroundColor Cyan
        Start-Sleep -Seconds 10

        # Check if container is running
        $containerStatus = docker inspect -f '{{.State.Status}}' $containerName
        if ($containerStatus -ne "running") {
            Write-Host "❌ Container failed to start properly" -ForegroundColor Red
            docker logs $containerName
            throw "Container health check failed"
        }

        # Run pytest inside the container with test environment
        Write-Host "📊 Running pytest..." -ForegroundColor Cyan
        docker exec $containerName python -m pytest tests/ -v

        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Tests failed" -ForegroundColor Red
            throw "Tests failed"
        }

        Write-Host "✅ Tests passed successfully!" -ForegroundColor Green
    }
    finally {
        # Clean up: stop and remove the test containers
        Write-Host "🧹 Cleaning up test containers..." -ForegroundColor Cyan
        docker stop $containerName 2>$null
        docker rm $containerName 2>$null
        docker stop $dbContainerName 2>$null
        docker rm $dbContainerName 2>$null
    }
}

# Check prerequisites
Write-Host "🔍 Checking prerequisites..." -ForegroundColor Cyan

# Check AWS CLI
if (-not (Test-Command "aws")) {
    Write-Host "❌ AWS CLI is not installed. Please install it from: https://aws.amazon.com/cli/" -ForegroundColor Red
    exit 1
}

# Check Docker
if (-not (Test-Command "docker")) {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop for Windows." -ForegroundColor Red
    exit 1
}

# Check Terraform
if (-not (Test-Command "terraform")) {
    Write-Host "❌ Terraform is not installed. Please install it from: https://www.terraform.io/downloads.html" -ForegroundColor Red
    exit 1
}

# Get Terraform outputs
Write-Host "📡 Getting Terraform outputs..." -ForegroundColor Cyan
$ECR_REPO = terraform output -raw ecr_repository_url
$ECS_CLUSTER = terraform output -raw ecs_cluster_name
$ECS_SERVICE = terraform output -raw ecs_service_name

if (-not $ECR_REPO -or -not $ECS_CLUSTER -or -not $ECS_SERVICE) {
    Write-Host "❌ Failed to get required Terraform outputs. Make sure you're in the correct directory and Terraform is initialized." -ForegroundColor Red
    exit 1
}

Write-Host "🚀 Starting deployment process..." -ForegroundColor Green

# Build the image
Write-Host "🏗️ Building Docker image..." -ForegroundColor Cyan
docker build -t genassist-app -f ./app/Dockerfile .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed" -ForegroundColor Red
    exit 1
}

# Run tests
Run-Tests

# Login to ECR
Write-Host "🔑 Logging into ECR..." -ForegroundColor Cyan
$ecrPassword = aws ecr get-login-password --region us-east-1
$ecrPassword | docker login --username AWS --password-stdin $ECR_REPO

# Tag the image
Write-Host "🏷️ Tagging image..." -ForegroundColor Cyan
docker tag genassist-app:latest "${ECR_REPO}:latest"

# Push to ECR
Write-Host "⬆️ Pushing image to ECR..." -ForegroundColor Cyan
docker push "${ECR_REPO}:latest"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker push failed" -ForegroundColor Red
    exit 1
}

# Force new deployment
Write-Host "🔄 Forcing new ECS deployment..." -ForegroundColor Cyan
aws ecs update-service `
    --cluster $ECS_CLUSTER `
    --service $ECS_SERVICE `
    --force-new-deployment

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ ECS deployment failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Deployment initiated successfully!" -ForegroundColor Green
Write-Host "📊 You can monitor the deployment using:" -ForegroundColor Yellow
Write-Host "aws ecs describe-services --cluster $ECS_CLUSTER --services $ECS_SERVICE" -ForegroundColor Gray

# Optional: Show deployment status
Write-Host "`n🔍 Checking deployment status..." -ForegroundColor Cyan
aws ecs describe-services `
    --cluster $ECS_CLUSTER `
    --services $ECS_SERVICE `
    --query 'services[0].deployments[*].[status,desiredCount,runningCount]' `
    --output table 