{{ config(materialized='view', schema='staging') }}
-- Status is normalised from event_type: the dirty status values (APPROVD, DONE, N/A, UNKNOWN) are an injected defect.
with ranked as (
    select *, row_number() over (partition by trim(event_id) order by _ingested_at desc) rn
    from {{ source('raw_payments', 'payment_lifecycle_events') }}
    where nullif(trim(event_id), '') is not null
)
select
    trim(event_id) as event_id,
    trim(payment_id) as payment_id,
    upper(trim(event_type)) as event_type,
    {{ safe_ts('event_ts') }} as event_ts,
    {{ safe_numeric('amount') }} as amount,
    nullif(upper(trim(currency)), '') as currency,
    case
        when upper(trim(event_type)) = 'AUTH_REQUEST' then 'REQUESTED'
        when upper(trim(event_type)) = 'AUTH_RESPONSE'
             then case when upper(trim(event_status)) = 'DECLINED' then 'DECLINED' else 'APPROVED' end
        when upper(trim(event_type)) = 'CLEARING' then 'CLEARED'
        when upper(trim(event_type)) = 'SETTLEMENT' then 'SETTLED'
        when upper(trim(event_type)) = 'REVERSAL' then 'REVERSED'
        when upper(trim(event_type)) = 'REFUND' then 'REFUNDED'
        when upper(trim(event_type)) = 'CHARGEBACK' then 'CHARGEBACK'
    end as event_status,
    nullif(trim(reason_code), '') as reason_code,
    case when trim(response_ms) ~ '^[0-9]{1,9}$' then trim(response_ms)::int end as response_ms,
    nullif(dq_defect, '') as dq_defect
from ranked where rn = 1
