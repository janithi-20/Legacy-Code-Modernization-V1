import os
import time

import psycopg

from app.common import SCHEMA


def wait_for_database(dsn, label, attempts=30, delay=2):
    last_error = None
    for _ in range(attempts):
        try:
            with psycopg.connect(dsn, autocommit=True) as connection:
                connection.execute(SCHEMA)
            return
        except psycopg.Error as error:
            last_error = error
            time.sleep(delay)
    raise RuntimeError(f"{label} database did not become ready: {last_error}") from last_error


def ensure_demo_data(dsn):
    with psycopg.connect(dsn, autocommit=True) as connection:
        existing = connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        if existing:
            return
        connection.execute(
            """INSERT INTO trades
               (report_id, symbol, quantity, price, notional, fee)
               VALUES
               ('TRD-0001', 'ABC', 100, '25.50', '2550.00', '1.28'),
               ('TRD-0002', 'XYZ', 50, '10.00', '500.00', '0.25')"""
        )


if __name__ == "__main__":
    legacy_dsn = os.environ["LEGACY_DSN"]
    cloud_dsn = os.environ["CLOUD_DSN"]
    wait_for_database(legacy_dsn, "Legacy")
    wait_for_database(cloud_dsn, "Cloud")
    ensure_demo_data(legacy_dsn)
    ensure_demo_data(cloud_dsn)
