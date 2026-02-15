with r as (
  select
    candle_time,
    symbol_key,
    symbol,
    return_pct
  from {{ ref('fct_returns_5m') }}
)
select
  *,
  stddev_samp(return_pct) over (
    partition by symbol_key
    order by candle_time
    rows between 11 preceding and current row
  ) as vol_1h
from r
