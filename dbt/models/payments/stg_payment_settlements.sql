{{ config(materialized='view', schema='staging') }}
select
    trim(settlement_id) as settlement_id,
    trim(payment_id) as payment_id,
    trim(batch_id) as batch_id,
    {{ safe_ts('settlement_ts') }} as settlement_ts,
    {{ safe_numeric('settlement_amount') }} as settlement_amount,
    upper(trim(settlement_currency)) as settlement_currency
from {{ source('raw_payments', 'payment_settlements') }}
where nullif(trim(settlement_id), '') is not null
