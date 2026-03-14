---
name: test
description: Run the test suite and report results. Fix any failing tests.
disable-model-invocation: false
allowed-tools: Read, Edit, Bash
---

Run the test suite and report results.

```bash
cd backend && uv run python -m pytest tests/unit/ -v --tb=short
```

If any tests fail, investigate the root cause and fix the issue. After fixing, re-run the tests to confirm they pass.

Report the final test results with pass/fail counts.
