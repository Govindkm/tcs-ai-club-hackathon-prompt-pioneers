"""OpenTelemetry tracing setup for Strands agents (console and/or OTLP export).

Call setup_telemetry() once before any Agent is created; standard OTEL_* env
vars (OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_HEADERS, OTEL_SERVICE_NAME)
are read by the underlying OpenTelemetry SDK per the Strands tracing docs:
https://strandsagents.com/docs/user-guide/observability-evaluation/traces/
"""
from __future__ import annotations

import os

from strands.telemetry.config import StrandsTelemetry

_configured = False


def setup_telemetry() -> None:
    """Configure Strands/OpenTelemetry trace exporters from env vars (idempotent)."""
    global _configured
    if _configured:
        return

    telemetry = StrandsTelemetry()

    if os.getenv("STRANDS_TRACE_CONSOLE", "true").lower() == "true":
        telemetry.setup_console_exporter()

    if os.getenv("STRANDS_TRACE_OTLP", "false").lower() == "true":
        telemetry.setup_otlp_exporter()

    _configured = True
