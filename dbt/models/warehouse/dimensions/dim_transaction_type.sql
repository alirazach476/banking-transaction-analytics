with types as (
    select distinct transaction_type
    from {{ ref('stg_transactions') }}
    where transaction_type is not null

    union

    select distinct transaction_type
    from {{ ref('stg_atm_transactions') }}
    where transaction_type is not null
)

select
    row_number() over (order by transaction_type) as transaction_type_key,
    transaction_type,
    case
        when transaction_type in ('Deposit', 'Credit') then 'Credit'
        when transaction_type in ('Withdrawal', 'Payment', 'Debit') then 'Debit'
        when transaction_type = 'Balance Inquiry' then 'Inquiry'
        else 'Other'
    end as transaction_category,
    current_timestamp as loaded_at
from types
