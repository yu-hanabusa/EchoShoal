---
name: refactor
description: Review changed code for quality, reuse opportunities, and efficiency. Then fix any issues found.
disable-model-invocation: false
allowed-tools: Read, Grep, Glob, Edit, Bash
---

Review changed code for quality, reuse opportunities, and efficiency. Then fix any issues found.

## Checklist

### Backend

1. **Dead code**: Search for unused imports (`Grep` for imported names that aren't used in the file). Remove unused functions, commented-out blocks, and variables that were made obsolete by changes.

2. **Stale references**: Search for references to deleted functions, constants, or classes. Check comments that mention removed code.

3. **Code duplication**: Find repeated logic that should be extracted into shared functions or base classes.

4. **Type safety**: Ensure all function signatures have type hints. Verify Pydantic models are used for data validation at API boundaries.

5. **Error handling**: Check that errors are handled appropriately - no bare `except:`, no swallowed exceptions. Errors at system boundaries should return meaningful messages.

6. **Naming consistency**: Verify variable/function/class names follow project conventions (snake_case for Python).

7. **Complexity**: Flag functions longer than 50 lines or with cyclomatic complexity > 10.

8. **Test coverage**: Verify new code has corresponding tests. Flag untested public functions.

9. **Async correctness**: Ensure async functions are properly awaited. No blocking calls inside async functions.

10. **Configuration**: Verify magic numbers and strings are extracted to config.py or constants.

11. **Import organization**: Ensure imports follow: stdlib -> third-party -> local, sorted alphabetically.

### Frontend

12. **Layout consistency**: Check that ALL pages use NavBar for navigation. Search for duplicate `<header>` elements or hardcoded "EchoShoal" text outside NavBar. Every page should use the shared layout.

13. **Style consistency**: Search for inline `style={{...}}` in components. All styling should use Tailwind CSS classes. Flag any file with more than 2 inline style usages.

14. **Type alignment**: Verify frontend TypeScript types match backend response shapes (check `api/types.ts` against actual API responses).

15. **Dead components**: Check if any component is imported but not rendered, or if any page is unreachable from the router.

Fix all issues found during the review.
