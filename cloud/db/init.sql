CREATE SEQUENCE cloud_trade_seq START 500001;
 
CREATE TABLE bronze_trades_raw (
  id           BIGSERIAL PRIMARY KEY,
  kafka_offset BIGINT,
  payload      JSONB NOT NULL,
  received_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
 
CREATE TABLE silver_trades (
  trade_id UUID PRIMARY KEY,
  symbol   VARCHAR(12)   NOT NULL,
  side     CHAR(4)       NOT NULL CHECK (side IN ('BUY','SELL')),
  quantity INTEGER       NOT NULL CHECK (quantity > 0),
  price    NUMERIC(14,4) NOT NULL CHECK (price > 0),
  trade_ts TIMESTAMPTZ   NOT NULL,
  seq_no   BIGINT        NOT NULL,
  source   VARCHAR(10)   NOT NULL,
  UNIQUE (source, seq_no)
);
CREATE INDEX idx_silver_trade_ts ON silver_trades (trade_ts);   
 
CREATE TABLE dim_instrument (
  instrument_key SERIAL PRIMARY KEY,
  symbol VARCHAR(12) UNIQUE NOT NULL,
  name   TEXT,
  sector TEXT
);
CREATE TABLE dim_date (
  date_key  INT PRIMARY KEY,
  full_date DATE NOT NULL,
  year INT, month INT, day INT
);
CREATE TABLE fact_trades (
  trade_id       UUID PRIMARY KEY,
  instrument_key INT REFERENCES dim_instrument(instrument_key),
  date_key       INT REFERENCES dim_date(date_key),
  side     CHAR(4),
  quantity INTEGER,
  price    NUMERIC(14,4),
  notional NUMERIC(18,4),
  seq_no   BIGINT
);
 
CREATE TABLE sync_watermark (
  stream TEXT PRIMARY KEY,
  last_seq_no BIGINT,

  updated_at TIMESTAMPTZ
);
CREATE TABLE reconciliation_runs (
  run_id SERIAL PRIMARY KEY,
  run_at TIMESTAMPTZ DEFAULT now(),
  legacy_count BIGINT, cloud_count BIGINT,
  legacy_checksum TEXT, cloud_checksum TEXT,
  status TEXT
);
 
INSERT INTO dim_instrument (symbol, name, sector) VALUES
 ('ABCD','Alpha Bank','Financials'),
 ('WXYZ','Wave Energy','Energy'),
 ('LMNO','Lumen Tech','Technology');
