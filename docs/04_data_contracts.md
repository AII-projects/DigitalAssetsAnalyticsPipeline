## Topic: ticks.raw.crypto.v1 (JSON)

Source: Kraken WebSocket v2 trade feed

Fields (v1):
- event_id (string)
- ts (string, UTC timestamp)
- symbol (string, e.g., "BTC/USD")
- price (number)
- volume (number)  # trade qty
- side (string, optional)
- venue (string = "kraken")
- asset_class (string = "crypto")
- schema_version (int)
- source (string)
