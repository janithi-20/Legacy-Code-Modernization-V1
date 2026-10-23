import psycopg
from psycopg.rows import dict_row
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN

Q = Decimal("0.01")
COLS = "report_id, symbol, quantity, price, notional, fee"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades(
    report_id TEXT PRIMARY KEY, symbol TEXT, quantity INTEGER,
    price TEXT, notional TEXT, fee TEXT, seq BIGINT DEFAULT 0);
CREATE TABLE IF NOT EXISTS change_log(seq BIGSERIAL PRIMARY KEY, payload TEXT);
CREATE TABLE IF NOT EXISTS cdc_offset(id INTEGER PRIMARY KEY, value BIGINT);
"""

def calc(quantity, price, bug=False):
    notional = (Decimal(str(quantity)) * Decimal(str(price))).quantize(Q)
    mode = ROUND_DOWN if bug else ROUND_HALF_UP
    fee = (notional * Decimal("0.0005")).quantize(Q, rounding=mode)
    return str(notional), str(fee)

class TradeStore:
    def __init__(self, dsn, bug=False):
        self.bug, self.healthy = bug, True
        self.db = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)
        self.db.execute(SCHEMA)
        # demo/test setup: start every run from empty tables
        self.db.execute("TRUNCATE trades, change_log, cdc_offset RESTART IDENTITY")

    def compute(self, symbol, quantity, price):
        return calc(quantity, price, self.bug)

    def _row(self, report_id, symbol, quantity, price):
        n, f = self.compute(symbol, quantity, price)
        return dict(report_id=report_id, symbol=symbol, quantity=int(quantity),
                    price=str(price), notional=n, fee=f)

    def _put(self, row, seq=0):
        self.db.execute(
            """INSERT INTO trades(report_id,symbol,quantity,price,notional,fee,seq)
               VALUES(%(report_id)s,%(symbol)s,%(quantity)s,%(price)s,%(notional)s,%(fee)s,%(seq)s)
               ON CONFLICT (report_id) DO UPDATE SET
                 symbol=EXCLUDED.symbol, quantity=EXCLUDED.quantity, price=EXCLUDED.price,
                 notional=EXCLUDED.notional, fee=EXCLUDED.fee, seq=EXCLUDED.seq""",
            {**row, "seq": seq})

    def all(self):
        rows = self.db.execute(f"SELECT {COLS} FROM trades").fetchall()
        return {r["report_id"]: r for r in rows}