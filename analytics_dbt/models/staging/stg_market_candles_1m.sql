with src as (
  select
    time::timestamptz as candle_time,
    symbol::text as symbol,
    open::double precision as open,
    high::double precision as high,
    low::double precision as low,
    close::double precision as close,
    volume::double precision as volume
  from {{ source('raw_timescale', 'market_candles_1m') }}
)

select
  candle_time,
  symbol,
  replace(symbol, '/', '-') as symbol_key,
  open,
  high,
  low,
  close,
  volume
from src
