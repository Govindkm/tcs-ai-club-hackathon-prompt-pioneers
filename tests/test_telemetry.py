"""Tests for OpenTelemetry tracing setup (console/OTLP exporters)."""
import src.telemetry as telemetry_module
from src.telemetry import setup_telemetry


def test_setup_telemetry_is_idempotent(monkeypatch):
    monkeypatch.setattr(telemetry_module, "_configured", False)
    setup_telemetry()
    assert telemetry_module._configured is True
    setup_telemetry()  # second call must be a no-op, not re-configure/raise
