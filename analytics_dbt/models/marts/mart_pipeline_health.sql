with last_seen as (
  select
    symbol_key,
    symbol,
    max(candle_time) as last_candle_time
  from {{ ref('fct_candles_1m') }}
  group by 1,2
)
select
  symbol_key,
  symbol,
  last_candle_time,
  extract(epoch from (now() - last_candle_time))::bigint as lag_seconds,
  round(extract(epoch from (now() - last_candle_time)) / 60.0, 2) as lag_minutes,
  (now() - last_candle_time) > interval '2 minutes' as is_stale
from last_seen
order by lag_seconds desc
