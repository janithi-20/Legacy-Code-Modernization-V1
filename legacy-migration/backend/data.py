import json
import os
import urllib.error
import urllib.request

import psycopg
from psycopg.rows import dict_row

from app.config import CLOUD_DSN, LEGACY_DSN

CONNECTOR_URL = os.getenv(
    "CONNECTOR_URL",
    "http://localhost:8083/connectors/legacy-trades-connector/status",
)
COLS = "report_id, symbol, quantity, price, notional, fee"


def run_query(dsn, sql):
    with psycopg.connect(dsn, row_factory=dict_row, autocommit=True) as conn:
        return conn.execute(sql).fetchall()


class Reader:
    """Read-only view of a trades table."""

    def __init__(self, dsn):
        self.dsn = dsn

    def all(self):
        rows = run_query(self.dsn, f"SELECT {COLS} FROM trades")
        return {row["report_id"]: row for row in rows}


def connector_status():
    try:
        with urllib.request.urlopen(CONNECTOR_URL, timeout=3) as response:
            info = json.load(response)
        connector = info.get("connector", {})
        tasks = info.get("tasks", [])
        task_states = [
            task.get("state", "UNKNOWN")
            for task in tasks
            if isinstance(task, dict)
        ]
        return connector.get("state", "UNKNOWN"), task_states
    except urllib.error.HTTPError as exc:
        return ("NOT REGISTERED" if exc.code == 404 else "ERROR"), []
    except (OSError, ValueError, KeyError):
        return "UNREACHABLE", []


def slot_info():
    rows = run_query(
        LEGACY_DSN,
        "SELECT active, "
        "pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)::bigint AS lag_bytes "
        "FROM pg_replication_slots WHERE slot_name = 'legacy_slot'",
    )
    return rows[0] if rows else None
