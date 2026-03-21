---
name: test
description: Run the test suite and report results. Fix any failing tests.
disable-model-invocation: false
allowed-tools: Read, Edit, Grep, Glob, Bash
---

Run tests related to changed files only.

## Step 1: Identify changed files

```bash
git diff --name-only HEAD && git diff --name-only --cached && git ls-files --others --exclude-standard
```

Collect all changed, staged, and untracked files from the output.

## Step 2: Determine which tests to run

- If any files under `backend/tests/` were changed, run those test files directly.
- For each changed source file under `backend/app/` (e.g. `backend/app/foo/bar.py`), look for a corresponding test file (e.g. `backend/tests/unit/test_bar.py` or `backend/tests/unit/foo/test_bar.py`). Use Glob to find matches.
- If no test files are found for any changed file, report "No relevant tests found for changed files" and skip.
- If changed files are only in `frontend/`, run `cd frontend && pnpm test` instead.

## Step 3: Run the tests

Run only the identified test files:

```bash
cd backend && uv run python -m pytest <test_files> -v --tb=short
```

If any tests fail, investigate the root cause and fix the issue. After fixing, re-run the tests to confirm they pass.

Report the final test results with pass/fail counts.
