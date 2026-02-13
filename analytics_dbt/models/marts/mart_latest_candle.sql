with ranked as (
  select
    *,
    row_number() over (partition by symbol_key order by candle_time desc) as rn
  from {{ ref('fct_candles_1m') }}
)
select
  candle_time,
  symbol_key,
  symbol,
  open,
  high,
  low,
  close,
  volume
from ranked
where rn = 1
