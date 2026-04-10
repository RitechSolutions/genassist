"""
OpenTelemetry bootstrap for FastAPI and workflow instrumentation.

Traces:
- OTLP HTTP/protobuf to Opik (Comet) when USE_OTEL and OPIK_OTEL_EXPORT are enabled.
- Optional second export via OTLP gRPC when OTEL_EXPORTER_OTLP_GRPC_ENDPOINT is set.

Metrics (histogram genassist.workflow.node.duration_seconds):
- Exported with OTLP gRPC when OTEL_EXPORTER_OTLP_GRPC_ENDPOINT is set (e.g. to a collector
  that forwards to Prometheus). Opik's documented ingest is trace-oriented.

Celery: workers do not run this module unless you call init_opentelemetry() from the worker
process and propagate W3C trace context on task payloads; use Flower for task monitoring until then.

Collector fan-out (roadmap OTLP gRPC + Opik HTTP): run an OpenTelemetry Collector with an
otlp receiver (gRPC) and an otlphttp exporter targeting Opik's endpoint, or use dual exporters
from this app (gRPC + HTTP) as configured below.

Env (standard OTEL): OTEL_TRACES_SAMPLER, OTEL_TRACES_SAMPLER_ARG, OTEL_RESOURCE_ATTRIBUTES, etc.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

_initialized: bool = False
_node_duration_histogram: Any = None


def _otel_sdk_disabled() -> bool:
    return os.getenv("OTEL_SDK_DISABLED", "").lower() == "true"


def is_otel_runtime_enabled() -> bool:
    """True when settings enable OTEL and the SDK is not disabled via env."""
    from app.core.config.settings import settings

    return bool(settings.USE_OTEL) and not _otel_sdk_disabled()


def _build_opik_traces_endpoint() -> Optional[str]:
    from app.core.config.settings import settings

    if settings.OPIK_OTEL_TRACES_ENDPOINT:
        return settings.OPIK_OTEL_TRACES_ENDPOINT.strip()
    base = (settings.OPIK_URL_OVERRIDE or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/v1/private/otel/v1/traces"


def _build_opik_otlp_headers() -> dict[str, str]:
    from app.core.config.settings import settings

    headers: dict[str, str] = {}
    if settings.OPIK_API_KEY:
        headers["Authorization"] = settings.OPIK_API_KEY
    if settings.OPIK_PROJECT_NAME:
        headers["projectName"] = settings.OPIK_PROJECT_NAME
    if settings.OPIK_WORKSPACE:
        headers["Comet-Workspace"] = settings.OPIK_WORKSPACE
    return headers


def _parse_otlp_headers_env(raw: Optional[str]) -> dict[str, str]:
    if not raw:
        return {}
    out: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        out[k.strip()] = v.strip()
    return out


def init_opentelemetry(app: Optional["FastAPI"] = None) -> None:
    global _initialized  # pylint: disable=global-statement
    if _initialized:
        return

    from app.core.config.settings import settings

    if not settings.USE_OTEL or _otel_sdk_disabled():
        logger.debug("OpenTelemetry disabled (USE_OTEL=false or OTEL_SDK_DISABLED=true)")
        return

    from opentelemetry import metrics, trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    service_name = os.getenv("OTEL_SERVICE_NAME") or settings.OTEL_SERVICE_NAME
    version = settings.API_VERSION or "0"
    resource_attrs: dict[str, Any] = {
        "service.name": service_name,
        "service.version": str(version),
    }
    extra = os.getenv("OTEL_RESOURCE_ATTRIBUTES")
    if extra:
        for item in extra.split(","):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                resource_attrs[k.strip()] = v.strip()
    resource = Resource.create(resource_attrs)

    ratio = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0"))
    sampler = ParentBased(TraceIdRatioBased(ratio))

    provider = TracerProvider(resource=resource, sampler=sampler)

    span_processors_added = 0

    if settings.OPIK_OTEL_EXPORT:
        endpoint = _build_opik_traces_endpoint()
        headers = _build_opik_otlp_headers()
        headers.update(_parse_otlp_headers_env(os.getenv("OTEL_EXPORTER_OTLP_HEADERS")))
        auth_ok = headers.get("Authorization") or headers.get("authorization")
        if endpoint and auth_ok:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter as HttpOTLPSpanExporter,
                )
            except ModuleNotFoundError:
                logger.error(
                    "Opik OTLP HTTP export needs opentelemetry-exporter-otlp-proto-http "
                    "(pip install opentelemetry-exporter-otlp-proto-http==1.36.0 or "
                    "pip install -r requirements-main.txt)"
                )
            else:
                exporter = HttpOTLPSpanExporter(endpoint=endpoint, headers=headers)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                span_processors_added += 1
                logger.info("OpenTelemetry: OTLP HTTP trace export enabled for Opik")
        else:
            logger.warning(
                "OPIK_OTEL_EXPORT is true but Opik OTLP endpoint or Authorization header is "
                "missing; set OPIK_URL_OVERRIDE / OPIK_OTEL_TRACES_ENDPOINT and OPIK_API_KEY"
            )

    grpc_endpoint = (
        os.getenv("OTEL_EXPORTER_OTLP_GRPC_ENDPOINT")
        or settings.OTEL_EXPORTER_OTLP_GRPC_ENDPOINT
        or ""
    ).strip()
    if grpc_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter as GrpcOTLPSpanExporter,
        )

        insecure = (
            os.getenv("OTEL_EXPORTER_OTLP_GRPC_INSECURE", "true").lower() == "true"
        )
        exporter = GrpcOTLPSpanExporter(endpoint=grpc_endpoint, insecure=insecure)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        span_processors_added += 1
        logger.info(
            "OpenTelemetry: OTLP gRPC trace export enabled (endpoint=%s)", grpc_endpoint
        )

    if span_processors_added == 0:
        logger.warning(
            "USE_OTEL is true but no span exporters configured; enable OPIK_OTEL_EXPORT with "
            "Opik credentials or set OTEL_EXPORTER_OTLP_GRPC_ENDPOINT"
        )

    trace.set_tracer_provider(provider)

    global _node_duration_histogram  # pylint: disable=global-statement
    if grpc_endpoint and settings.OTEL_METRICS_VIA_GRPC:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

            insecure = (
                os.getenv("OTEL_EXPORTER_OTLP_GRPC_INSECURE", "true").lower() == "true"
            )
            metric_exporter = OTLPMetricExporter(
                endpoint=grpc_endpoint, insecure=insecure
            )
            reader = PeriodicExportingMetricReader(metric_exporter)
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
            metrics.set_meter_provider(meter_provider)
            meter = metrics.get_meter("genassist.workflow")
            _node_duration_histogram = meter.create_histogram(
                "genassist.workflow.node.duration_seconds",
                unit="s",
                description="Wall time for workflow node execute()",
            )
            logger.info(
                "OpenTelemetry: OTLP gRPC metrics export enabled (histogram for node duration)"
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception("Failed to initialize OpenTelemetry metrics export")

    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry: FastAPI/ASGI instrumentation enabled")

    _initialized = True


def shutdown_opentelemetry() -> None:
    global _initialized, _node_duration_histogram  # pylint: disable=global-statement
    if not _initialized:
        return
    from opentelemetry import metrics, trace

    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if callable(shutdown):
        shutdown()

    mp = metrics.get_meter_provider()
    shutdown_m = getattr(mp, "shutdown", None)
    if callable(shutdown_m):
        shutdown_m()

    _node_duration_histogram = None
    _initialized = False
    logger.debug("OpenTelemetry shut down")


def record_workflow_node_duration(
    node_type: str, duration_seconds: float, success: bool
) -> None:
    h = _node_duration_histogram
    if h is None:
        return
    h.record(
        max(0.0, duration_seconds),
        {
            "genassist.node.type": node_type or "unknown",
            "genassist.success": "true" if success else "false",
        },
    )
