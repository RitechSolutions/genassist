# Observability stack (dev)

Prometheus scrapes the OpenTelemetry Collector (`otel-collector:8889`). Grafana is at **http://localhost:3010**.

## Histogram from the GenAssist app

The backend records OpenTelemetry histogram **`genassist.workflow.node.duration_seconds`** (see `app/core/observability/otel.py`) when:

- `USE_OTEL=true`
- `OTEL_EXPORTER_OTLP_GRPC_ENDPOINT` points at the collector (e.g. `localhost:4317` on the host, `otel-collector:4317` inside Docker)
- `OTEL_METRICS_VIA_GRPC=true`

After export through the collector’s Prometheus exporter, Prometheus usually exposes:

- `genassist_workflow_node_duration_seconds_bucket`
- `genassist_workflow_node_duration_seconds_sum`
- `genassist_workflow_node_duration_seconds_count`

Labels from attributes may appear with dots replaced by underscores, e.g. `genassist_node_type`, `genassist_success`. Verify names in **Prometheus** → **Status** → **Targets**, then **Graph** with autocomplete, or `http://localhost:9090/graph`.

## Grafana: build a histogram / latency panel yourself

1. Open **http://localhost:3010** → **Connections** → **Data sources** → **Prometheus** (or **Explore**).
2. **Heatmap** (distribution over time): panel type **Heatmap**, query:

   ```promql
   sum(rate(genassist_workflow_node_duration_seconds_bucket[$__rate_interval])) by (le)
   ```

3. **Percentiles** (single line chart): panel type **Time series**, queries such as:

   ```promql
   histogram_quantile(0.95, sum(rate(genassist_workflow_node_duration_seconds_bucket[5m])) by (le))
   ```

4. **By node type** (if label exists): add the label to `by (...)`:

   ```promql
   histogram_quantile(0.95, sum(rate(genassist_workflow_node_duration_seconds_bucket[5m])) by (le, genassist_node_type))
   ```

If a query returns no data, the metric name or labels may differ slightly—use Prometheus UI to copy the exact series name.

## Provisioned dashboard

Start the OTEL stack:

```bash
docker compose -f docker-compose.dev.yml -f docker-compose.otel.yml up -d
```

Then open **Dashboards** → folder **OTEL** → **GenAssist — OTEL workflow node histogram**.
