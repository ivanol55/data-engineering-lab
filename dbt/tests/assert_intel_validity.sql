-- A validity window that ends before it starts is a feed bug, not a query bug.
select *
from {{ ref('stg_threat_intel') }}
where valid_to is not null
  and valid_from > valid_to
