import requests

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.avro.functions import from_avro

import config

# Reuse your existing process_batch + sinks from main.py
# If your existing file is spark_processor/main.py with process_batch defined:
from main import process_batch  # <- keep your existing code there


def fetch_latest_schema_str() -> str:
    """
    Fetch schema string from Karapace Schema Registry (Confluent-compatible API).
    """
    url = f"{config.SCHEMA_REGISTRY_URL}/subjects/{config.SCHEMA_SUBJECT}/versions/latest"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    # Confluent/compatible SR returns schema as a JSON string
    return r.json()["schema"]


def get_spark() -> SparkSession:
    spark = (
        SparkSession.builder
        .appName("digital-assets-candles-1m-avro")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def main() -> None:
    spark = get_spark()

    avro_schema_str = fetch_latest_schema_str()

    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", config.KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", config.KAFKA_TOPIC)
        .option("startingOffsets", config.STARTING_OFFSETS)
        .load()
    )

    is_not_null = F.col("value").isNotNull()
    has_min_len = F.length(F.col("value")) > F.lit(5)

    # Magic byte check (byte 1, length 1) -> hex should be "00"
    magic_hex = F.hex(F.expr("substring(value, 1, 1)"))
    is_confluent = magic_hex == F.lit("00")

    raw_valid = raw.where(is_not_null & has_min_len & is_confluent)

    # 2) Strip Confluent header (magic byte + 4-byte schema id = 5 bytes)
    # Spark substring is 1-indexed; payload starts at byte 6
    payload = F.expr("substring(value, 6, 2147483647)")

    # 3) Decode Avro with PERMISSIVE mode (skip malformed instead of FAILFAST)
    t = from_avro(payload, avro_schema_str, {"mode": "PERMISSIVE"})

    decoded = (
    raw_valid
    .select(
        F.col("key").cast("string").alias("kafka_key"),
        F.col("timestamp").alias("kafka_ts"),
        t.alias("t")
    )
    .where(F.col("t").isNotNull())      # drop malformed
    .select("t.*", "kafka_key", "kafka_ts")
)

    # Timestamp parsing (keep resilient)
    ts_clean = F.when(
        F.col("ts").endswith("Z"),
        F.regexp_replace(F.col("ts"), "Z$", "+00:00")
    ).otherwise(F.col("ts"))

    parsed = (
        decoded
        .withColumn("event_time", F.to_timestamp(ts_clean))
        .withColumn("event_time", F.coalesce(F.col("event_time"), F.col("kafka_ts")))
        .withWatermark("event_time", config.WATERMARK_DELAY)
    )

    # === Keep your existing candle aggregation unchanged ===
    candles = (
        parsed.groupBy(
            F.window(F.col("event_time"), config.WINDOW_DURATION).alias("w"),
            F.col("symbol"),
        )
        .agg(
            F.expr("min_by(price, event_time)").alias("open"),
            F.max("price").alias("high"),
            F.min("price").alias("low"),
            F.expr("max_by(price, event_time)").alias("close"),
            F.sum("volume").alias("volume"),
        )
        .select(
            F.col("w").start.alias("time"),
            "symbol", "open", "high", "low", "close", "volume"
        )
    )

    query = (
        candles.writeStream
        .outputMode("update")
        .option("checkpointLocation", config.CHECKPOINT_DIR)
        .foreachBatch(process_batch)  # foreachBatch is the correct custom-sink pattern :contentReference[oaicite:6]{index=6}
        .trigger(processingTime=config.TRIGGER_INTERVAL)
        .start()
    )

    print("[RUN] Spark Avro streaming started.")
    query.awaitTermination()


if __name__ == "__main__":
    main()
