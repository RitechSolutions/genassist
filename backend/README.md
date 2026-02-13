# GenAssist Backend

FastAPI-based backend API for GenAssist.

## Prerequisites

- Python 3.12+
- Docker and Docker Compose
- (Optional) NVIDIA GPU with Container Toolkit for Whisper acceleration

## Quick Start

### 1. Setup Virtual Environment

```bash
# Create and activate virtual environment
python3.12 -m venv genassist_env
source genassist_env/bin/activate  # Linux/Mac
# genassist_env\Scripts\activate   # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements-main.txt
pip install -r requirements-app.txt
pip install -r requirements-rag.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

> **Note:** If using HuggingFace models for the first time, accept the license at https://hf.co/pyannote/segmentation

### 4. Start Infrastructure Services

```bash
# From repository root
make services

# Or using docker compose directly
docker compose -f docker/docker-compose.base.yml -f docker/docker-compose.build.yml up -d db redis chroma qdrant whisper
```

> **Important:** When running backend locally (not in Docker), ensure `CHROMA_HOST=localhost` and `CHROMA_PORT=8005` are set in your `.env` file.

### 5. Run the Application

```bash
python run.py
```

### 6. Access the API

- **Swagger UI:** http://localhost:8000/docs
- **API Key:** `test123`
- **User Auth:** `admin` / `genadmin`

## Development

### Linting

```bash
pylint app
```

### Testing

```bash
# Run all tests
pytest .

# Run with coverage
pytest --cov=app --cov-report=html
```

### Debugging in VSCode

1. Open `run.py` in VSCode
2. Ensure the Python interpreter is set to `genassist_env`
3. Press F5 or use the Run/Debug panel

### Deactivate Virtual Environment

```bash
deactivate
```

## Docker

### Build and Run Locally

```bash
# From repository root (recommended)
make dev-backend

# Or build manually
docker build -t genassist-backend:local .
docker run genassist-backend:local
```

## Monitoring (Optional)

### System Metrics Dashboard

```bash
cd monitoring
docker compose up -d
```

Access Grafana at http://localhost:9000

Services started:
- Prometheus (metrics collection)
- cAdvisor (container metrics)
- node-exporter (host metrics)
- Grafana (dashboards)

### Centralized Logging (ELK Stack)

```bash
cd elk-logs
docker compose up -d
```

Access Kibana at http://localhost:5601

Services started:
- Elasticsearch
- Logstash
- Filebeat
- Kibana

## System Setup (Clean Linux Install)

<details>
<summary>Click to expand installation instructions</summary>

### Install Python via pyenv

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y software-properties-common build-essential libssl-dev \
  zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
  libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev ffmpeg

# Install pyenv
curl -fsSL https://pyenv.run | bash

# Install Python 3.12
pyenv install 3.12
pyenv global 3.12
```

### Install NVIDIA Container Toolkit (for GPU support)

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
```

</details>
