import json
import os
import time
from confluent_kafka import Consumer, TopicPartition, OFFSET_BEGINNING

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.getenv("DEBEZIUM_TOPIC", "legacy.public.trades")
COLS = ["report_id", "symbol", "quantity", "price", "notional", "fee"]


class CdcConsumer:
    def __init__(self, group, from_end=False, start=None):
        self.c = Consumer({"bootstrap.servers": BOOTSTRAP_SERVERS,
                           "group.id": group,
                           "enable.auto.commit": False})
        metadata = self.c.list_topics(topic=TOPIC, timeout=10)
        topic_metadata = metadata.topics.get(TOPIC)
        if topic_metadata is None or topic_metadata.error is not None:
            self.c.close()
            raise RuntimeError(
                f"Kafka topic {TOPIC!r} is unavailable at "
                f"{BOOTSTRAP_SERVERS}. Register or start the Debezium connector "
                "before starting the CDC consumer."
            )
        if 0 not in topic_metadata.partitions:
            self.c.close()
            raise RuntimeError(
                f"Kafka topic {TOPIC!r} has no partition 0 at "
                f"{BOOTSTRAP_SERVERS}."
            )
        tp = TopicPartition(TOPIC, 0)
        committed = self.c.committed([tp], timeout=10)[0].offset
        if start is not None:
            pos = start
        elif committed >= 0:
            pos = committed                    # resume where we stopped
        elif from_end:
            pos = self.c.get_watermark_offsets(tp, timeout=10)[1]
        else:
            pos = OFFSET_BEGINNING
        self.start_offset = pos
        self.c.assign([TopicPartition(TOPIC, 0, pos)])

    def drain(self, cloud, idle=5.0, max_seconds=90):
        """Apply events until the topic is quiet. Returns how many changed the cloud."""
        changed, t0, last = 0, time.time(), time.time()
        while time.time() - last < idle and time.time() - t0 < max_seconds:
            m = self.c.poll(0.5)
            if m is None or m.error():
                continue
            last = time.time()
            if m.value():
                ev = json.loads(m.value())
                after = ev.get("after")
                before = ev.get("before")
                op = ev.get("op")
                lsn = ev["source"]["lsn"]

                if op in ("c", "u", "r") and after:
                    report_id = after.get("report_id", after.get("trade_id"))
                    if report_id is None:
                        self.c.commit(message=m, asynchronous=False)
                        continue
                    row = {k: after.get(k, after.get("trade_id") if k == "report_id" else None) for k in COLS}
                    if cloud.apply(lsn, row):
                        changed += 1
                elif op == "d" and before:
                    report_id = before.get("report_id", before.get("trade_id"))
                    if report_id is not None and cloud.delete(lsn, report_id):
                        changed += 1
            self.c.commit(message=m, asynchronous=False)
        return changed

    def close(self):
        self.c.close()