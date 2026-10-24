"""Run the CDC demo through a Kafka topic.

Requires a Kafka broker reachable at KAFKA_BOOTSTRAP_SERVERS (default:
localhost:9092). The legacy and cloud stores use the same PostgreSQL
configuration as demo.py.
"""

import json
import os
import sys
import time
from uuid import uuid4

from confluent_kafka import Consumer, KafkaError, Producer

from app.cloud.service import Cloud
from app.legacy.service import Legacy
from app.validation.reconciliation import reconcile


BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC", f"legacy-migration-{uuid4().hex}")
GROUP_ID = f"legacy-migration-demo-{uuid4().hex}"


def delivery_report(err, message):
    if err is not None:
        raise RuntimeError(f"Kafka delivery failed: {err}")


def main():
    legacy, cloud = Legacy(), Cloud()
    kafka_config = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "socket.timeout.ms": 3000,
        "message.timeout.ms": 5000,
    }
    producer = Producer(kafka_config)
    consumer = Consumer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "group.id": GROUP_ID,
            "auto.offset.reset": "earliest",
            "socket.timeout.ms": 3000,
        }
    )

    try:
        try:
            producer.list_topics(timeout=5)
        except Exception as exc:
            raise RuntimeError(
                f"Cannot connect to Kafka at {BOOTSTRAP_SERVERS}: {exc}"
            ) from exc

        print(f"1. Kafka CDC topic: {TOPIC}")
        print("2. Legacy accepts trades")
        for number in range(1, 6):
            row = legacy.submit(f"KAFKA-{number:04}", "ABC", 100 + number, "25.50")
            producer.produce(
                TOPIC,
                key=row["report_id"],
                value=json.dumps(row),
                callback=delivery_report,
            )
        producer.flush()

        print("3. Kafka consumer copies trades to cloud")
        consumer.subscribe([TOPIC])
        received = 0
        deadline = time.monotonic() + 15
        while received < 5 and time.monotonic() < deadline:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise RuntimeError(f"Kafka consumer failed: {message.error()}")
            row = json.loads(message.value())
            cloud.apply(received + 1, row)
            received += 1

        if received != 5:
            raise TimeoutError(
                f"Timed out waiting for Kafka CDC events: received {received} of 5"
            )

        result = reconcile(legacy, cloud)
        print(f"   received={received} reconcile={result}")
        if any(result.values()):
            raise RuntimeError(f"Kafka CDC reconciliation failed: {result}")
        print("ALL KAFKA CHECKS PASSED")
    finally:
        consumer.close()
        legacy.db.close()
        cloud.db.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"Kafka demo failed: {exc}\n"
            "Start a Kafka broker or set KAFKA_BOOTSTRAP_SERVERS to its address.",
            file=sys.stderr,
        )
        raise SystemExit(1)
