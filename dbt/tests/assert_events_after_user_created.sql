-- An event cannot happen before the user existed. A join that loses the
-- timestamp constraint produces rows that look valid but are impossible.
select *
from {{ ref('fct_login_events') }}
where event_time < user_created_at
