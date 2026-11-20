{{ config(materialized='view', schema='staging') }}
with ranked as (
    select *, row_number() over (partition by trim(payment_id) order by _ingested_at desc) rn
    from {{ source('raw_payments', 'payment_transactions') }}
    where nullif(trim(payment_id), '') is not null
)
select
    trim(payment_id) as payment_id,
    trim(card_id) as card_id,
    trim(customer_id) as customer_id,
    trim(account_id) as account_id,
    trim(merchant_id) as merchant_id,
    initcap(trim(merchant_category)) as merchant_category,
    upper(trim(merchant_country)) as merchant_country,
    upper(trim(card_country)) as card_country,
    trim(channel) as channel,
    {{ safe_numeric('amount') }} as amount,
    case when upper(trim(currency)) ~ '^[A-Z]{3}$' then upper(trim(currency)) end as currency,
    {{ safe_ts('authorization_ts') }} as authorization_ts,
    (lower(trim(is_international)) = 'true') as is_international,
    nullif(trim(synthetic_fraud_pattern), '') as synthetic_fraud_pattern,
    nullif(dq_defect, '') as dq_defect
from ranked where rn = 1
