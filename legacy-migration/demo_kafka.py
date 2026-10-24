import time
from app.legacy.service import Legacy
from app.cloud.service import Cloud
from app.cdc.kafka_consumer import CdcConsumer
from app.validation.reconciliation import reconcile

legacy, cloud = Legacy(), Cloud()
group = f"cloud-applier-{int(time.time())}"
CLEAN = dict(missing=[], extra=[], different=[])


def send(first, count):
    for i in range(first, first + count):
        legacy.submit(f"K-{i:04}", "ABC", 100 + i, "25.50")


print("1. Start the Kafka consumer at the end of the topic")
cdc = CdcConsumer(group, from_end=True)
first_offset = cdc.start_offset

print("2. Legacy accepts 20 trades; Debezium streams them through Kafka")
send(1, 20)
n = cdc.drain(cloud)
r = reconcile(legacy, cloud)
print("   applied:", n, "| reconcile:", r)
assert n == 20 and r == CLEAN

print("3. Consumer stopped; legacy accepts 10 more trades")
cdc.close()
send(21, 10)
missing = len(reconcile(legacy, cloud)["missing"])
print("   cloud is missing", missing, "trades")
assert missing == 10

print("4. Consumer restarts and resumes from its committed offset")
cdc = CdcConsumer(group)
n = cdc.drain(cloud)
r = reconcile(legacy, cloud)
print("   applied:", n, "| reconcile:", r)
assert n == 10 and r == CLEAN
cdc.close()

print("5. Replay every event again (duplicate delivery)")
replay = CdcConsumer(group + "-replay", start=first_offset)
n = replay.drain(cloud)
r = reconcile(legacy, cloud)
print("   changed:", n, "| reconcile:", r, "| trades:", len(cloud.all()))
assert n == 0 and r == CLEAN and len(cloud.all()) == 30
replay.close()

print("KAFKA CDC CHECKS PASSED")