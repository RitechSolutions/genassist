# OpenTelemetry (OTEL)

## Overview

GenAssist has an **optional** OpenTelemetry implementation focused on:

- **Traces**: FastAPI/ASGI request instrumentation plus workflow spans (`workflow.run`, `workflow.node.execute`).
- **Metrics**: A workflow node duration histogram (`genassist.workflow.node.duration_seconds`) exported via **OTLP gRPC**.

Everything is gated behind configuration so existing functionality remains unchanged unless OTEL is explicitly enabled.

## Functional analysis (current behavior)

### What gets instrumented

- **FastAPI / ASGI auto-instrumentation**
  - Enabled when OTEL is initialized with a `FastAPI` app instance.
  - Produces spans for inbound requests (ASGI).

- **Workflow execution spans**
  - `workflow.run`: one span per workflow execution.
  - `workflow.node.execute`: one span per node execution (child span of the workflow run span when context is present).

- **Workflow node duration metric (histogram)**
  - Metric name: `genassist.workflow.node.duration_seconds`
  - Unit: seconds (`s`)
  - Recorded for every node execution in a `finally` block, regardless of success/failure.
  - Attributes:
    - `genassist.node.type`
    - `genassist.success` (`"true"` / `"false"`)

### Runtime gating and compatibility

- **Primary switch**: `USE_OTEL=true` enables OTEL SDK initialization.
- **Hard-disable switch**: `OTEL_SDK_DISABLED=true` forces OTEL off even if `USE_OTEL=true`.
- **No-exporter behavior**: if `USE_OTEL=true` but no span exporter is configured, the app will still run normally; it logs a warning and continues.
- **Celery**: workers do **not** initialize OTEL by default; queue spans and cross-process trace propagation are not currently enabled unless you add worker bootstrap + context propagation.

### Export paths (what data goes where)

#### Traces

The backend can export traces to either (or both) destinations:

- **Opik (Comet) via OTLP HTTP/protobuf**
  - Enable with `OPIK_OTEL_EXPORT=true` and Opik credentials/headers.
  - Endpoint is derived from `OPIK_OTEL_TRACES_ENDPOINT` or `OPIK_URL_OVERRIDE`.

- **Collector / Tempo / any OTLP endpoint via OTLP gRPC**
  - Enable by setting `OTEL_EXPORTER_OTLP_GRPC_ENDPOINT` (example: `localhost:4317`).
  - Uses insecure transport by default unless `OTEL_EXPORTER_OTLP_GRPC_INSECURE=false`.

#### Metrics

- The workflow node duration histogram is exported via **OTLP gRPC** to the same `OTEL_EXPORTER_OTLP_GRPC_ENDPOINT` when:
  - `OTEL_EXPORTER_OTLP_GRPC_ENDPOINT` is set, and
  - `OTEL_METRICS_VIA_GRPC=true`

This is intentionally conservative: if there is no OTLP gRPC endpoint configured, the metric is not exported.

## Mermaid workflow diagram (current implementation)

```mermaid
flowchart LR
  %% ===== Application side =====
  subgraph App[GenAssist backend (FastAPI)]
    A1[Incoming HTTP request] --> A2[FastAPI/ASGI instrumentation]
    A2 -->|creates spans| Treq[Request spans]

    A3[WorkflowEngine.execute_from_node()] -->|start span| Wrun[Span: workflow.run]
    Wrun --> A4[BaseNode.execute() per node]
    A4 -->|start span| Wnode[Span: workflow.node.execute]
    A4 -->|finally record duration| M1[Histogram: genassist.workflow.node.duration_seconds]
  end

  %% ===== Exporters in the app =====
  subgraph Exporters[OTEL SDK exporters (configured at runtime)]
    E1[OTLP HTTP trace exporter\n(Opik)]:::opt
    E2[OTLP gRPC trace exporter\n(Collector/Tempo/...)]:::opt
    E3[OTLP gRPC metric exporter\n(Collector)]:::opt
  end

  Treq --> E1
  Wrun --> E1
  Wnode --> E1

  Treq --> E2
  Wrun --> E2
  Wnode --> E2

  M1 --> E3

  %% ===== Local OTEL stack (optional) =====
  subgraph Stack[Local OTEL dev stack (docker-compose.otel.yml)]
    C[otel-collector\nOTLP receivers :4317/:4318]
    C -->|metrics pipeline| Pexp[Prometheus exporter :8889/metrics]
    P[Prometheus :9090] -->|scrape :8889 + :8888| Pexp
    G[Grafana :3010] -->|query| P
    Z[zpages :55679/debug/tracez]
    C --> Z
  end

  E2 --> C
  E3 --> C

  %% Collector traces pipeline currently exports to debug only
  C -->|traces pipeline| D[debug exporter (collector logs)]

  classDef opt fill:#f7f7f7,stroke:#999,stroke-dasharray: 3 3,color:#111;
```

