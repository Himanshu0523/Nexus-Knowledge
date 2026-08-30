import time
import threading
from typing import Dict, List, Tuple, Any, Optional

try:
    import prometheus_client
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False


class MetricValue:
    """Represents a metric series with specific label values."""
    def __init__(self):
        self.value: float = 0.0
        # Histogram specific
        self.count: int = 0
        self.sum: float = 0.0
        # Buckets for histograms: (le_threshold, count_le)
        # Default buckets for latency/duration in seconds
        self.buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self.bucket_counts: Dict[float, int] = {b: 0 for b in self.buckets}
        self.bucket_counts[float("inf")] = 0


class Metric:
    def __init__(self, name: str, help_text: str, metric_type: str, label_names: List[str]):
        self.name = name
        self.help_text = help_text
        self.metric_type = metric_type  # 'counter', 'gauge', 'histogram'
        self.label_names = label_names
        self.series: Dict[Tuple[str, ...], MetricValue] = {}
        self._lock = threading.Lock()

    def _get_series(self, labels: Dict[str, str]) -> MetricValue:
        label_key = tuple(labels.get(lbl, "unknown") for lbl in self.label_names)
        if label_key not in self.series:
            self.series[label_key] = MetricValue()
        return self.series[label_key]

    def inc(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        labels = labels or {}
        with self._lock:
            mv = self._get_series(labels)
            mv.value += value

    def dec(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        labels = labels or {}
        with self._lock:
            mv = self._get_series(labels)
            mv.value -= value

    def set(self, value: float, labels: Optional[Dict[str, str]] = None):
        labels = labels or {}
        with self._lock:
            mv = self._get_series(labels)
            mv.value = value

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        labels = labels or {}
        with self._lock:
            mv = self._get_series(labels)
            mv.count += 1
            mv.sum += value
            mv.value = mv.sum  # sum of observations
            for b in mv.buckets:
                if value <= b:
                    mv.bucket_counts[b] += 1
            mv.bucket_counts[float("inf")] += 1


class MetricsCollector:
    """
    Prometheus-compatible Metrics Collector.
    Provides standard system & domain metrics with low-overhead exposition format.
    """

    def __init__(self):
        self.metrics: Dict[str, Metric] = {}
        self._lock = threading.Lock()
        self._register_default_metrics()

    def _register(self, name: str, help_text: str, metric_type: str, label_names: List[str]) -> Metric:
        metric = Metric(name, help_text, metric_type, label_names)
        self.metrics[name] = metric
        return metric

    def _register_default_metrics(self):
        # 1. HTTP Metrics
        self.http_requests_total = self._register(
            "http_requests_total",
            "Total HTTP requests received",
            "counter",
            ["method", "endpoint", "status", "tenant_id"]
        )
        self.http_request_duration_seconds = self._register(
            "http_request_duration_seconds",
            "HTTP request handling latency in seconds",
            "histogram",
            ["method", "endpoint", "tenant_id"]
        )
        self.sse_active_connections = self._register(
            "sse_active_connections",
            "Currently active Server-Sent Events (SSE) connections",
            "gauge",
            ["endpoint", "tenant_id"]
        )

        # 2. LLM Metrics
        self.llm_requests_total = self._register(
            "llm_requests_total",
            "Total LLM generation requests",
            "counter",
            ["provider", "model", "status", "tenant_id"]
        )
        self.llm_request_duration_seconds = self._register(
            "llm_request_duration_seconds",
            "LLM API request latency in seconds",
            "histogram",
            ["provider", "model", "tenant_id"]
        )
        self.llm_tokens_total = self._register(
            "llm_tokens_total",
            "Total LLM tokens consumed",
            "counter",
            ["provider", "model", "type", "tenant_id"]  # type: input / output
        )

        # 3. RAG & VectorDB Metrics
        self.rag_operations_total = self._register(
            "rag_operations_total",
            "Total RAG search and retrieval operations",
            "counter",
            ["operation", "status", "tenant_id"]
        )
        self.rag_operation_duration_seconds = self._register(
            "rag_operation_duration_seconds",
            "RAG operation latency in seconds",
            "histogram",
            ["operation", "tenant_id"]
        )

        # 4. Database Metrics
        self.db_operations_total = self._register(
            "db_operations_total",
            "Total database queries and commands",
            "counter",
            ["database", "operation", "status"]
        )
        self.db_operation_duration_seconds = self._register(
            "db_operation_duration_seconds",
            "Database operation latency in seconds",
            "histogram",
            ["database", "operation"]
        )

        # 5. Event Bus (Kafka) Metrics
        self.kafka_messages_total = self._register(
            "kafka_messages_total",
            "Total Kafka messages processed or published",
            "counter",
            ["topic", "group_id", "status"]
        )
        self.kafka_consumer_lag = self._register(
            "kafka_consumer_lag",
            "Current estimated Kafka consumer group lag",
            "gauge",
            ["topic", "group_id"]
        )

        # 6. Agent & Tool Metrics
        self.tool_calls_total = self._register(
            "tool_calls_total",
            "Total AI Agent tool invocations",
            "counter",
            ["tool_name", "status", "tenant_id"]
        )
        self.tool_call_duration_seconds = self._register(
            "tool_call_duration_seconds",
            "Tool execution duration in seconds",
            "histogram",
            ["tool_name", "tenant_id"]
        )

        # 7. Tenant Usage Aggregation Metrics
        self.tenant_requests_total = self._register(
            "tenant_requests_total",
            "Aggregated request count per tenant",
            "counter",
            ["tenant_id"]
        )
        self.tenant_tokens_total = self._register(
            "tenant_tokens_total",
            "Aggregated token usage per tenant",
            "counter",
            ["tenant_id"]
        )

    def record_http_request(self, method: str, endpoint: str, status: int, duration: float, tenant_id: str = "default"):
        lbls = {"method": method, "endpoint": endpoint, "status": str(status), "tenant_id": tenant_id}
        self.http_requests_total.inc(1, lbls)
        self.http_request_duration_seconds.observe(duration, {"method": method, "endpoint": endpoint, "tenant_id": tenant_id})
        self.tenant_requests_total.inc(1, {"tenant_id": tenant_id})

    def record_llm_request(self, provider: str, model: str, status: str, duration: float, input_tokens: int = 0, output_tokens: int = 0, tenant_id: str = "default"):
        lbls = {"provider": provider, "model": model, "status": status, "tenant_id": tenant_id}
        self.llm_requests_total.inc(1, lbls)
        self.llm_request_duration_seconds.observe(duration, {"provider": provider, "model": model, "tenant_id": tenant_id})
        if input_tokens > 0:
            self.llm_tokens_total.inc(input_tokens, {"provider": provider, "model": model, "type": "input", "tenant_id": tenant_id})
            self.tenant_tokens_total.inc(input_tokens, {"tenant_id": tenant_id})
        if output_tokens > 0:
            self.llm_tokens_total.inc(output_tokens, {"provider": provider, "model": model, "type": "output", "tenant_id": tenant_id})
            self.tenant_tokens_total.inc(output_tokens, {"tenant_id": tenant_id})

    def record_rag_operation(self, operation: str, status: str, duration: float, tenant_id: str = "default"):
        self.rag_operations_total.inc(1, {"operation": operation, "status": status, "tenant_id": tenant_id})
        self.rag_operation_duration_seconds.observe(duration, {"operation": operation, "tenant_id": tenant_id})

    def record_db_operation(self, database: str, operation: str, status: str, duration: float):
        self.db_operations_total.inc(1, {"database": database, "operation": operation, "status": status})
        self.db_operation_duration_seconds.observe(duration, {"database": database, "operation": operation})

    def record_kafka_event(self, topic: str, group_id: str, status: str):
        self.kafka_messages_total.inc(1, {"topic": topic, "group_id": group_id, "status": status})

    def record_tool_call(self, tool_name: str, status: str, duration: float, tenant_id: str = "default"):
        self.tool_calls_total.inc(1, {"tool_name": tool_name, "status": status, "tenant_id": tenant_id})
        self.tool_call_duration_seconds.observe(duration, {"tool_name": tool_name, "tenant_id": tenant_id})

    def generate_prometheus_text(self) -> str:
        """Generate text format payload for Prometheus scraping."""
        lines: List[str] = []
        with self._lock:
            for m_name, metric in self.metrics.items():
                lines.append(f"# HELP {m_name} {metric.help_text}")
                lines.append(f"# TYPE {m_name} {metric.metric_type}")

                if metric.metric_type in ("counter", "gauge"):
                    for label_values, mv in metric.series.items():
                        labels_str = ",".join(
                            f'{k}="{v}"' for k, v in zip(metric.label_names, label_values)
                        )
                        label_formatted = f"{{{labels_str}}}" if labels_str else ""
                        lines.append(f"{m_name}{label_formatted} {mv.value}")

                elif metric.metric_type == "histogram":
                    for label_values, mv in metric.series.items():
                        base_labels = [
                            f'{k}="{v}"' for k, v in zip(metric.label_names, label_values)
                        ]
                        # Bucket lines
                        for le in mv.buckets:
                            count_le = mv.bucket_counts.get(le, 0)
                            b_labels = base_labels + [f'le="{le}"']
                            lines.append(f"{m_name}_bucket{{{','.join(b_labels)}}} {count_le}")

                        inf_labels = base_labels + ['le="+Inf"']
                        lines.append(f"{m_name}_bucket{{{','.join(inf_labels)}}} {mv.bucket_counts[float('inf')]}")
                        
                        base_str = f"{{{','.join(base_labels)}}}" if base_labels else ""
                        lines.append(f"{m_name}_sum{base_str} {mv.sum}")
                        lines.append(f"{m_name}_count{base_str} {mv.count}")

                lines.append("")

        return "\n".join(lines)


metrics = MetricsCollector()
