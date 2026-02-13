BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "ticks.raw.crypto.avro.v1"

SCHEMA_REGISTRY_URL = "http://localhost:8081"
SCHEMA_SUBJECT = f"{TOPIC}-value"
KRAKEN_WS_URL = "wss://ws.kraken.com/v2"

# Start with a small watchlist
SYMBOLS = ["BTC/USD", "ETH/USD", "SOL/USD"]

PING_EVERY_SECONDS = 30
