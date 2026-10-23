import json
from app.common import TradeStore
from app.config import LEGACY_DSN

class Legacy(TradeStore):
    def __init__(self, bug=False):
        super().__init__(LEGACY_DSN, bug)

    def submit(self, report_id, symbol, quantity, price):
        row = self._row(report_id, symbol, quantity, price)
        self.insert_row(row)
        return row

    def insert_row(self, row):
        with self.db.transaction():       # trade + change event commit together
            self._put(row)
            self.db.execute("INSERT INTO change_log(payload) VALUES(%s)", (json.dumps(row),))

    def changes_after(self, seq):
        rows = self.db.execute(
            "SELECT seq, payload FROM change_log WHERE seq>%s ORDER BY seq", (seq,)).fetchall()
        return [(r["seq"], json.loads(r["payload"])) for r in rows]

    def last_seq(self):
        return self.db.execute("SELECT COALESCE(MAX(seq),0) AS m FROM change_log").fetchone()["m"]