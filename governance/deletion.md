# Deletion procedure

TODO(learner): a user deletion in Postgres is not a deletion in the lakehouse,
the log, the cache, or the model store. Write the procedure, then exercise it
on a test user.

The check looks for these sections:

- scope: which identifiers and which systems are in scope;
- procedure: ordered steps for Postgres, Iceberg/S3, Kafka, Valkey and MLflow;
- verification: how you prove no copy remains;
- retention: which copies are kept for legal or audit reasons and for how long.
