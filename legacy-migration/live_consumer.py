import time

from app.cdc.kafka_consumer import CdcConsumer
from app.cloud.service import Cloud

cloud = Cloud()
cdc = CdcConsumer(f"live-{int(time.time())}", from_end=True)
print("Live consumer running. Press Ctrl+C to stop.")
try:
    while True:
        applied = cdc.drain(cloud, idle=1.0)
        if applied:
            print(f"applied {applied} change(s) to the cloud")
except KeyboardInterrupt:
    pass
finally:
    cdc.close()
    print("Stopped.")