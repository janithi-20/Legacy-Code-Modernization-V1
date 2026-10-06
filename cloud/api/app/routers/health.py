from fastapi import APIRouter
from app.db import get_conn

router = APIRouter()


@router.get("/health")
def health():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
    return {"status": "ok", "service": "cloud-api"}