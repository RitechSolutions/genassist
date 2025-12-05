
<img width="2752" height="1536" alt="GenAssist_Infographic" src="https://github.com/user-attachments/assets/7f5b636c-ae01-4076-9480-b29ce84bf2ea" />

# GenAssist

GenAssist is an AI-powered platform for managing and leveraging various AI workflows, with a focus on conversation management, analytics, and agent-based interactions.

Documentation: https://docs.genassist.ritech.io/docs/introduction

How-to Videos: https://docs.genassist.ritech.io/docs/workflows/

## Overview

GenAssist provides a comprehensive solution for building, managing, and deploying AI agents with the following key features:

- **User Management**: Authentication, authorization, role-based access control, and API key management
- **AI Agents**: Configure and manage agents with various LLM providers and tools
- **Knowledge Base**: Document management with RAG (Retrieval-Augmented Generation) configuration
- **Analytics**: Performance metrics, conversation analysis, and KPI tracking
- **Conversation Management**: Transcript viewing, conversation analysis, and sentiment analysis
- **Audit Logging**: System activity tracking and change history

## Architecture

### Frontend
- Built with React, TypeScript, Vite, and Tailwind CSS
- Uses shadcn-ui for accessible UI components
- Follows a well-structured component architecture

### Backend
- Python-based API built with FastAPI
- SQLAlchemy ORM with PostgreSQL database
- Follows layered architecture with dependency injection

## Getting Started

### Prerequisites

- Git
- Docker and Docker Compose
- Node.js and npm (for local development)
- Python 3.10+ (for local development)

### Clone the Repository

```bash
# Clone the repository
git clone https://github.com/RitechSolutions/genassist
cd genassist

## Docker Containers
### Prepare .env files
Create a ./frontend/.env environment file based on ./frontend/.env.example
Create a /backend/.env environment file based on ./backend/.env.example

### Build containers from source
```bash
#RUN
docker compose -e ENV=dev -f docker-compose.dev.yml -p genassist_dev up --build -d
#STOP
docker compose -e ENV=dev -f docker-compose.dev.yml -p genassist_dev down
```

### Use container registry
```bash
#RUN
docker compose -f docker-compose.yml -p genassist_local_01 up -d
#STOP
docker compose -f docker-compose.yml -p genassist_local_01 down
```

## Local Development

### Frontend

```bash
cd frontend
```
Create a `.env` file in the root directory of frontend similar to .env.example:
Follow Readme.md for frontend project

Access the frontend app at: http://localhost
User: admin
Password: genadmin

### Backend

```bash
cd backend
```

Create a `.env` file in the root directory of backend similar to .env.example:
Follow Readme.md for backend project

Access the backend API: http://localhost:8000/api
Access API documentation: http://localhost:8000/docs

Celery jobs: http://localhost:5555  (user:user1 password: password1)

## Integration Options

GenAssist provides multiple integration options:

### React Integration

```bash
#Build the plugin
cd plugins/react
npm run build

#Run chat plugin example
cd example-app
npm run dev
```

### IOS Integration

```bash
#Build the plugin
cd plugins/ios
```

## UI Test Automation

```bash
# Frontend Tests
cd ui_tests

npx playwright install
npx playwright test
```

## Backend Testing

```bash
# Backend Tests
cd backend
python -m pytest tests/

# Run tests with coverage
coverage run --source=app -m pytest -v tests && coverage report -m

# Detailed coverage report
python -m pytest tests/ -v --cov=app --cov-report=html
```


