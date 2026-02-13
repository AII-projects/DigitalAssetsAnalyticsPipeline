select
  {{ dbt_utils.generate_surrogate_key(['symbol_key', 'candle_time']) }} as candle_id,
  candle_time,
  symbol_key,
  symbol,
  open,
  high,
  low,
  close,
  volume
from {{ ref('stg_market_candles_1m') }}
