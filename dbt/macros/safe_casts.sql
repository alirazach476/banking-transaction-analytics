{# Safe casts: return NULL instead of failing on injected invalid values (Postgres). #}
{% macro safe_ts(col) %}
    case when trim({{ col }}) ~ '^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|30|31)[ T]([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]'
              and not (trim({{ col }}) ~ '^[0-9]{4}-(02-(30|31)|(04|06|09|11)-31)')
         then replace(trim({{ col }}), 'T', ' ')::timestamp end
{% endmacro %}

{% macro safe_numeric(col) %}
    case when trim({{ col }}) ~ '^-?[0-9]+(\.[0-9]+)?$' then trim({{ col }})::numeric end
{% endmacro %}
