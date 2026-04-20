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


```bash
# Only for development purpooses
pip install -r requirements-dev.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

> **Note:** If using HuggingFace models for the first time, accept the license at https://hf.co/pyannote/segmentation
create .env file from example and put config values

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

### OpenTelemetry and Opik (application traces)

With `USE_OTEL=true`, the backend registers the OpenTelemetry SDK, instruments FastAPI/ASGI, and records spans for each workflow run (`workflow.run`) and workflow node (`workflow.node.execute`). See `backend/.env.example` for variables.

- **Opik (Comet)**: Set `OPIK_OTEL_EXPORT=true` and `OPIK_API_KEY`, `OPIK_WORKSPACE`, `OPIK_PROJECT_NAME`, and usually `OPIK_URL_OVERRIDE` (traces POST to `{OPIK_URL_OVERRIDE}/v1/private/otel/v1/traces`). Alternatively set `OTEL_EXPORTER_OTLP_HEADERS` with `Authorization`, `projectName`, and `Comet-Workspace`. This path uses **OTLP HTTP/protobuf**, as in the [Opik OpenTelemetry docs](https://www.comet.com/docs/opik/integrations/opentelemetry). `USE_OPIK` remains the switch for LangChain `OpikTracer` on `QuestionAnswerer`; platform spans and LLM spans can share one trace when both are enabled and context is preserved.

- **OTLP gRPC**: Set `OTEL_EXPORTER_OTLP_GRPC_ENDPOINT` (for example `localhost:4317`) to send traces to an OpenTelemetry Collector, Tempo, or similar. For a **single** gRPC ingress and export to Opik over HTTP, configure a collector (gRPC receiver, `otlphttp` exporter) instead of duplicating exporters in the app.

- **Node duration metrics**: Histogram `genassist.workflow.node.duration_seconds` is emitted via OTLP gRPC when `OTEL_EXPORTER_OTLP_GRPC_ENDPOINT` is set and `OTEL_METRICS_VIA_GRPC=true`.

- **Local docker compose (OTEL optional)**: Bring up the main dev stack, and add the OTEL stack only when needed:

  ```bash
  docker compose -f docker-compose.dev.yml up -d
  docker compose -f docker-compose.dev.yml -f docker-compose.otel.yml up -d
  ```

  There is **no** collector home page: open **Grafana** at [http://localhost:3010](http://localhost:3010) → **Explore** → data source **Prometheus** → run e.g. `genassist_workflow_node_duration_seconds_bucket` or use **Prometheus UI** at [http://localhost:9090](http://localhost:9090). Collector **zpages** (debug): [http://localhost:55679/debug/tracez](http://localhost:55679/debug/tracez) (not `http://localhost:55679/` alone). For **histogram panels** in Grafana, see [observability/README.md](../observability/README.md).

- **Celery**: Workers do not call `init_opentelemetry()` unless you add it; use Flower for task monitoring until worker bootstrap and trace-context propagation are in place.

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
