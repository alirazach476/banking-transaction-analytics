with date_spine as (
    select generate_series(
        '{{ var("date_spine_start") }}'::date,
        '{{ var("date_spine_end") }}'::date,
        interval '1 day'
    )::date as calendar_date
)

select
    to_char(calendar_date, 'YYYYMMDD')::int as date_key,
    calendar_date,
    extract(year from calendar_date)::int as calendar_year,
    extract(quarter from calendar_date)::int as calendar_quarter,
    extract(month from calendar_date)::int as calendar_month,
    to_char(calendar_date, 'Month') as month_name,
    extract(week from calendar_date)::int as calendar_week,
    extract(dow from calendar_date)::int as day_of_week,
    to_char(calendar_date, 'Day') as day_name,
    extract(day from calendar_date)::int as day_of_month,
    extract(doy from calendar_date)::int as day_of_year,
    case when extract(dow from calendar_date) in (0, 6) then true else false end as is_weekend,
    (date_trunc('month', calendar_date) + interval '1 month - 1 day')::date = calendar_date as is_month_end,
    (date_trunc('quarter', calendar_date) + interval '3 months - 1 day')::date = calendar_date as is_quarter_end,
    (date_trunc('year', calendar_date) + interval '1 year - 1 day')::date = calendar_date as is_year_end
from date_spine
