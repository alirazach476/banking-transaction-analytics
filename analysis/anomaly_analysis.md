# Anomaly Detection Evaluation Guide

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

## Purpose

The data generator **injects controlled anomalies** with ground-truth flags. This guide explains how to evaluate detection behavior against those labels without over-claiming fraud detection accuracy.

---

## Ground Truth Fields

In source and raw layers:

| Field | Location | Meaning |
|-------|----------|---------|
| `is_injected_anomaly` | raw.transactions | `true` if generator injected anomaly |
| `anomaly_type` | raw.transactions | Category: high_amount, high_frequency, rapid_transactions, night_activity, multiple_failures, sudden_behavior_change, unusual_location |

Injection rate: `ANOMALY_INJECTION_RATE` (default 2%).

Warehouse: `fact_transactions.is_anomaly` may reflect injection or detection flags depending on transform logic.

---

## Evaluation Approach

### Step 1: Build detection results

```powershell
python -m src.pipeline.run_pipeline --skip-generate
# or: make anomaly-detection
```

### Step 2: Join labels to detections

```sql
WITH labeled AS (
    SELECT
        t.transaction_id,
        COALESCE(t.is_injected_anomaly::boolean, false) AS is_injected,
        t.anomaly_type AS injected_type
    FROM raw.transactions t
    WHERE t.is_injected_anomaly IS NOT NULL
),
detected AS (
    SELECT DISTINCT transaction_id
    FROM monitoring.transaction_anomalies
)
SELECT
    l.is_injected,
    COUNT(*) AS txn_count,
    COUNT(d.transaction_id) AS detected_count
FROM labeled l
LEFT JOIN detected d ON l.transaction_id = d.transaction_id
GROUP BY l.is_injected;
```

### Step 3: Break down by injected type

```sql
SELECT
    r.anomaly_type,
    COUNT(*) AS injected_count,
    COUNT(m.transaction_id) AS flagged_by_detector
FROM raw.transactions r
LEFT JOIN monitoring.transaction_anomalies m
    ON r.transaction_id = m.transaction_id
WHERE COALESCE(r.is_injected_anomaly, 'false') IN ('true', 'True', '1')
GROUP BY r.anomaly_type
ORDER BY injected_count DESC;
```

### Step 4: Review false positives

```sql
SELECT m.transaction_id, m.amount, m.anomaly_reason, m.severity
FROM monitoring.transaction_anomalies m
LEFT JOIN raw.transactions r ON m.transaction_id = r.transaction_id
WHERE COALESCE(r.is_injected_anomaly, 'false') NOT IN ('true', 'True', '1')
ORDER BY m.rule_based_score DESC
LIMIT 50;
```

Legitimate high-value business transactions may appear — expected for unsupervised methods.

---

## Method-Specific Evaluation

### Rule-based

Check recall per rule against `anomaly_type`:

| Injected type | Expected rule hit |
|---------------|-------------------|
| high_amount | Unusually High Amount |
| high_frequency | Unusually High Frequency |
| rapid_transactions | Rapid Transactions |
| night_activity | Unusual Transaction Time |
| multiple_failures | Multiple Failed Transactions |
| sudden_behavior_change | Sudden Behavior Change |

### Z-score

Effective for `high_amount` and some `sudden_behavior_change`. Less effective for frequency-only anomalies unless amount also deviates.

### Isolation Forest

Multivariate — may catch combinations missed by single rules. Compare `ml_anomaly_flag` against injected set.

---

## Metrics (Use with Caution)

If computing precision/recall:

```text
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
```

Where TP = injected AND detected.

**Caveats:**

- Labels are synthetic and cleaner than real fraud
- Detection tuned for demo visibility (2% contamination)
- Do not cite metrics as production fraud performance

Document results qualitatively in interviews: *"Rule-based recall was strong on high_amount injections; IF added multivariate catches at cost of false positives on premium customers."*

---

## Severity Distribution

```sql
SELECT severity, COUNT(*)
FROM monitoring.transaction_anomalies
GROUP BY severity;
```

Critical severity should correlate with high_amount + multi-method agreement.

---

## Comparison to mart_anomaly_monitoring

```sql
SELECT activity_segment, COUNT(*) AS anomalies
FROM analytics.mart_anomaly_monitoring m
JOIN analytics.mart_customer_activity c USING (customer_id)
GROUP BY activity_segment;
```

Premium Activity segments may have higher absolute anomaly counts due to volume — normalize with **anomaly rate** not raw count.

---

## Tuning Parameters

Adjust in `.env` and re-run:

| Parameter | Effect |
|-----------|--------|
| ANOMALY_ZSCORE_THRESHOLD | ↑ reduces z-score flags |
| ANOMALY_HIGH_AMOUNT_MULTIPLIER | ↑ reduces high-amount rules |
| ANOMALY_RAPID_COUNT_THRESHOLD | ↑ reduces rapid txn flags |
| ISOLATION_FOREST_CONTAMINATION | ↓ reduces ML flags |

---

## Reporting Template

```markdown
### Anomaly Evaluation (Synthetic Demo Run)

- Injected anomalies: N (2% of transactions)
- Detected (any method): M
- Overlap (TP): X
- Recall (approx): X/N
- Top missed type: [type] — [hypothesis]
- Top false positive pattern: [pattern]
- Conclusion: Prototype suitable for demonstration; not production fraud.
```

Fill N, M, X from actual queries after pipeline run.

---

## Related Documentation

- [docs/anomaly_detection.md](../docs/anomaly_detection.md)
- [docs/interview_guide.md](../docs/interview_guide.md) (Q22–26)
- [sql/analytics/anomaly_candidates.sql](../sql/analytics/anomaly_candidates.sql)
