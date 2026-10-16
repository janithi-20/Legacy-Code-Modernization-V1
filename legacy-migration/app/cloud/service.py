from app.common import TradeStore

class Cloud(TradeStore):
    def submit(self, report_id, symbol, quantity, price):
        if not self.healthy:
            raise RuntimeError("cloud unavailable")
        row = self._row(report_id, symbol, quantity, price)
        with self.db:
            self._put(row)
        return row

    def apply(self, seq, row):
        cur = self.db.execute("SELECT seq FROM trades WHERE report_id=?", (row["report_id"],)).fetchone()
        if cur and cur["seq"] >= seq:
            return False          # duplicate or out-of-order older event
        with self.db:
            self._put(row, seq)
        return True

    def offset(self):
        r = self.db.execute("SELECT value FROM cdc_offset WHERE id=1").fetchone()
        return r["value"] if r else 0

    def set_offset(self, v):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO cdc_offset VALUES(1,?)", (v,))
