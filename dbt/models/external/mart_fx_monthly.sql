{{ config(materialized='table', schema='external_analytics') }}
-- Monthly average, min, max and month-over-month change of external (ECB) FX reference rates.
with m as (
    select base_currency, target_currency, date_trunc('month', effective_date)::date as month,
           avg(rate) as avg_rate, min(rate) as min_rate, max(rate) as max_rate, count(*) as obs
    from {{ source('external_staging', 'stg_exchange_rates') }}
    group by 1,2,3
)
select *, avg_rate / nullif(lag(avg_rate) over (partition by base_currency, target_currency order by month), 0) - 1 as mom_change
from m
