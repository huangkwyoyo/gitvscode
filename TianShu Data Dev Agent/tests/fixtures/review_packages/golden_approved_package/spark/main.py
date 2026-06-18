# 草案：未经验证，未经人审，不得上线。
# M2 阶段未执行 Spark，未连接生产环境。
from pyspark.sql import functions as F

def build_dataframe(spark):
    df = spark.table("gold.dws_daily_trip_summary")
    df = df.where((F.col("trip_date") >= "2026-01-01") & (F.col("trip_date") <= "2026-03-31"))
    result = df.groupBy("trip_date").agg(
        F.sum("trip_count").alias("trip_count"),
        F.sum("total_fare_amount").alias("total_fare_amount"),
        F.sum("total_distance_miles").alias("total_distance_miles")
    )
    return result.select("trip_date", 'trip_count', 'total_fare_amount', 'total_distance_miles')
