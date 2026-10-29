{{ config(
    materialized='incremental',
    incremental_strategy=var('fct_incremental_strategy'),
    unique_key=var('fct_unique_key')
) }}

with inputs as (
    select * from {{ ref('int_login_risk_inputs') }}
)

select
    event_id,
    event_time,
    cast(event_time as date) as event_date,
    user_id,
    email,
    session_id,
    source_ip,
    country,
    city,
    latitude,
    longitude,
    device_id,
    device_type,
    operating_system,
    browser,
    auth_method,
    mfa_used,
    outcome,
    failure_reason,
    risk_score,
    is_attack,
    attack_type,
    attack_id,
    generator_version,
    account_status,
    department,
    home_country,
    mfa_enabled,
    user_created_at,
    user_is_deleted,
    intel_indicator,
    intel_threat_type,
    intel_confidence,
    intel_severity,
    intel_valid_from,
    intel_valid_to,
    case when intel_indicator is not null then true else false end as intel_hit
from inputs
{% if is_incremental() %}
where event_time >= (
    select coalesce(
        max(event_time) - interval '{{ var("fct_late_window_days") }}' day,
        timestamp '1970-01-01 00:00:00 UTC'
    )
    from {{ this }}
)
{% endif %}
