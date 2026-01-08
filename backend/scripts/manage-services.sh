#!/bin/bash

# Function to display usage information
function show_usage {
    echo "Usage: $0 [OPTION]"
    echo "Manage Docker Compose services for GenAgent"
    echo ""
    echo "Options:"
    echo "  start-all       Start all services"
    echo "  stop-all        Stop all services"
    echo "  start-db        Start only DB"
    echo "  stop-db         Stop only DB"
    echo "  start-neo4j     Start only Neo4j"
    echo "  stop-neo4j      Stop only Neo4j"
    echo "  start-chroma    Start only Chroma"
    echo "  stop-chroma     Stop only Chroma"
    echo "  start-app       Start only the application"
    echo "  stop-app        Stop only the application"
    echo "  logs [service]  Show logs for a specific service (neo4j, chroma, app) or all if not specified"
    echo "  status          Show status of all services"
    echo "  clean           Remove all containers and volumes (WARNING: This will delete all data)"
    echo ""
    echo "Examples:"
    echo "  $0 start-all"
    echo "  $0 logs neo4j"
    echo "  $0 status"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running or not installed"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed"
    exit 1
fi

# Process command line arguments
case "$1" in
    start-all)
        echo "Starting all services..."
        docker-compose up -d
        ;;
    stop-all)
        echo "Stopping all services..."
        docker-compose down
        ;;
    start-db)
        echo "Starting DB..."
        docker-compose up -d db
        ;;
    stop-db)
        echo "Stopping DB..."
        docker-compose stop db
        ;;
    start-neo4j)
        echo "Starting Neo4j..."
        docker-compose up -d neo4j
        ;;
    stop-neo4j)
        echo "Stopping Neo4j..."
        docker-compose stop neo4j
        ;;
    start-chroma)
        echo "Starting Chroma..."
        docker-compose up -d chroma
        ;;
    stop-chroma)
        echo "Stopping Chroma..."
        docker-compose stop chroma
        ;;
    start-app)
        echo "Starting application..."
        docker-compose up -d app
        ;;
    stop-app)
        echo "Stopping application..."
        docker-compose stop app
        ;;
    logs)
        if [ -z "$2" ]; then
            echo "Showing logs for all services..."
            docker-compose logs -f
        else
            echo "Showing logs for $2..."
            docker-compose logs -f "$2"
        fi
        ;;
    status)
        echo "Service status:"
        docker-compose ps
        ;;
    clean)
        echo "WARNING: This will remove all containers and volumes, deleting all data."
        read -p "Are you sure you want to continue? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Removing all containers and volumes..."
            docker-compose down -v
            echo "Cleanup complete."
        else
            echo "Operation cancelled."
        fi
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

exit 0 