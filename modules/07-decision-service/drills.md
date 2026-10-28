# Module 7 — Decision service — drills

Break-it exercises. There is no answer key on purpose: the point is to
see the failure, then explain which invariant broke.

1. Change the exception path to return `allow` and stop Valkey. Send a request and inspect the response and the log.
2. Set the feature TTL to 30 days. Update an indicator and confirm the service still blocks the old value.
3. Move the default allow rule to the top. Run the fixture suite and count how many blocks disappear.

Record what you observed, not just what you expected. A drill you
cannot reproduce is not finished.
