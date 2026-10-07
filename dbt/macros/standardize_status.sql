{% macro standardize_status(column_name, domain='generic') %}
    case
        when {{ column_name }} is null or trim({{ column_name }}) = '' then
            {% if domain == 'customer' %}'Unknown'
            {% elif domain == 'account' %}'Unknown'
            {% elif domain == 'transaction' %}'Unknown'
            {% else %}'Unknown'
            {% endif %}
        else
            case lower(trim({{ column_name }}))
                when 'completed' then 'Completed'
                when 'complete' then 'Completed'
                when 'success' then 'Completed'
                when 'successful' then 'Completed'
                when 'pending' then 'Pending'
                when 'in progress' then 'Pending'
                when 'processing' then 'Pending'
                when 'failed' then 'Failed'
                when 'failure' then 'Failed'
                when 'error' then 'Failed'
                when 'declined' then 'Failed'
                when 'fail' then 'Failed'
                when 'reversed' then 'Reversed'
                when 'reverse' then 'Reversed'
                when 'refunded' then 'Reversed'
                when 'active' then 'Active'
                when 'inactive' then 'Inactive'
                when 'closed' then 'Closed'
                when 'frozen' then 'Frozen'
                when 'open' then 'Open'
                when 'suspended' then 'Suspended'
                when 'blocked' then 'Blocked'
                when 'expired' then 'Expired'
                when 'cancelled' then 'Cancelled'
                when 'canceled' then 'Cancelled'
                when 'renovating' then 'Renovating'
                else initcap(trim({{ column_name }}))
            end
    end
{% endmacro %}
