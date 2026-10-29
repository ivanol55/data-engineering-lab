# Runbook: decision dependency errors

1. Check `/ready` on the API. It reports which dependency is down.
2. Check `lab_dependency_errors_total{dependency="postgres"}` and
   `{dependency="valkey"}` to identify the failing path.
3. Confirm the service is failing closed. A spike in `allow` during an outage
   is a security incident.
4. Restore the dependency. If it cannot be restored quickly, keep the service
   closed and page the owner.
