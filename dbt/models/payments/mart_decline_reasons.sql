{{ config(materialized='table', schema='analytics') }}
select
    date_trunc('month', payment_date)::date as month,
    channel,
    coalesce(decline_reason, 'UNSPECIFIED') as decline_reason,
    count(*) as declined_payments,
    sum(amount) as declined_amount
from {{ ref('int_payment_outcomes') }}
where declined and payment_date is not null
group by 1,2,3
