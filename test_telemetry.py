import unittest
import json
import logging
from io import StringIO
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.telemetry.context import (
    set_telemetry_context,
    get_telemetry_context,
    clear_telemetry_context,
)

from shared.telemetry.tracer import Tracer, Span
from shared.telemetry.metrics import MetricsCollector
from shared.telemetry.logging import JSONTelemetryFormatter
from shared.telemetry.middleware import TelemetryMiddleware
from shared.telemetry.routes import register_telemetry_routes


class TestTelemetryContext(unittest.TestCase):
    def setUp(self):
        clear_telemetry_context()

    def tearDown(self):
        clear_telemetry_context()

    def test_context_set_get_clear(self):
        set_telemetry_context(
            request_id="req_123",
            trace_id="trace_abc",
            span_id="span_456",
            tenant_id="tenant_x",
            user_id="user_99"
        )
        ctx = get_telemetry_context()
        self.assertEqual(ctx["request_id"], "req_123")
        self.assertEqual(ctx["trace_id"], "trace_abc")
        self.assertEqual(ctx["span_id"], "span_456")
        self.assertEqual(ctx["tenant_id"], "tenant_x")
        self.assertEqual(ctx["user_id"], "user_99")

        clear_telemetry_context()
        empty_ctx = get_telemetry_context()
        self.assertIsNone(empty_ctx["request_id"])
        self.assertIsNone(empty_ctx["trace_id"])


class TestTracer(unittest.TestCase):
    def setUp(self):
        self.tracer = Tracer(service_name="test-service")

    def test_span_creation_and_context(self):
        with self.tracer.start_span("test_op", attributes={"key": "val"}) as span:
            self.assertEqual(span.name, "test_op")
            self.assertEqual(span.attributes["key"], "val")
            self.assertIsNotNone(span.trace_id)
            self.assertIsNotNone(span.span_id)
            self.assertEqual(span.status, "OK")

        # Check export
        recent = self.tracer.exporter.get_recent_spans()
        self.assertTrue(any(s["name"] == "test_op" for s in recent))

    def test_traceparent_formatting_and_extraction(self):
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        span_id = "00f067aa0ba902b7"
        tp = self.tracer.format_w3c_traceparent(trace_id, span_id)
        self.assertEqual(tp, f"00-{trace_id}-{span_id}-01")

        headers = {"traceparent": tp}
        extracted_trace_id, parent_span_id = self.tracer.extract_headers(headers)
        self.assertEqual(extracted_trace_id, trace_id)
        self.assertEqual(parent_span_id, span_id)


class TestMetricsCollector(unittest.TestCase):
    def setUp(self):
        self.metrics = MetricsCollector()

    def test_http_request_recording(self):
        self.metrics.record_http_request(
            method="POST",
            endpoint="/api/v1/chat",
            status=200,
            duration=0.125,
            tenant_id="tenant_test"
        )
        text = self.metrics.generate_prometheus_text()
        self.assertIn("http_requests_total", text)
        self.assertIn("http_request_duration_seconds", text)
        self.assertIn('method="POST"', text)

    def test_llm_metrics_recording(self):
        self.metrics.record_llm_request(
            model="qwen-2.5",
            prompt_tokens=100,
            completion_tokens=50,
            latency=0.450,
            tenant_id="tenant_test"
        )
        text = self.metrics.generate_prometheus_text()
        self.assertIn("llm_tokens_total", text)
        self.assertIn("llm_latency_seconds", text)
        self.assertIn('model="qwen-2.5"', text)


class TestJSONTelemetryFormatter(unittest.TestCase):
    def test_json_formatting(self):
        set_telemetry_context(request_id="req_test_123", trace_id="trace_test_456")
        formatter = JSONTelemetryFormatter(service_name="test-logger-service")
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Testing telemetry log entry",
            args=(),
            exc_info=None
        )

        formatted_str = formatter.format(record)
        log_json = json.loads(formatted_str)

        self.assertEqual(log_json["service"], "test-logger-service")
        self.assertEqual(log_json["message"], "Testing telemetry log entry")
        self.assertEqual(log_json["request_id"], "req_test_123")
        self.assertEqual(log_json["trace_id"], "trace_test_456")
        clear_telemetry_context()


class TestTelemetryMiddlewareAndRoutes(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI(title="Test App")
        self.app.add_middleware(TelemetryMiddleware, service_name="test-app")
        register_telemetry_routes(self.app)

        @self.app.get("/hello")
        async def hello():
            return {"message": "hello telemetry"}

        self.client = TestClient(self.app)

    def test_middleware_injects_headers(self):
        response = self.client.get("/hello", headers={"X-Tenant-ID": "tenant_test"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Request-ID", response.headers)
        self.assertIn("X-Trace-ID", response.headers)
        self.assertIn("X-Process-Time", response.headers)
        self.assertIn("traceparent", response.headers)

    def test_metrics_endpoint(self):
        # Trigger a request first
        self.client.get("/hello")
        
        metrics_resp = self.client.get("/metrics")
        self.assertEqual(metrics_resp.status_code, 200)
        self.assertIn("http_requests_total", metrics_resp.text)

    def test_traces_endpoint(self):
        # Trigger a request first
        self.client.get("/hello")

        traces_resp = self.client.get("/traces")
        self.assertEqual(traces_resp.status_code, 200)
        data = traces_resp.json()
        self.assertIn("spans", data)
        self.assertGreater(data["count"], 0)


if __name__ == "__main__":
    unittest.main()
