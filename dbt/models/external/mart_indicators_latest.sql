{{ config(materialized='table', schema='external_analytics') }}
-- Latest observation per indicator and country, with change versus the previous observation and ~1 year earlier.
with o as (
    select indicator_id, indicator_name, country, observation_date, value, unit,
           row_number() over (partition by indicator_id, country order by observation_date desc) as rn
    from {{ source('external_staging', 'stg_economic_indicators') }}
    where value is not null
),
latest as (select * from o where rn = 1),
prev as (select * from o where rn = 2)
select l.indicator_id, l.indicator_name, l.country, l.observation_date as latest_date, l.value as latest_value, l.unit,
       p.value as previous_value, l.value - p.value as change_vs_previous,
       (select value from {{ source('external_staging', 'stg_economic_indicators') }} y
         where y.indicator_id = l.indicator_id and y.country = l.country
           and y.observation_date <= l.observation_date - interval '1 year' and y.value is not null
         order by y.observation_date desc limit 1) as value_1y_earlier
from latest l left join prev p using (indicator_id, country)
