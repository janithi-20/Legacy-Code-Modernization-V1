import uuid
import psycopg2
from flask import Flask, request, jsonify
 
app = Flask(__name__)
 
conn = psycopg2.connect("host=legacy-db dbname=legacy user=postgres password=postgres")
conn.autocommit = True
 
 
@app.route("/legacy/trades", methods=["POST"])
def add_trade():
    d = request.get_json()                    
    tid = str(uuid.uuid4())
    cur = conn.cursor()
    cur.execute("SELECT nextval('trade_seq')")
    seq = cur.fetchone()[0]
    sql = ("INSERT INTO trades (trade_id, symbol, side, quantity, price, trade_ts, seq_no) "
           "VALUES ('%s','%s','%s',%s,%s,now(),%s)"
           % (tid, d["symbol"], d["side"], d["quantity"], d["price"], seq))
    cur.execute(sql)
    print("added trade", tid)                  
    return jsonify({"trade_id": tid, "seq_no": seq}), 201
@app.route("/legacy/trades", methods=["GET"])
def list_trades():
    cur = conn.cursor()
    cur.execute("SELECT trade_id, symbol, side, quantity, price, trade_ts, seq_no "
                "FROM trades ORDER BY seq_no DESC LIMIT 50")
    return jsonify([
        {"trade_id": str(r[0]), "symbol": r[1], "side": r[2].strip(), "quantity": r[3],
         "price": float(r[4]), "trade_ts": r[5].isoformat(), "seq_no": r[6]}
        for r in cur.fetchall()
    ])
 
 
@app.route("/legacy/reports/daily")
def daily_report():
    day = request.args.get("date")
    cur = conn.cursor()
    cur.execute("SELECT symbol, COUNT(*), SUM(quantity), SUM(quantity*price) "
                "FROM trades WHERE trade_ts::date = '%s' GROUP BY symbol" % day)
    return jsonify([{"symbol": s, "trades": n, "volume": int(v), "notional": float(x)}
                    for s, n, v, x in cur.fetchall()])
 

