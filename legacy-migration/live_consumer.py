import time

from app.cdc.kafka_consumer import CdcConsumer
from app.cloud.service import Cloud

# Do not clear existing cloud database records
cloud = Cloud(reset=False)

# Use a fixed group ID to resume from the last committed offset
cdc = CdcConsumer("legacy-cloud-applier", from_end=True)

print("Live CDC consumer running.")
print("Listening to:", "legacy.public.trades")
print("Press Ctrl+C to stop.")

try:
    while True:
        applied = cdc.drain(cloud, idle=1.0)

        if applied:
            print(f"Applied {applied} change(s) to the cloud database")

except KeyboardInterrupt:
    print("Stopping consumer...")

finally:
    cdc.close()
    cloud.db.close()
    print("Live consumer stopped.")