{{ config(materialized='view') }}

with events as (
    select * from {{ ref('stg_login_events') }}
),

users as (
    select * from {{ ref('stg_users') }}
),

intel as (
    select * from {{ ref('stg_threat_intel') }}
),

joined as (
    select
        e.*,
        u.full_name,
        u.account_status,
        u.department,
        u.home_country,
        u.mfa_enabled,
        u.created_at as user_created_at,
        u.is_deleted as user_is_deleted,
        i.indicator as intel_indicator,
        i.threat_type as intel_threat_type,
        i.confidence as intel_confidence,
        i.severity as intel_severity,
        i.valid_from as intel_valid_from,
        i.valid_to as intel_valid_to,
        {% if var('intel_join_mode') == 'latest_valid' %}
        row_number() over (
            partition by e.event_id
            order by i.updated_at desc nulls last
        ) as intel_rank
        {% else %}
        1 as intel_rank
        {% endif %}
    from events e
    left join users u
        on e.user_id = u.user_id
    {% if var('intel_join_mode') == 'latest_valid' %}
    left join intel i
        on e.source_ip = i.indicator
       and cast(e.event_time as date) >= i.valid_from
       and (i.valid_to is null or cast(e.event_time as date) <= i.valid_to)
    {% else %}
    left join intel i
        on e.source_ip = i.indicator
    {% endif %}
)

select *
from joined
{% if var('intel_join_mode') == 'latest_valid' %}
where intel_rank = 1
{% endif %}
