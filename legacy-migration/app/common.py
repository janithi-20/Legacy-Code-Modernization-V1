import sqlite3
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN

Q = Decimal("0.01")
COLS = ["report_id", "symbol", "quantity", "price", "notional", "fee"]

SCHEMA = """
CREATE TABLE trades(report_id TEXT PRIMARY KEY, symbol TEXT, quantity INTEGER,
                    price TEXT, notional TEXT, fee TEXT, seq INTEGER DEFAULT 0);
CREATE TABLE change_log(seq INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT);
CREATE TABLE cdc_offset(id INTEGER PRIMARY KEY, value INTEGER);
"""

def calc(quantity, price, bug=False):
    notional = (Decimal(str(quantity)) * Decimal(str(price))).quantize(Q)
    mode = ROUND_DOWN if bug else ROUND_HALF_UP
    fee = (notional * Decimal("0.0005")).quantize(Q, rounding=mode)
    return str(notional), str(fee)

class TradeStore:
    def __init__(self, bug=False):
        self.bug, self.healthy = bug, True
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def compute(self, symbol, quantity, price):
        return calc(quantity, price, self.bug)

    def _row(self, report_id, symbol, quantity, price):
        n, f = self.compute(symbol, quantity, price)
        return dict(report_id=report_id, symbol=symbol, quantity=int(quantity),
                    price=str(price), notional=n, fee=f)

    def _put(self, row, seq=0):
        self.db.execute("INSERT OR REPLACE INTO trades VALUES"
                        "(:report_id,:symbol,:quantity,:price,:notional,:fee,:seq)",
                        {**row, "seq": seq})

    def all(self):
        return {r["report_id"]: {k: r[k] for k in COLS}
                for r in self.db.execute("SELECT * FROM trades")}
