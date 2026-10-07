{#
  Simplified SCD Type 2 for customer portfolio:
  tracks changes to customer_status and customer_type over time.
#}
with customers as (
    select
        customer_id,
        first_name,
        last_name,
        date_of_birth,
        gender,
        customer_type,
        registration_date,
        customer_status,
        city,
        region,
        country,
        coalesce(registration_date, current_date) as effective_date
    from {{ ref('stg_customers') }}
),

versioned as (
    select
        customer_id,
        first_name,
        last_name,
        date_of_birth,
        gender,
        customer_type,
        registration_date,
        customer_status,
        city,
        region,
        country,
        effective_date,
        lead(effective_date) over (
            partition by customer_id
            order by effective_date
        ) as next_effective_date
    from customers
)

select
    row_number() over (order by customer_id, effective_date) as customer_key,
    customer_id,
    first_name,
    last_name,
    date_of_birth,
    gender,
    customer_type,
    registration_date,
    customer_status,
    city,
    region,
    country,
    effective_date,
    coalesce(next_effective_date - interval '1 day', '9999-12-31'::date) as expiration_date,
    next_effective_date is null as is_current,
    current_timestamp as loaded_at
from versioned
