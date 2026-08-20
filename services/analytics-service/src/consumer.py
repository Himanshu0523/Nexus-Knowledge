import logging
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from shared.kafka.consumer import KafkaEventConsumer
from shared.events.chat import TOPIC_RESPONSE_COMPLETED, TOPIC_TOOL_EXECUTED

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("analytics-consumer")

# In-memory counters (replace with time-series DB in production)
stats = defaultdict(lambda: {"count": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_latency_ms": 0.0})


def handle_response_completed(event: dict):
    data      = event.get("data", {})
    model     = data.get("model", "unknown")
    tenant    = event.get("tenant_id", "default")
    key       = f"{tenant}:{model}"

    stats[key]["count"]                += 1
    stats[key]["total_input_tokens"]   += data.get("input_tokens", 0)
    stats[key]["total_output_tokens"]  += data.get("output_tokens", 0)
    stats[key]["total_latency_ms"]     += data.get("latency_ms", 0.0)

    logger.info(
        f"[ANALYTICS] tenant={tenant} model={model} "
        f"total_responses={stats[key]['count']} "
        f"total_tokens={stats[key]['total_output_tokens']}"
    )


def handle_tool_executed(event: dict):
    data    = event.get("data", {})
    tool    = data.get("tool_name", "unknown")
    success = data.get("success", True)
    logger.info(f"[ANALYTICS] tool={tool} success={success}")


def main():
    consumer = KafkaEventConsumer(
        topics=[TOPIC_RESPONSE_COMPLETED, TOPIC_TOOL_EXECUTED],
        group_id="analytics-group",
    )
    consumer.register(TOPIC_RESPONSE_COMPLETED, handle_response_completed)
    consumer.register(TOPIC_TOOL_EXECUTED,       handle_tool_executed)

    logger.info("Analytics Service consumer starting...")
    consumer.start()


if __name__ == "__main__":
    main()
