CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS market_candles_1m (
  time        TIMESTAMPTZ NOT NULL,
  symbol      TEXT        NOT NULL,
  open        DOUBLE PRECISION,
  high        DOUBLE PRECISION,
  low         DOUBLE PRECISION,
  close       DOUBLE PRECISION,
  volume      DOUBLE PRECISION,
  PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('market_candles_1m', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_market_candles_1m_symbol_time
ON market_candles_1m (symbol, time DESC);
