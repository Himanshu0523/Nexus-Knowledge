import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from shared.kafka.consumer import KafkaEventConsumer
from shared.events.chat import TOPIC_MESSAGE_CREATED

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("moderation-consumer")

# Simple keyword blocklist (expand as needed)
_BLOCKLIST = {"hate", "violence", "spam", "abuse"}

def handle_message_created(event: dict):
    data    = event.get("data", {})
    message = data.get("user_message", "").lower()
    flagged = [w for w in _BLOCKLIST if w in message]

    if flagged:
        logger.warning(
            f"[MODERATION] FLAGGED conversation_id={data.get('conversation_id')} "
            f"tenant={event.get('tenant_id')} words={flagged}"
        )
    else:
        logger.info(f"[MODERATION] OK conversation_id={data.get('conversation_id')}")


def main():
    consumer = KafkaEventConsumer(
        topics=[TOPIC_MESSAGE_CREATED],
        group_id="moderation-group",
    )
    consumer.register(TOPIC_MESSAGE_CREATED, handle_message_created)

    logger.info("Moderation Service consumer starting...")
    consumer.start()


if __name__ == "__main__":
    main()
