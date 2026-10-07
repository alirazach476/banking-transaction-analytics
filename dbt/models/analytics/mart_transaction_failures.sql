with enriched as (
    select * from {{ ref('int_transaction_enriched') }}
),

failures as (
    select *
    from enriched
    where transaction_status in ('Failed', 'Reversed', 'Pending')
)

select
    transaction_id,
    customer_id,
    account_id,
    transaction_timestamp,
    transaction_date,
    transaction_type,
    amount,
    currency,
    channel,
    branch_id,
    merchant_id,
    transaction_status,
    reference_type,
    is_injected_anomaly,
    anomaly_type,
    customer_type,
    account_type,
    branch_name,
    merchant_name,
    case transaction_status
        when 'Failed' then 'Hard Failure'
        when 'Reversed' then 'Reversal'
        when 'Pending' then 'Stuck Pending'
        else 'Other'
    end as failure_category,
    current_timestamp as refreshed_at
from failures
