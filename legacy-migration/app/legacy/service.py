import json
from app.common import TradeStore
class Legacy(TradeStore):
    def submit(self, report_id, symbol, quantity, price):
        row = self._row(report_id, symbol, quantity, price)
        self.insert_row(row)
        return row
    def insert_row(self, row):
        with self.db:
            self._put(row)
            self.db.execute("INSERT INTO change_log(payload) VALUES(?)", (json.dumps(row),))
    def changes_after(self, seq):
        rows = self.db.execute("SELECT seq, payload FROM change_log WHERE seq>? ORDER BY seq", (seq,)
        return [(r["seq"], json.loads(r["payload"])) for r in rows]
        def last_seq(self):
        return self.db.execute("SELECT COALESCE(MAX(seq),0) FROM change_log").fetchone()[0])