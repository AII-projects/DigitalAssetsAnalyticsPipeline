with base as (
  select
    time_bucket('5 minutes', candle_time) as bucket_time,
    symbol,
    symbol_key,
    candle_time,
    open, high, low, close, volume
  from {{ ref('stg_market_candles_1m') }}
),

agg as (
  select
    bucket_time,
    symbol,
    symbol_key,
    min(candle_time) as first_time,
    max(candle_time) as last_time,
    max(high) as high,
    min(low) as low,
    sum(volume) as volume
  from base
  group by 1,2,3
),

open_close as (
  select
    a.bucket_time as candle_time,
    a.symbol,
    a.symbol_key,
    b1.open as open,
    a.high,
    a.low,
    b2.close as close,
    a.volume
  from agg a
  join base b1
    on b1.bucket_time = a.bucket_time
   and b1.symbol_key  = a.symbol_key
   and b1.candle_time = a.first_time
  join base b2
    on b2.bucket_time = a.bucket_time
   and b2.symbol_key  = a.symbol_key
   and b2.candle_time = a.last_time
)

select
  {{ dbt_utils.generate_surrogate_key(['symbol_key', 'candle_time']) }} as candle_id,
  *
from open_close