## Configuration

### Backend env vars

These are the key variables (see `backend/.env.example` and `backend/app/core/config/settings.py`):

- **Enable OTEL runtime**
  - `USE_OTEL=true|false` (default: `false`)
  - `OTEL_SDK_DISABLED=true|false` (default: `false`)
  - `OTEL_SERVICE_NAME=genassist-api` (default from settings; can be overridden via env)

- **Sampling**
  - `OTEL_TRACES_SAMPLER_ARG=1.0` (ratio for `ParentBased(TraceIdRatioBased(ratio))`)

- **Trace export to Opik (OTLP HTTP/protobuf)**
  - `OPIK_OTEL_EXPORT=true|false`
  - `OPIK_URL_OVERRIDE=...` (used to derive `{base}/v1/private/otel/v1/traces`) or `OPIK_OTEL_TRACES_ENDPOINT=...`
  - `OPIK_API_KEY=...`
  - `OPIK_WORKSPACE=...`
  - `OPIK_PROJECT_NAME=...`
  - Alternative/extra: `OTEL_EXPORTER_OTLP_HEADERS=Authorization=...,projectName=...,Comet-Workspace=...`

- **Trace export to OTLP gRPC**
  - `OTEL_EXPORTER_OTLP_GRPC_ENDPOINT=localhost:4317`
  - `OTEL_EXPORTER_OTLP_GRPC_INSECURE=true|false` (default: `true`)

- **Metric export (workflow node duration histogram)**
  - `OTEL_METRICS_VIA_GRPC=true|false` (default: `true`)
  - Requires `OTEL_EXPORTER_OTLP_GRPC_ENDPOINT` to be set.

### Local OTEL stack (collector + prometheus + grafana)

Start the dev stack plus OTEL stack:

```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml -f docker-compose.otel.yml up -d
```

Useful endpoints:

- **Grafana**: `http://localhost:3010` (Dashboards → folder `OTEL`)
- **Prometheus**: `http://localhost:9090`
- **Collector exported metrics**: `http://localhost:8889/metrics`
- **Collector zpages**: `http://localhost:55679/debug/tracez`

## Validating the implementation (quick checks)

### Metrics appear in Prometheus

When OTEL is enabled and `OTEL_EXPORTER_OTLP_GRPC_ENDPOINT` points to the collector, Prometheus typically shows:

- `genassist_workflow_node_duration_seconds_bucket`
- `genassist_workflow_node_duration_seconds_sum`
- `genassist_workflow_node_duration_seconds_count`

Note: attribute keys may be normalized by the Prometheus exporter (e.g., dots become underscores).

### Traces in the local stack

The current dev collector config exports **traces to the `debug` exporter** (collector logs), not to a tracing backend UI. For UI-based trace exploration, add a trace backend (e.g., Tempo/Jaeger) and a matching collector exporter, or export traces to Opik.

## Relevant implementation files

- Backend OTEL bootstrap: `backend/app/core/observability/otel.py`
- Workflow spans + metric recording:
  - `backend/app/modules/workflow/engine/workflow_engine.py` (`workflow.run`)
  - `backend/app/modules/workflow/engine/base_node.py` (`workflow.node.execute` + histogram record)
- Local dev stack:
  - `docker-compose.otel.yml`
  - `observability/otel-collector-config.yaml`
  - `observability/prometheus-otel.yml`
  - `observability/grafana/dashboards/genassist-otel-workflow.json`

