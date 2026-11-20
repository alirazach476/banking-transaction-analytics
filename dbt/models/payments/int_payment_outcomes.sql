{{ config(materialized='table', schema='intermediate') }}
-- One row per payment with lifecycle flags (mirrors src/payments/kpis.py payment_outcomes).
select
    t.payment_id, t.merchant_category, t.channel, t.currency, t.is_international, t.amount,
    t.authorization_ts::date as payment_date,
    coalesce(bool_or(e.event_type = 'AUTH_RESPONSE' and e.event_status = 'APPROVED'), false) as authorized,
    coalesce(bool_or(e.event_type = 'AUTH_RESPONSE' and e.event_status = 'DECLINED'), false) as declined,
    max(e.reason_code) filter (where e.event_type = 'AUTH_RESPONSE' and e.event_status = 'DECLINED') as decline_reason,
    avg(e.response_ms) filter (where e.event_type = 'AUTH_RESPONSE') as response_ms,
    coalesce(bool_or(e.event_type = 'CLEARING'), false) as cleared,
    coalesce(bool_or(e.event_type = 'SETTLEMENT'), false) as settled,
    coalesce(bool_or(e.event_type = 'REVERSAL'), false) as reversed,
    coalesce(bool_or(e.event_type = 'REFUND'), false) as refunded,
    coalesce(bool_or(e.event_type = 'CHARGEBACK'), false) as charged_back
from {{ ref('stg_payment_transactions') }} t
left join {{ ref('stg_payment_lifecycle_events') }} e using (payment_id)
group by 1,2,3,4,5,6,7
