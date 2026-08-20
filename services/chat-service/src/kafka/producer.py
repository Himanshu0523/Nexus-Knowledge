import json
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# Try to import kafka-python; fall back to a no-op producer when unavailable
try:
    from kafka import KafkaProducer as _KafkaProducer
    _KAFKA_AVAILABLE = True
except ImportError:
    _KAFKA_AVAILABLE = False
    logger.warning("kafka-python not installed. Events will be logged only.")


class KafkaEventProducer:
    """Thin Kafka producer wrapper with graceful fallback."""

    def __init__(self):
        self._producer = None
        if _KAFKA_AVAILABLE:
            try:
                self._producer = _KafkaProducer(
                    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                    acks="all",
                    retries=3,
                    max_block_ms=5000,
                )
                logger.info(f"Kafka producer connected to {KAFKA_BOOTSTRAP_SERVERS}")
            except Exception as e:
                logger.warning(f"Kafka unavailable ({e}). Events will be logged only.")
                self._producer = None

    def publish(self, topic: str, event_dict: dict, key: Optional[str] = None) -> bool:
        """
        Publish an event to a Kafka topic.
        Returns True on success, False on failure (never raises).
        """
        if self._producer:
            try:
                future = self._producer.send(topic, value=event_dict, key=key)
                self._producer.flush(timeout=5)
                logger.info(f"[Kafka] Published → {topic} | event_id={event_dict.get('event_id')}")
                return True
            except Exception as e:
                logger.error(f"[Kafka] Failed to publish to {topic}: {e}")
                return False
        else:
            # Graceful no-op: log the event so nothing is lost in dev mode
            logger.info(
                f"[Kafka-NOOP] topic={topic} event_id={event_dict.get('event_id')} "
                f"event_type={event_dict.get('event_type')}"
            )
            return False

    def close(self):
        if self._producer:
            self._producer.close()


# Singleton instance shared across the chat-service process
kafka_producer = KafkaEventProducer()
