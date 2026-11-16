import os
import time

import psycopg
from psycopg.rows import dict_row

from app.common import SCHEMA


DEFAULT_TRADES = (
    ("TRD-0015", "DOCK.N0000", 25000, "272.00"),
    ("TRD-0014", "LOLC.N0000", 10000, "575.25"),
    ("TRD-0013", "CTC.N0000", 5000, "1700.00"),
    ("TRD-0012", "LLUB.N0000", 15000, "198.25"),
    ("TRD-0011", "HAYC.N0000", 20000, "175.75"),
    ("TRD-0010", "HAYL.N0000", 104900, "195.00"),
    ("TRD-0009", "SUN.N0000", 362400, "34.26"),
    ("TRD-0008", "SAMP.N0000", 122047, "148.98"),
    ("TRD-0007", "DIAL.N0000", 4424539, "30.02"),
    ("TRD-0006", "HNB.N0000", 46731, "411.11"),
    ("TRD-0005", "HPL.N0000", 10903500, "27.30"),
    ("TRD-0004", "COMB.N0000", 300000, "210.50"),
    ("TRD-0003", "COMB.X0000", 110000, "193.00"),
    ("TRD-0002", "VONE.N0000", 200000, "105.00"),
    ("TRD-0001", "JKH.N0000", 900000, "22.80"),
)
DEFAULT_TRADE_IDS = {trade[0] for trade in DEFAULT_TRADES}


def initialize_database(dsn, reconcile_defaults=True):
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(SCHEMA)
    ensure_demo_data(dsn, reconcile_defaults=reconcile_defaults)


def wait_for_database(dsn, label, attempts=30, delay=2):
    last_error = None
    for _ in range(attempts):
        try:
            initialize_database(dsn)
            return
        except psycopg.Error as error:
            last_error = error
            time.sleep(delay)
    raise RuntimeError(f"{label} database did not become ready: {last_error}") from last_error


def ensure_demo_data(dsn, reconcile_defaults=True):
    with psycopg.connect(dsn, autocommit=True) as connection:
        existing_ids = {
            row[0] for row in connection.execute("SELECT report_id FROM trades")
        }
        if existing_ids and existing_ids != DEFAULT_TRADE_IDS and not reconcile_defaults:
            return
        if existing_ids != DEFAULT_TRADE_IDS:
            connection.execute("DELETE FROM trades")
        with connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO trades (report_id, symbol, quantity, price)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (report_id) DO UPDATE SET
                     symbol = EXCLUDED.symbol,
                     quantity = EXCLUDED.quantity,
                     price = EXCLUDED.price""",
                DEFAULT_TRADES,
            )
        connection.execute(
            """UPDATE trades
               SET notional = ROUND(quantity * price::numeric, 2),
                   fee = ROUND(quantity * price::numeric * 0.0005, 2)
               WHERE report_id = ANY(%s)""",
            ([trade[0] for trade in DEFAULT_TRADES],),
        )


def backfill_trade_values(legacy_dsn, cloud_dsn):
    with psycopg.connect(legacy_dsn, row_factory=dict_row, autocommit=True) as legacy:
        rows = legacy.execute(
            "SELECT report_id, notional, fee FROM trades "
            "WHERE notional IS NOT NULL AND fee IS NOT NULL"
        ).fetchall()
    with psycopg.connect(cloud_dsn, autocommit=True) as cloud:
        for row in rows:
            cloud.execute(
                "UPDATE trades SET notional=%s, fee=%s "
                "WHERE report_id=%s AND (notional IS NULL OR fee IS NULL)",
                (row["notional"], row["fee"], row["report_id"]),
            )


if __name__ == "__main__":
    legacy_dsn = os.environ["LEGACY_DSN"]
    cloud_dsn = os.environ["CLOUD_DSN"]
    wait_for_database(legacy_dsn, "Legacy")
    wait_for_database(cloud_dsn, "Cloud")
    backfill_trade_values(legacy_dsn, cloud_dsn)
