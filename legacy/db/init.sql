CREATE SEQUENCE trade_seq START 100001;

CREATE TABLE trades (
  trade_id UUID PRIMARY KEY,
  symbol   VARCHAR(12)   NOT NULL,
  side     CHAR(4)       NOT NULL,
  quantity INTEGER       NOT NULL,
  price    NUMERIC(14,4) NOT NULL,
  trade_ts TIMESTAMPTZ   NOT NULL,
  seq_no   BIGINT        NOT NULL
);

INSERT INTO trades (trade_id, symbol, side, quantity, price, trade_ts, seq_no) VALUES
('7b1c0c3e-5d2a-4f55-9a43-1d6c2f1e9a10','ABCD','BUY', 500,132.4500,'2026-10-06 09:30:00+00',nextval('trade_seq')),
('2e9f44aa-0c1b-4d3e-8a77-5b6c7d8e9f01','WXYZ','SELL',120, 58.2000,'2026-10-06 09:30:01+00',nextval('trade_seq')),
('91d7b0c2-3a4b-4c5d-9e6f-7a8b9c0d1e2f','ABCD','SELL',300,132.5000,'2026-10-06 09:30:02+00',nextval('trade_seq')),
('c3a1f0d9-1b2c-4e3d-8f4a-5b6c7d8e9a0b','LMNO','BUY', 250,240.1000,'2026-10-06 09:30:03+00',nextval('trade_seq')),
('d4b2e1c8-2c3d-4f4e-9a5b-6c7d8e9f0a1b','WXYZ','BUY', 800, 58.1500,'2026-10-06 09:30:04+00',nextval('trade_seq'));