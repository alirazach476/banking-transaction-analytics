{{ config(materialized='table', schema='analytics') }}
-- Settlement coverage per day: cleared payments vs settlement records, and settlements with no matching payment.
with s as (
    select settlement_ts::date as settlement_date, count(*) as settlement_records,
           count(distinct payment_id) as distinct_payments, sum(settlement_amount) as settlement_amount
    from {{ ref('stg_payment_settlements') }}
    where settlement_ts is not null
    group by 1
),
orphans as (
    select s.settlement_ts::date as settlement_date, count(*) as orphan_settlements
    from {{ ref('stg_payment_settlements') }} s
    left join {{ ref('stg_payment_transactions') }} t using (payment_id)
    where t.payment_id is null and s.settlement_ts is not null
    group by 1
)
select s.*, coalesce(o.orphan_settlements, 0) as orphan_settlements,
       s.settlement_records - s.distinct_payments as duplicate_settlement_records
from s left join orphans o using (settlement_date)
