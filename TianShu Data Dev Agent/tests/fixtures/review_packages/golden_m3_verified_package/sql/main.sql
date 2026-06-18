-- 草案：未经验证，未经人审，不得上线。
-- M2 阶段未执行 SQL，未连接生产库。
SELECT
    trip_date AS trip_date,
    SUM(trip_count) AS trip_count,
    SUM(total_fare_amount) AS total_fare_amount,
    SUM(total_distance_miles) AS total_distance_miles
FROM gold.dws_daily_trip_summary
WHERE trip_date BETWEEN '2026-01-01' AND '2026-03-31'
GROUP BY trip_date
ORDER BY trip_date;
