# Module 2 — dbt modelling — stretch

Open-ended extensions. They are deliberately larger than one sitting and
have no reference solution.

1. Implement SCD2 for `dim_users` with `valid_from`/`valid_to` and join facts on event time. Prove that a user who moves country does not rewrite history.
2. Add dbt exposures for the decision service and the ML training set, so lineage shows who depends on `fct_login_events`.
3. Add a singular test that fails when an event predates its user's `created_at`.

Write down the trade-off you chose and the case where it would be the
wrong choice.
