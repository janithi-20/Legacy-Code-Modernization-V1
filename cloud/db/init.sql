CREATE TABLE IF NOT EXISTS trades(
    report_id TEXT PRIMARY KEY,
    symbol TEXT,
    quantity INTEGER,
    price TEXT,
    notional TEXT,
    fee TEXT,
    seq BIGINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS change_log(
    seq BIGSERIAL PRIMARY KEY,
    payload TEXT
);

CREATE TABLE IF NOT EXISTS cdc_offset(
    id INTEGER PRIMARY KEY,
    value BIGINT
);
