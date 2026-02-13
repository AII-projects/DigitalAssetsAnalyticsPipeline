import asyncio
import io
import json
import struct
import time
from typing import Any, Dict, Tuple

import requests
import websockets
from fastavro import parse_schema, schemaless_writer
from kafka import KafkaProducer

import config


def normalize_symbol_key(symbol: str) -> str:
    return symbol.replace("/", "-")


def fetch_latest_schema() -> Tuple[int, dict]:
    """
    Fetch latest schema id + schema JSON from Schema Registry (Karapace is SR-compatible).
    """
    url = f"{config.SCHEMA_REGISTRY_URL}/subjects/{config.SCHEMA_SUBJECT}/versions/latest"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    schema_id = int(data["id"])
    schema_obj = json.loads(data["schema"])
    return schema_id, schema_obj


def encode_confluent_avro(schema_id: int, parsed_schema: dict, record: dict) -> bytes:
    """
    Confluent Schema Registry wire format:
      [0]     magic byte 0x00
      [1..4]  schema id (big endian int32)
      [5..]   avro binary payload
    """
    buf = io.BytesIO()
    schemaless_writer(buf, parsed_schema, record)
    avro_payload = buf.getvalue()
    return b"\x00" + struct.pack(">I", schema_id) + avro_payload


def make_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=config.BOOTSTRAP_SERVERS,
        key_serializer=lambda s: s.encode("utf-8"),
        value_serializer=lambda b: b,  # already bytes
        acks="all",
        linger_ms=10,
    )


async def kraken_stream_loop() -> None:
    producer = make_producer()

    # Load schema ONCE at startup (stable for learning project).
    schema_id, schema_obj = fetch_latest_schema()
    parsed_schema = parse_schema(schema_obj)
    print(f"[OK] Loaded schema: subject={config.SCHEMA_SUBJECT} schema_id={schema_id}")

    subscribe_msg = {
        "method": "subscribe",
        "params": {"channel": "trade", "symbol": config.SYMBOLS, "snapshot": True},
        "req_id": 1,
    }
    ping_msg = {"method": "ping", "req_id": 99}

    backoff = 1
    while True:
        try:
            async with websockets.connect(config.KRAKEN_WS_URL) as ws:
                print("[OK] Connected to Kraken WS v2")
                await ws.send(json.dumps(subscribe_msg))
                print("[OK] Sent subscribe")

                last_ping = time.time()

                async for raw in ws:
                    now = time.time()
                    if now - last_ping >= config.PING_EVERY_SECONDS:
                        await ws.send(json.dumps(ping_msg))
                        last_ping = now

                    msg: Dict[str, Any] = json.loads(raw)

                    if msg.get("channel") != "trade":
                        continue

                    msg_type = msg.get("type")
                    if msg_type not in ("snapshot", "update"):
                        continue

                    for t in msg.get("data", []):
                        symbol = t.get("symbol")
                        if not symbol:
                            continue

                        price = t.get("price")
                        qty = t.get("qty")
                        ts = t.get("timestamp")
                        side = t.get("side")

                        # Avro schema likely requires these to be non-null -> skip incomplete records
                        if price is None or qty is None or ts is None:
                            continue

                        trade_id = t.get("trade_id") or f"{ts}:{price}:{qty}"

                        record = {
                            "event_id": f"kraken:{symbol}:{trade_id}",
                            "ts": ts,  # keep as RFC3339 string
                            "symbol": symbol,
                            "price": float(price),
                            "volume": float(qty),
                            "side": side if side is not None else None,
                            "venue": "kraken",
                            "asset_class": "crypto",
                            "schema_version": 1,
                            "source": "kraken_ws_v2_trade",
                        }

                        payload = encode_confluent_avro(schema_id, parsed_schema, record)

                        # HARD PROOF: must start with magic byte 0x00
                        if payload[0] != 0x00:
                            raise RuntimeError("Not Confluent wire format (magic byte != 0x00)")

                        # Optional: show prefix once in a while
                        # print("payload_prefix_hex=", payload[:8].hex())

                        producer.send(
                            config.TOPIC,
                            key=normalize_symbol_key(symbol),
                            value=payload
                        ).get(timeout=10)

        except Exception as e:
            print(f"[ERR] Kraken WS loop failed: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
        else:
            backoff = 1


def main() -> None:
    asyncio.run(kraken_stream_loop())


if __name__ == "__main__":
    main()
