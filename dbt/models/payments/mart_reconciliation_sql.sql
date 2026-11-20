{{ config(materialized='table', schema='analytics') }}
-- SQL re-implementation of the core reconciliation exception counts, used to cross-check src/payments/reconciliation.py
-- (missing / duplicate settlements, orphan settlements). Amount/currency/late logic stays in Python (needs FX + SLA config).
with clearing as (
    select distinct on (payment_id) payment_id, event_ts as clearing_ts
    from {{ ref('stg_payment_lifecycle_events') }}
    where event_type = 'CLEARING'
    order by payment_id, event_ts
),
stl as (
    select payment_id, count(*) as n_settlements
    from {{ ref('stg_payment_settlements') }}
    group by 1
),
joined as (
    select c.payment_id, coalesce(s.n_settlements, 0) as n_settlements
    from clearing c left join stl s using (payment_id)
)
select
    count(*) as cleared_payments,
    count(*) filter (where n_settlements = 0) as missing_settlement,
    count(*) filter (where n_settlements > 1) as duplicate_settlement,
    count(*) filter (where n_settlements = 1) as single_settlement,
    (select count(*) from stl s where not exists (select 1 from clearing c where c.payment_id = s.payment_id)) as orphan_settlement_payments
from joined
