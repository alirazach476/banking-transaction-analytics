{{ config(
    materialized='table',
    schema='intermediate',
    post_hook=[
        "create index if not exists idx_card_payments_card_ts on {{ this }} (card_id, authorization_ts)"
    ]
) }}
-- Compact, indexed per-card payment history used by the API to compute scoring-time card features.
select payment_id, card_id, authorization_ts, amount
from {{ ref('stg_payment_transactions') }}
where card_id is not null and authorization_ts is not null and amount is not null
