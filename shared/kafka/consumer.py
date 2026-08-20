import json
import logging
import os
import sys
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

try:
    from kafka import KafkaConsumer as _KafkaConsumer
    _KAFKA_AVAILABLE = True
except ImportError:
    _KAFKA_AVAILABLE = False


class KafkaEventConsumer:
    """Generic Kafka consumer with handler dispatch."""

    def __init__(self, topics: List[str], group_id: str):
        self.topics = topics
        self.group_id = group_id
        self._handlers: Dict[str, Callable] = {}
        self._consumer = None

    def register(self, event_type: str, handler: Callable):
        """Register a handler for a specific event_type."""
        self._handlers[event_type] = handler

    def _connect(self):
        if not _KAFKA_AVAILABLE:
            logger.warning("kafka-python not installed. Consumer is a no-op.")
            return False
        try:
            self._consumer = _KafkaConsumer(
                *self.topics,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=self.group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                consumer_timeout_ms=1000,
            )
            logger.info(f"Consumer '{self.group_id}' connected. Topics: {self.topics}")
            return True
        except Exception as e:
            logger.error(f"Consumer connection failed: {e}")
            return False

    def start(self):
        """Blocking poll loop — run in a thread."""
        if not self._connect():
            logger.warning(f"[{self.group_id}] Running without Kafka (dev mode).")
            return

        logger.info(f"[{self.group_id}] Listening on {self.topics}...")
        try:
            for message in self._consumer:
                event = message.value
                event_type = event.get("event_type", "")
                handler = self._handlers.get(event_type)

                if handler:
                    try:
                        handler(event)
                    except Exception as e:
                        logger.error(f"Handler error for {event_type}: {e}")
                else:
                    logger.debug(f"No handler for event_type={event_type}")
        except Exception as e:
            logger.error(f"Consumer loop error: {e}")
        finally:
            if self._consumer:
                self._consumer.close()
