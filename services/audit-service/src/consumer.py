import logging
import sys
import os

# Allow importing from shared/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from shared.kafka.consumer import KafkaEventConsumer
from shared.events.chat import (
    TOPIC_MESSAGE_CREATED,
    TOPIC_RESPONSE_COMPLETED,
    TOPIC_RESPONSE_FAILED,
)
from handlers.chat_events import (
    handle_message_created,
    handle_response_completed,
    handle_response_failed,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("audit-consumer")


def main():
    consumer = KafkaEventConsumer(
        topics=[TOPIC_MESSAGE_CREATED, TOPIC_RESPONSE_COMPLETED, TOPIC_RESPONSE_FAILED],
        group_id="audit-group",
    )
    consumer.register(TOPIC_MESSAGE_CREATED,    handle_message_created)
    consumer.register(TOPIC_RESPONSE_COMPLETED, handle_response_completed)
    consumer.register(TOPIC_RESPONSE_FAILED,    handle_response_failed)

    logger.info("Audit Service consumer starting...")
    consumer.start()


if __name__ == "__main__":
    main()
