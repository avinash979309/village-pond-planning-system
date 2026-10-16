"""
OpenTelemetry setup for Village Pond Planning System.

Exports:
  - Traces  → Jaeger (OTLP gRPC, localhost:4317)
  - Metrics → Prometheus (exposed on /metrics via prometheus_client)
  - Logs    → OTLP (same Jaeger endpoint) + Python logging bridge

Call setup_telemetry() once at app startup (main.py).
"""

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# ── Config ────────────────────────────────────────────────────────────────────
SERVICE_NAME = "village-pond-api"
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

_resource = Resource.create({"service.name": SERVICE_NAME})

# ── Module-level handles (populated by setup_telemetry) ──────────────────────
tracer: trace.Tracer = None          # noqa: F841  used by other modules
meter:  metrics.Meter = None         # noqa: F841  used by other modules

# Metrics instruments (created after meter is ready)
analysis_counter        = None
analysis_duration       = None
cache_hit_counter       = None
cache_miss_counter      = None
active_analyses_gauge   = None


def setup_telemetry(app) -> None:
    """Wire up OTel SDK and instrument the FastAPI app. Call once at startup."""
    global tracer, meter
    global analysis_counter, analysis_duration
    global cache_hit_counter, cache_miss_counter, active_analyses_gauge

    # ── Traces ────────────────────────────────────────────────────────────────
    tp = TracerProvider(resource=_resource)
    tp.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True))
    )
    trace.set_tracer_provider(tp)
    tracer = trace.get_tracer(SERVICE_NAME)

    # ── Metrics ───────────────────────────────────────────────────────────────
    mp = MeterProvider(
        resource=_resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=OTEL_ENDPOINT, insecure=True),
                export_interval_millis=15_000,
            )
        ],
    )
    metrics.set_meter_provider(mp)
    meter = metrics.get_meter(SERVICE_NAME)

    analysis_counter = meter.create_counter(
        "pond.analysis.total",
        description="Total pond analyses completed",
        unit="1",
    )
    analysis_duration = meter.create_histogram(
        "pond.analysis.duration_seconds",
        description="Wall-clock time for each analysis run",
        unit="s",
    )
    cache_hit_counter = meter.create_counter(
        "pond.cache.hits",
        description="Redis cache hits on /analyzeArea",
        unit="1",
    )
    cache_miss_counter = meter.create_counter(
        "pond.cache.misses",
        description="Redis cache misses on /analyzeArea",
        unit="1",
    )
    active_analyses_gauge = meter.create_up_down_counter(
        "pond.analysis.active",
        description="Analyses currently running (0 or 1 due to mutex)",
        unit="1",
    )

    # ── Logs ──────────────────────────────────────────────────────────────────
    lp = LoggerProvider(resource=_resource)
    lp.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=OTEL_ENDPOINT, insecure=True))
    )
    set_logger_provider(lp)
    # Bridge existing Python logging → OTel logs
    LoggingInstrumentor().instrument(set_logging_format=True)

    # ── Auto-instrument FastAPI + httpx ───────────────────────────────────────
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()

    logging.getLogger(__name__).info(
        "OpenTelemetry configured: service=%s endpoint=%s",
        SERVICE_NAME, OTEL_ENDPOINT,
    )
