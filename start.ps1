# scripts/start.ps1
$ErrorActionPreference = "Stop"

# ---- config you may change ----
$ComposeFile = "infra/docker-compose.yml"

$KafkaContainer = "kafka"
$TopicAvro      = "ticks.raw.crypto.avro.v1"
$Partitions     = 3

$SchemaRegistryUrl = "http://127.0.0.1:8081/subjects"

# Optional: also keep a JSON topic around (only if you still use it)
$CreateJsonTopic = $false
$TopicJson = "ticks.raw.crypto.v1"

# -------------------------------

function ExecOrFail($cmd) {
  Write-Host ">> $cmd"
  cmd /c $cmd
  if ($LASTEXITCODE -ne 0) { throw "Command failed: $cmd" }
}

function Wait-ForKafka([int]$maxTries = 60, [int]$sleepSeconds = 2) {
  Write-Host "== Waiting for Kafka to be ready =="
  for ($i=1; $i -le $maxTries; $i++) {
    $out = & docker exec $KafkaContainer bash -lc "/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9093 --list" 2>$null
    if ($LASTEXITCODE -eq 0) {
      Write-Host "[OK] Kafka is ready."
      return
    }
    Start-Sleep -Seconds $sleepSeconds
  }
  throw "Kafka did not become ready in time."
}

function Ensure-Topic($topic, $partitions) {
  Write-Host "== Ensuring topic exists: $topic =="
  # Create if missing
  & docker exec $KafkaContainer bash -lc "/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9093 --create --if-not-exists --topic $topic --partitions $partitions --replication-factor 1" | Out-Null

  # Describe and enforce partition count (only increase if needed)
  $desc = & docker exec $KafkaContainer bash -lc "/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9093 --describe --topic $topic" 2>$null
  if ($LASTEXITCODE -ne 0) { throw "Failed to describe topic $topic" }

  $m = [regex]::Match($desc, "PartitionCount:\s*(\d+)")
  if (-not $m.Success) { throw "Could not parse PartitionCount for topic $topic. Output:`n$desc" }

  $current = [int]$m.Groups[1].Value
  Write-Host "Topic $topic PartitionCount=$current (desired=$partitions)"

  if ($current -lt $partitions) {
    Write-Host "== Increasing partitions for $topic to $partitions =="
    & docker exec $KafkaContainer bash -lc "/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9093 --alter --topic $topic --partitions $partitions" | Out-Null
  } elseif ($current -gt $partitions) {
    Write-Host "[WARN] Topic $topic has more partitions ($current) than desired ($partitions). Kafka cannot decrease partitions."
  } else {
    Write-Host "[OK] Topic $topic already has $partitions partitions."
  }
}

function Wait-ForSchemaRegistry([int]$maxTries = 60, [int]$sleepSeconds = 2) {
  Write-Host "== Waiting for Schema Registry (Karapace) =="
  for ($i=1; $i -le $maxTries; $i++) {
    & curl.exe -fsS $SchemaRegistryUrl 1>$null 2>$null
    if ($LASTEXITCODE -eq 0) {
      Write-Host "[OK] Schema Registry is reachable."
      return
    }
    Start-Sleep -Seconds $sleepSeconds
  }
  throw "Schema Registry did not become ready in time at $SchemaRegistryUrl"
}

# --- Start sequence ---

Write-Host "== Starting infra containers =="
ExecOrFail "docker compose -f $ComposeFile up -d kafka timescaledb valkey karapace-registry karapace-rest kafka-ui"

Wait-ForKafka

Ensure-Topic $TopicAvro $Partitions
if ($CreateJsonTopic) { Ensure-Topic $TopicJson $Partitions }

Write-Host "== Verifying Karapace endpoints (optional) =="
# Registry subjects + REST proxy topics
& curl.exe -fsS "http://127.0.0.1:8081/subjects" | Out-Null
& curl.exe -fsS "http://127.0.0.1:8082/topics"   | Out-Null

Wait-ForSchemaRegistry

Write-Host "== Registering Avro schema (idempotent script) =="
# Run from repo root (assumes python is available and script exists)
ExecOrFail "python tools/schema_registry/register_avro.py"

Write-Host "== Starting Spark processor (last) =="
ExecOrFail "docker compose -f $ComposeFile up -d --build spark-processor"

Write-Host ""
Write-Host "[NEXT] Start your Kraken Avro producer in a separate terminal."
Write-Host "[CHECK] Offsets:"
Write-Host "  docker exec -it kafka bash -lc ""/opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:9093 --topic $TopicAvro --time -1"""
Write-Host "[CHECK] DB:"
Write-Host "  docker exec -it timescaledb psql -U postgres -d stock_db -c ""SELECT COUNT(*) FROM market_candles_1m;"""
