import json
from pathlib import Path
import requests

REGISTRY_URL = "http://localhost:8081"
TOPIC = "ticks.raw.crypto.avro.v1"
SUBJECT = f"{TOPIC}-value"

schema_path = Path(__file__).resolve().parents[2] / "schemas" / "crypto_tick_v1.avsc"
schema_obj = json.loads(schema_path.read_text(encoding="utf-8"))

headers = {"Content-Type": "application/vnd.schemaregistry.v1+json"}  

# If already exists, reuse it
latest = requests.get(f"{REGISTRY_URL}/subjects/{SUBJECT}/versions/latest", timeout=10)
if latest.status_code == 200:
    data = latest.json()
    print(f"[OK] Schema already registered: subject={SUBJECT} id={data['id']} version={data['version']}")
else:
    payload = {"schema": json.dumps(schema_obj)}
    r = requests.post(f"{REGISTRY_URL}/subjects/{SUBJECT}/versions", headers=headers, json=payload, timeout=10)
    r.raise_for_status()
    print(f"[OK] Registered schema: subject={SUBJECT} id={r.json()['id']}")
