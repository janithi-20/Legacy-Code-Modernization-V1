import zlib

class Router:
    def __init__(self, legacy, cloud):
        self.legacy, self.cloud, self.percent = legacy, cloud, 0

    def route(self, request_id):
        return "cloud" if zlib.crc32(request_id.encode()) % 100 < self.percent else "legacy"

    def submit(self, request_id, symbol, quantity, price):
        if self.route(request_id) == "cloud":
            try:
                return "cloud", self.cloud.submit(request_id, symbol, quantity, price)
            except Exception:
                self.percent = 0   # safe fallback
        return "legacy", self.legacy.submit(request_id, symbol, quantity, price)
