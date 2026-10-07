# EXPLAIN ANALYZE Results (live run)
> Synthetic NovaBank data. Numbers below are from an actual PostgreSQL run.

## daily_txn_count
```
Limit  (cost=0.29..448.03 rows=100 width=44) (actual time=0.561..8.798 rows=100.00 loops=1)
  Buffers: shared hit=199 read=9
  ->  GroupAggregate  (cost=0.29..4902.98 rows=1095 width=44) (actual time=0.559..8.773 rows=100.00 loops=1)
        Group Key: date_key
        Buffers: shared hit=199 read=9
        ->  Index Scan using idx_fact_txn_date_key on fact_transactions  (cost=0.29..4127.29 rows=101600 width=10) (actual time=0.238..4.701 rows=9160.00 loops=1)
              Index Searches: 1
              Buffers: shared hit=199 read=9
Planning:
  Buffers: shared hit=196
Planning Time: 1.723 ms
Execution Time: 8.902 ms
```

## customer_activity
```
Limit  (cost=4169.04..4169.09 rows=20 width=48) (actual time=98.456..98.463 rows=20.00 loops=1)
  Buffers: shared hit=2243
  ->  Sort  (cost=4169.04..4178.70 rows=3862 width=48) (actual time=98.454..98.458 rows=20.00 loops=1)
        Sort Key: (sum(amount)) DESC
        Sort Method: top-N heapsort  Memory: 27kB
        Buffers: shared hit=2243
        ->  HashAggregate  (cost=4018.00..4066.28 rows=3862 width=48) (actual time=92.584..95.889 rows=3908.00 loops=1)
              Group Key: customer_key
              Batches: 1  Memory Usage: 1681kB
              Buffers: shared hit=2240
              ->  Seq Scan on fact_transactions  (cost=0.00..3256.00 rows=101600 width=14) (actual time=0.020..28.029 rows=101600.00 loops=1)
                    Buffers: shared hit=2240
Planning:
  Buffers: shared hit=22
Planning Time: 0.296 ms
Execution Time: 99.209 ms
```

## anomaly_by_severity
```
HashAggregate  (cost=436.29..436.32 rows=3 width=44) (actual time=9.017..9.022 rows=3.00 loops=1)
  Group Key: severity
  Batches: 1  Memory Usage: 32kB
  Buffers: shared hit=285
  ->  Seq Scan on transaction_anomalies  (cost=0.00..371.45 rows=8645 width=11) (actual time=0.035..2.351 rows=8645.00 loops=1)
        Buffers: shared hit=285
Planning:
  Buffers: shared hit=93
Planning Time: 1.248 ms
Execution Time: 9.088 ms
```
