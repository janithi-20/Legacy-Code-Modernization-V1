from app.common import TradeStore
from app.config import CLOUD_DSN

class Cloud(TradeStore):
    def __init__(self, bug=False):
        super().__init__(CLOUD_DSN, bug)

    def submit(self, report_id, symbol, quantity, price):
        if not self.healthy:
            raise RuntimeError("cloud unavailable")
        row = self._row(report_id, symbol, quantity, price)
        self._put(row)
        return row

    def apply(self, seq, row):
        cur = self.db.execute("SELECT seq FROM trades WHERE report_id=%s",
                              (row["report_id"],)).fetchone()
        if cur and cur["seq"] >= seq:
            return False          # duplicate or out-of-order older event
        self._put(row, seq)
        return True

    def offset(self):
        r = self.db.execute("SELECT value FROM cdc_offset WHERE id=1").fetchone()
        return r["value"] if r else 0

    def set_offset(self, v):
        self.db.execute("""INSERT INTO cdc_offset(id,value) VALUES(1,%s)
                           ON CONFLICT (id) DO UPDATE SET value=EXCLUDED.value""", (v,))