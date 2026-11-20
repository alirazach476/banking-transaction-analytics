{{ config(materialized='table', schema='analytics') }}
-- Denominators as in docs/BUSINESS_METRICS.md: approval = approved/(approved+declined);
-- completion = cleared/approved; settlement = settled/cleared.
select
    payment_date,
    count(*) as payments,
    count(*) filter (where authorized) as approved,
    count(*) filter (where declined) as declined,
    count(*) filter (where cleared) as cleared,
    count(*) filter (where settled) as settled,
    count(*) filter (where reversed) as reversed,
    count(*) filter (where refunded) as refunded,
    count(*) filter (where charged_back) as charged_back,
    count(*) filter (where authorized)::numeric / nullif(count(*) filter (where authorized or declined), 0) as approval_rate,
    count(*) filter (where cleared)::numeric / nullif(count(*) filter (where authorized), 0) as completion_rate,
    count(*) filter (where settled)::numeric / nullif(count(*) filter (where cleared), 0) as settlement_rate,
    avg(response_ms) as avg_response_ms
from {{ ref('int_payment_outcomes') }}
where payment_date is not null
group by 1
