import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException
from app.db import get_conn
from app.models import TradeIn

router = APIRouter()
COLS = "trade_id, symbol, side, quantity, price, trade_ts, seq_no, source"


def to_dict(r):
    return {"trade_id": str(r[0]), "symbol": r[1], "side": r[2].strip(),
            "quantity": r[3], "price": float(r[4]), "trade_ts": r[5].isoformat(),
            "seq_no": r[6], "source": r[7]}


@router.post("/trades", status_code=201)
def create_trade(t: TradeIn):
    trade_id = str(uuid.uuid4())
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT nextval('cloud_trade_seq')")
        seq = cur.fetchone()[0]
        cur.execute(
            f"INSERT INTO silver_trades ({COLS}) "
            f"VALUES (%s,%s,%s,%s,%s,now(),%s,'cloud') RETURNING {COLS}",
            (trade_id, t.symbol, t.side, t.quantity, t.price, seq))
        row = cur.fetchone()
    return to_dict(row)


@router.get("/trades")
def list_trades(symbol: Optional[str] = None, limit: int = 50):
    limit = min(max(limit, 1), 500)
    sql, params = f"SELECT {COLS} FROM silver_trades", []
    if symbol:
        sql += " WHERE symbol = %s"
        params.append(symbol)
    sql += " ORDER BY trade_ts DESC, seq_no DESC LIMIT %s"
    params.append(limit)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"count": len(rows), "trades": [to_dict(r) for r in rows]}


@router.get("/trades/{trade_id}")
def get_trade(trade_id: str):
    try:
        uuid.UUID(trade_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="trade_id must be a UUID")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {COLS} FROM silver_trades WHERE trade_id = %s", (trade_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="trade not found")
    return to_dict(row)