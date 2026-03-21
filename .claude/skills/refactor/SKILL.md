---
name: refactor
description: Review changed code for quality, reuse opportunities, and efficiency. Then fix any issues found.
disable-model-invocation: false
allowed-tools: Read, Grep, Glob, Edit, Bash
---

Review only changed files for quality, reuse opportunities, and efficiency. Then fix any issues found.

## Step 1: Identify changed files

```bash
git diff --name-only HEAD && git diff --name-only --cached && git ls-files --others --exclude-standard
```

Collect all changed, staged, and untracked files. Only these files are the review target.

## Step 2: Review each changed file against the applicable checklist items

### For changed Python files (backend/)

1. **Dead code**: In changed files, search for unused imports and remove them. Remove unused functions, commented-out blocks, and variables that were made obsolete by changes.

2. **Stale references**: In changed files, search for references to deleted functions, constants, or classes.

3. **Code duplication**: In changed files, find repeated logic that should be extracted into shared functions or base classes.

4. **Type safety**: In changed files, ensure all function signatures have type hints. Verify Pydantic models are used for data validation at API boundaries.

5. **Error handling**: In changed files, check that errors are handled appropriately - no bare `except:`, no swallowed exceptions.

6. **Complexity**: In changed files, flag functions longer than 50 lines or with cyclomatic complexity > 10.

7. **Test coverage**: Verify new/changed code has corresponding tests. Flag untested public functions.

8. **Async correctness**: In changed files, ensure async functions are properly awaited. No blocking calls inside async functions.

9. **Configuration**: In changed files, verify magic numbers and strings are extracted to config.py or constants.

### For changed TypeScript/TSX files (frontend/)

10. **Layout consistency**: In changed pages, check that they use NavBar for navigation.

11. **Style consistency**: In changed files, search for inline `style={{...}}`. All styling should use Tailwind CSS classes.

12. **Type alignment**: If `api/types.ts` was changed, verify frontend types match backend response shapes.

13. **Dead components**: In changed files, check if any imported component is not rendered.

Fix all issues found during the review.
