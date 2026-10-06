from contextlib import contextmanager
import psycopg2
from app.config import CLOUD_DB_URL


@contextmanager
def get_conn():
    """One connection per request; commit on success, roll back on error."""
    conn = psycopg2.connect(CLOUD_DB_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()