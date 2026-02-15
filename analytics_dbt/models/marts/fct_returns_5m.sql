with base as (
  select
    candle_time,
    symbol_key,
    symbol,
    open, high, low, close, volume,
    lag(close) over (partition by symbol_key order by candle_time) as prev_close
  from {{ ref('fct_candles_5m') }}
)
select
  *,
  case when prev_close is null then null else (close - prev_close) / prev_close end as return_pct
from base
