{#
  Customer activity segments (documented thresholds):
  - Inactive: days_since_last_transaction > 90 OR transaction_count = 0
  - Low Activity: transaction_count < 10
  - Medium Activity: 10–49 transactions
  - High Activity: 50–199 transactions
  - Premium Activity: >= 200 transactions
#}
with metrics as (
    select * from {{ ref('int_customer_transaction_metrics') }}
),

customers as (
    select
        customer_id,
        first_name,
        last_name,
        customer_type,
        customer_status,
        city,
        region,
        country
    from {{ ref('stg_customers') }}
)

select
    c.customer_id,
    c.first_name,
    c.last_name,
    c.customer_type,
    c.customer_status,
    c.city,
    c.region,
    c.country,
    m.transaction_count,
    m.completed_count,
    m.failed_count,
    m.pending_count,
    m.total_amount,
    m.total_completed_amount,
    round(m.avg_completed_amount, 2) as avg_completed_amount,
    m.first_transaction_at,
    m.last_transaction_at,
    m.days_since_last_transaction,
    m.distinct_channels,
    m.distinct_accounts,
    case
        when coalesce(m.transaction_count, 0) = 0
          or coalesce(m.days_since_last_transaction, 9999) > 90 then 'Inactive'
        when m.transaction_count < 10 then 'Low Activity'
        when m.transaction_count between 10 and 49 then 'Medium Activity'
        when m.transaction_count between 50 and 199 then 'High Activity'
        when m.transaction_count >= 200 then 'Premium Activity'
        else 'Unknown'
    end as activity_segment,
    current_timestamp as refreshed_at
from customers c
left join metrics m on c.customer_id = m.customer_id
