select distinct
  symbol_key,
  symbol,
  'crypto'::text as asset_class
from {{ ref('stg_market_candles_1m') }}
