# Runbook: Kafka consumer lag

1. Open Kafbat at <http://localhost:8087> and find the group in the alert.
2. Check whether the consumer process is running and whether it is committing.
3. Compare `lab_kafka_consumer_lag` with the topic's produce rate. A constant
   lag is a slow consumer; a growing lag is a stopped consumer.
4. Scale consumers up to the partition count, or fix the slow transform.
