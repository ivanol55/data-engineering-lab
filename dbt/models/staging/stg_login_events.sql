with source as (
    select * from {{ source('raw', 'login_events') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by event_id
            order by event_time desc
        ) as row_number
    from source
)

select
    event_id,
    event_time,
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
    generator_version
from ranked
where row_number = 1
