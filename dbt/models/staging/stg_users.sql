with source as (
    select * from {{ source('raw', 'users') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by user_id
            order by updated_at desc
        ) as row_number
    from source
)

select
    user_id,
    email,
    full_name,
    role_id,
    account_status,
    department,
    home_country,
    home_city,
    home_lat,
    home_lon,
    mfa_enabled,
    created_at,
    updated_at,
    last_login_at,
    deleted_at,
    coalesce(is_deleted, deleted_at is not null) as is_deleted
from ranked
where row_number = 1
