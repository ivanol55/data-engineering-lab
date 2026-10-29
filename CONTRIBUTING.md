# Contributing

This repository is a course, so the most useful contribution is a learner gap
that fails in a realistic way and a check that proves it.

## Branches

- `main` is the learner branch. Every `TODO(learner)` is in its wrong state and
  `make check M=<n>` is expected to fail.
- `solutions` is the reference branch. The same checks pass.

Do not merge solution values into `main`. When you add or change a module,
make the change on `main` first, then port the reference values to `solutions`.

## Before opening a pull request

```bash
make doctor
make up P=core
make check M=0
make down
```

For a module change, run the module check on both branches:

```bash
git checkout main
make check M=<n>          # must fail
git checkout solutions
make check M=<n>          # must pass
```

A check must test behaviour, not source text. Mutate data, rerun the pipeline,
and assert on the result. If a failure is loud and unrelated to the learner's
decision, fix the plumbing instead of weakening the check.

## Adding a module

1. Add `modules/NN-topic/{README.md,hints.md,drills.md,stretch.md,exercises/}`.
2. Put the learner decisions in a config file with `TODO(learner)` comments and
   a wrong but runnable default.
3. Add `checks/module_NN/test_module_NN.py`.
4. Add the profile and service to `compose.yaml` with a pinned image and a
   `mem_limit`.
5. Add the `make check M=NN` runner in the `Makefile`.
6. Add the reference values on `solutions` and confirm both branch outcomes.

## Style

- Python 3.12, type hints where they help, no hidden global state.
- Prefer standard-library and pinned dependencies over new services.
- Keep the lab offline: no cloud account, API key, or telemetry.
- Document a decision in `DECISIONS.md` when it is easy to get wrong later.
