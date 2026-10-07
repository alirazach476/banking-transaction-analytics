with transactions as (
    select * from {{ ref('stg_transactions') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

accounts as (
    select * from {{ ref('stg_accounts') }}
),

branches as (
    select * from {{ ref('stg_branches') }}
),

merchants as (
    select * from {{ ref('stg_merchants') }}
)

select
    t.transaction_id,
    t.account_id,
    t.customer_id,
    t.transaction_timestamp,
    t.transaction_timestamp::date as transaction_date,
    t.transaction_type,
    t.amount,
    t.currency,
    t.channel,
    t.merchant_id,
    t.branch_id,
    t.transaction_status,
    t.reference_type,
    t.is_injected_anomaly,
    t.anomaly_type,
    t.updated_at,
    c.first_name,
    c.last_name,
    c.customer_type,
    c.customer_status,
    c.city as customer_city,
    c.region as customer_region,
    a.account_type,
    a.account_status,
    a.current_balance as account_balance,
    b.branch_name,
    b.city as branch_city,
    b.region as branch_region,
    m.merchant_name,
    m.merchant_category,
    case
        when t.transaction_status = 'Completed' then t.amount
        else 0
    end as completed_amount,
    case
        when t.transaction_status in ('Failed', 'Reversed') then 1
        else 0
    end as is_failure_flag
from transactions t
left join customers c on t.customer_id = c.customer_id
left join accounts a on t.account_id = a.account_id
left join branches b on t.branch_id = b.branch_id
left join merchants m on t.merchant_id = m.merchant_id
