import json
import psycopg2
from psycopg2.extras import execute_values
import redis

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DoubleType, LongType, IntegerType
)

import config


TICK_SCHEMA = StructType([
    StructField("event_id", StringType(), True),
    StructField("ts", StringType(), True),          # ISO-8601 string
    StructField("symbol", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("volume", DoubleType(), True),
    StructField("schema_version", IntegerType(), True),
    StructField("source", StringType(), True),
])


def get_spark() -> SparkSession:
    spark = (
        SparkSession.builder
        .appName("stock-candles-1m")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def upsert_timescale(rows: list[tuple]) -> None:
    if not rows:
        return

    conn = psycopg2.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )
    cur = conn.cursor()

    # UPSERT is atomic and is the correct way to make streaming-to-DB idempotent. :contentReference[oaicite:6]{index=6}
    sql = f"""
    INSERT INTO {config.POSTGRES_TABLE} (time, symbol, open, high, low, close, volume)
    VALUES %s
    ON CONFLICT (time, symbol) DO UPDATE SET
      open = EXCLUDED.open,
      high = EXCLUDED.high,
      low = EXCLUDED.low,
      close = EXCLUDED.close,
      volume = EXCLUDED.volume;
    """

    execute_values(cur, sql, rows, page_size=1000)
    conn.commit()
    cur.close()
    conn.close()


def update_valkey(latest_records: list[dict]) -> None:
    if not latest_records:
        return

    r = redis.Redis(host=config.VALKEY_HOST, port=config.VALKEY_PORT, decode_responses=True)
    pipe = r.pipeline()
    for rec in latest_records:
        key = f"{config.VALKEY_PREFIX}:{rec['symbol']}"
        pipe.set(key, json.dumps(rec))
    pipe.execute()


def process_batch(batch_df, batch_id: int) -> None:
    # foreachBatch runs once per micro-batch. :contentReference[oaicite:7]{index=7}
    batch_df.persist()

    count = batch_df.count()
    if count == 0:
        print(f"[batch {batch_id}] empty")
        batch_df.unpersist()
        return

    # 1) Write ALL candles in this batch to TimescaleDB (warm store)
    rows = batch_df.select(
        "time", "symbol", "open", "high", "low", "close", "volume"
    ).collect()

    to_upsert = []
    for r in rows:
        to_upsert.append((
            r["time"],
            r["symbol"],
            float(r["open"]) if r["open"] is not None else None,
            float(r["high"]) if r["high"] is not None else None,
            float(r["low"]) if r["low"] is not None else None,
            float(r["close"]) if r["close"] is not None else None,
            float(r["volume"]) if r["volume"] is not None else None,
        ))
    upsert_timescale(to_upsert)

    # 2) Update Valkey with ONLY the latest candle per symbol (hot store)
    latest_df = (
        batch_df.groupBy("symbol")
        .agg(F.max("time").alias("time"))
        .join(batch_df, ["symbol", "time"], "inner")
    )
    latest_rows = latest_df.collect()

    latest_records = []
    for r in latest_rows:
        latest_records.append({
            "time": r["time"].isoformat(),
            "symbol": r["symbol"],
            "open": float(r["open"]) if r["open"] is not None else None,
            "high": float(r["high"]) if r["high"] is not None else None,
            "low": float(r["low"]) if r["low"] is not None else None,
            "close": float(r["close"]) if r["close"] is not None else None,
            "volume": float(r["volume"]) if r["volume"] is not None else None,
        })
    update_valkey(latest_records)

    print(f"[batch {batch_id}] upserted={len(to_upsert)} latest_symbols={len(latest_records)}")
    batch_df.unpersist()


def main() -> None:
    spark = get_spark()

    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", config.KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", config.KAFKA_TOPIC)
        .option("startingOffsets", config.STARTING_OFFSETS)
        .load()
    )

    parsed = (
        raw.select(
            F.col("key").cast("string").alias("kafka_key"),
            F.col("value").cast("string").alias("json_str"),
            F.col("timestamp").alias("kafka_ts"),
        )
        .select(
            F.from_json("json_str", TICK_SCHEMA).alias("t"),
            "kafka_key",
            "kafka_ts",
        )
        .select("t.*", "kafka_key", "kafka_ts")
        .withColumn("event_time", F.to_timestamp("ts", "yyyy-MM-dd'T'HH:mm:ss.SSSSSSX"))
        .withColumn("event_time", F.coalesce(F.col("event_time"), F.col("kafka_ts")))
        .withWatermark("event_time", config.WATERMARK_DELAY)
    )

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
            F.sum("volume").alias("volume")

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
        .foreachBatch(process_batch)
        .trigger(processingTime=config.TRIGGER_INTERVAL)
        .start()
    )

    print("[RUN] Spark streaming started.")
    query.awaitTermination()


if __name__ == "__main__":
    main()
