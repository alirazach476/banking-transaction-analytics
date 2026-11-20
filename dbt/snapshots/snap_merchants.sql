{% snapshot snap_merchants %}
{{
    config(
        target_schema='snapshots',
        unique_key='merchant_id',
        strategy='check',
        check_cols=['merchant_status', 'merchant_category', 'city', 'region'],
    )
}}
-- SCD Type 2 history of merchant attributes (dbt_valid_from / dbt_valid_to).
select merchant_id, merchant_name, merchant_category, city, region, merchant_status
from {{ ref('stg_merchants') }}
{% endsnapshot %}
