with source as (
    select * from {{ source('raw', 'threat_intel') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by indicator, valid_from
            order by updated_at desc
        ) as row_number
    from source
)

select
    indicator,
    indicator_type,
    threat_type,
    confidence,
    severity,
    source,
    description,
    valid_from,
    valid_to,
    updated_at,
    generator_version,
    indicator || '|' || cast(valid_from as varchar) as intel_key
from ranked
where row_number = 1
