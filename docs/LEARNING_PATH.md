# How to use this course

This is a guided course, not an exam. You are not expected to invent the right
answer from a blank page. Each module teaches the idea first, shows you a
working example, and then asks you to change a small number of decisions and
prove the result with a check.

## Who it is for

You need to be comfortable opening a terminal and running commands. You do
**not** need prior experience with data warehouses, Kafka, Iceberg, dbt, Flink,
or machine learning. Every term is explained when it first appears, and the
full list is in [`GLOSSARY.md`](GLOSSARY.md).

If you can run `cd`, `ls`, `cat`, and `docker compose`, you can start.

## The learning loop

Use the same loop in every module:

1. **Read the idea.** Start with the module's “Before you start” section. It
   explains the problem in plain language.
2. **Predict.** Before running a command, write one sentence about what you
   expect to see. This is the most important habit in the course.
3. **Run the guided step.** Copy the command exactly. Read the output, not just
   the exit code.
4. **Explain it.** Say out loud what changed and why. If you cannot, reread the
   concept section or open the first hint.
5. **Make the decision.** Change the config value the module asks for. The
   reference answer is always shown; the point is to understand why it is
   correct, not to guess it.
6. **Run the check.** `make check M=<n>` proves the behaviour. A failure message
   is part of the lesson: read the assertion before changing anything.
7. **Do one drill.** Drills break the pipeline on purpose. They are where the
   idea becomes yours.

## What the branches mean

- `main` is the learner branch. The configs contain wrong but runnable values,
  so the checks fail.
- `solutions` is the reference branch. The same checks pass.

You can compare your work with the reference at any time:

```bash
git diff main..solutions -- <path>
```

Do not copy the whole solution branch and call it done. The value is in
predicting, running, and explaining each step.

## A suggested schedule

| Week | Modules | What you are learning |
|---|---|---|
| 1 | 0, 1 | The lab, Postgres, object storage, Iceberg, batch loading |
| 2 | 2, 3 | SQL modelling, grains, incremental models, orchestration |
| 3 | 4, 5 | Kafka, schemas, delivery guarantees, change data capture |
| 4 | 6, 7 | Event time, windows, state, decision services, fail modes |
| 5 | 8, 9 | Observability, governance, leakage, model promotion |

Each module is designed for one or two sittings. If a module takes much longer,
stop and reread its concept section; the guided steps are not meant to be a
race.

## Before your first module

```bash
cp .env.example .env
make up P=core
make doctor
```

`make doctor` checks Docker, free memory, ports, and the core services. It is
safe to run repeatedly.

If you are short on memory, stop other stacks first. The full lab idles around
5–6 GiB, and each module uses less than that.

## How to read a failing check

A check failure is not a verdict on you. It is a sentence about the data. Read
it in this order:

1. **The assertion message.** It usually names the invariant that broke, for
   example “a second build duplicated every fact row”.
2. **The expected and actual values.** They tell you which direction the bug
   goes.
3. **The module section named in the message.** Most messages point at the
   decision that caused the failure.
4. **The hint file.** Hints are progressive; open one at a time.

If the failure is a connection error, a missing image, or a container that
never becomes healthy, it is plumbing, not your decision. Run `make doctor` and
read the container logs.

## The five questions to ask about any pipeline

These questions return in every module:

1. **What is one row?** (grain)
2. **What happens if I run it twice?** (idempotency)
3. **What happens to late or out-of-order data?** (time)
4. **What happens when a dependency is down?** (failure mode)
5. **How would I prove it is correct?** (check)

If you can answer those five for a pipeline, you understand it better than most
people who can operate it.

## Getting unstuck

- **“Command not found.”** The tools run inside containers. Use the `make` or
  `docker compose run` command from the module, not a host install.
- **“Port already in use.”** Change the port in `.env`, or stop the other
  stack. `make doctor` lists conflicts.
- **“Container is unhealthy.”** Read `docker compose logs <service>`. The lab
  fails loudly on purpose; the first error is usually the real one.
- **“The check fails but my code looks right.”** Run the check twice. Some
  checks reset tables and reload data; a stale volume can hide the previous
  run.
- **“I do not understand the output.”** Query the table by hand with
  `make query Q='...'` and compare the row count with the check's expected
  value.

## A note on using AI

AI is useful for explaining a term, reviewing a decision you already made, or
helping you read an error. It is not useful as a substitute for running the
pipeline. Ask “why does this join fan out?” rather than “write the whole
module”. The course is designed so that the running system can tell you whether
an answer is right.
