import struct
from kafka import KafkaConsumer

TOPIC = "ticks.raw.crypto.avro.v1"
BOOTSTRAP = "localhost:9092"  # host -> docker published port

c = KafkaConsumer(
    TOPIC,
    bootstrap_servers=BOOTSTRAP,
    auto_offset_reset="latest",
    enable_auto_commit=False,
    consumer_timeout_ms=8000,
)

msg = next(iter(c), None)
if msg is None:
    print("[NONE] No messages read (producer may be stopped or topic idle).")
    raise SystemExit(0)

v = msg.value
print("len(value) =", len(v))
print("first 10 bytes hex =", v[:10].hex())

magic = v[0]
print("magic byte =", hex(magic))

if magic == 0x00 and len(v) >= 5:
    schema_id = struct.unpack(">I", v[1:5])[0]
    print("schema_id =", schema_id)
    print("payload starts with (hex) =", v[5:15].hex())
else:
    # If this prints '{' (0x7b), your topic is JSON, not Confluent-Avro
    print("first byte as char =", chr(magic) if 32 <= magic <= 126 else "<non-printable>")
