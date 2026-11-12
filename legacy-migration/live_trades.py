import sys
import time

from app.legacy.service import Legacy

count = int(sys.argv[1]) if len(sys.argv) > 1 else 20
legacy = Legacy()
for i in range(1, count + 1):
    row = legacy.submit(f"LIVE-{i:04}", "ABC", 100 + i, "25.50")
    print(f"trade {row['report_id']}: value {row['notional']}, fee {row['fee']}")
    time.sleep(1)