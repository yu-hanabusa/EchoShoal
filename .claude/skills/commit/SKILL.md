---
name: commit
description: Run tests, security review, and commit after feature implementation. Use after completing a coding task.
disable-model-invocation: true
allowed-tools: Read, Grep, Bash, Edit
---

Commit the current changes after a feature implementation.

## Steps

1. Run `/test` to run tests related to changed files. Fix any failures before proceeding.

2. Run `/security-review` to check for hardcoded secrets or injection risks in changed files.

3. Run `/refactor` to review code quality of changed files.

4. Review the git diff to understand all changes:
   - `git status -u` (never use -uall)
   - `git diff --stat`

5. Stage only relevant files (avoid staging .env, credentials, or unrelated changes). Use specific file paths, not `git add -A`.

6. Write a commit message in Japanese following this project's convention:
   - First line: concise summary (e.g., "Phase N: 機能名")
   - Body: bullet points explaining what was done and why
   - End with: `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`

7. Report the commit hash and a summary of what was committed.

## Important

- Do NOT push to remote unless explicitly asked
- Do NOT commit .env files, credentials, or .claude/ memory files
- Do NOT amend previous commits unless asked
- If tests fail, fix the issue and create a NEW commit
