{#
  Anomaly monitoring mart — joins statistical features with transaction context.
  External Python jobs may populate monitoring.anomaly_scores; this mart surfaces
  dbt-computed z-score features as a baseline monitoring layer.
#}
with features as (
    select * from {{ ref('int_anomaly_features') }}
),

enriched as (
    select
        transaction_id,
        customer_id,
        account_id,
        transaction_type,
        channel,
        transaction_status,
        is_injected_anomaly,
        anomaly_type
    from {{ ref('int_transaction_enriched') }}
)

select
    f.transaction_id,
    f.customer_id,
    f.account_id,
    f.transaction_timestamp,
    f.transaction_date,
    f.transaction_type,
    f.channel,
    e.transaction_status,
    f.amount,
    f.currency,
    f.is_injected_anomaly,
    f.anomaly_type,
    round(f.amount_z_score, 4) as amount_z_score,
    round(f.rolling_amount_z_score, 4) as rolling_amount_z_score,
    round(f.rolling_30d_avg_amount, 2) as rolling_30d_avg_amount,
    f.rolling_7d_txn_count,
    f.is_statistical_outlier,
    case
        when f.is_injected_anomaly then 'Injected Anomaly'
        when f.is_statistical_outlier then 'Statistical Outlier'
        else 'Normal'
    end as monitoring_flag,
    current_timestamp as refreshed_at
from features f
left join enriched e on f.transaction_id = e.transaction_id
