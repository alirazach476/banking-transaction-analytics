with enriched as (
    select * from {{ ref('int_transaction_enriched') }}
    where transaction_status = 'Completed'
),

customer_stats as (
    select
        customer_id,
        avg(amount) as customer_avg_amount,
        stddev_pop(amount) as customer_stddev_amount,
        count(*) as customer_txn_count
    from enriched
    group by customer_id
),

scored as (
    select
        e.transaction_id,
        e.customer_id,
        e.account_id,
        e.transaction_timestamp,
        e.transaction_date,
        e.transaction_type,
        e.channel,
        e.amount,
        e.currency,
        e.is_injected_anomaly,
        e.anomaly_type,
        cs.customer_avg_amount,
        cs.customer_stddev_amount,
        cs.customer_txn_count,
        case
            when cs.customer_stddev_amount > 0
            then (e.amount - cs.customer_avg_amount) / cs.customer_stddev_amount
            else 0
        end as amount_z_score,
        avg(e.amount) over (
            partition by e.customer_id
            order by e.transaction_timestamp
            rows between 29 preceding and current row
        ) as rolling_30d_avg_amount,
        stddev_pop(e.amount) over (
            partition by e.customer_id
            order by e.transaction_timestamp
            rows between 29 preceding and current row
        ) as rolling_30d_stddev_amount,
        count(*) over (
            partition by e.customer_id
            order by e.transaction_timestamp
            rows between 6 preceding and current row
        ) as rolling_7d_txn_count
    from enriched e
    inner join customer_stats cs on e.customer_id = cs.customer_id
)

select
    *,
    case
        when rolling_30d_stddev_amount > 0
        then (amount - rolling_30d_avg_amount) / rolling_30d_stddev_amount
        else amount_z_score
    end as rolling_amount_z_score,
    case
        when abs(amount_z_score) >= 3 then true
        when abs(
            case
                when rolling_30d_stddev_amount > 0
                then (amount - rolling_30d_avg_amount) / rolling_30d_stddev_amount
                else amount_z_score
            end
        ) >= 3 then true
        else false
    end as is_statistical_outlier
from scored
