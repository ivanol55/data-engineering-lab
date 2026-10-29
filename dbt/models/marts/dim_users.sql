{{ config(materialized='table') }}

select
    user_id,
    email,
    full_name,
    role_id,
    account_status,
    department,
    home_country,
    home_city,
    mfa_enabled,
    created_at,
    updated_at,
    is_deleted,
    updated_at as valid_from,
    cast(null as timestamp(6) with time zone) as valid_to
from {{ ref('stg_users') }}
