Review changed code for quality, reuse opportunities, and efficiency. Then fix any issues found.

## Checklist

1. **Code duplication**: Find repeated logic that should be extracted into shared functions or base classes.

2. **Type safety**: Ensure all function signatures have type hints. Verify Pydantic models are used for data validation at API boundaries.

3. **Error handling**: Check that errors are handled appropriately - no bare `except:`, no swallowed exceptions. Errors at system boundaries (API, file I/O, external services) should return meaningful messages.

4. **Naming consistency**: Verify variable/function/class names follow project conventions (snake_case for Python, camelCase for TypeScript).

5. **Dead code**: Remove unused imports, unreachable code, commented-out blocks, and unused variables.

6. **Complexity**: Flag functions longer than 50 lines or with cyclomatic complexity > 10. Suggest decomposition.

7. **Test coverage**: Verify new code has corresponding tests. Flag untested public functions.

8. **Async correctness**: Ensure async functions are properly awaited. No blocking calls inside async functions.

9. **Configuration**: Verify magic numbers and strings are extracted to config.py or constants.

10. **Import organization**: Ensure imports follow the pattern: stdlib -> third-party -> local, sorted alphabetically within groups.

Fix all issues found during the review.
