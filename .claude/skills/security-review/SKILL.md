---
name: security-review
description: Scan changed or newly created files for hardcoded secrets, injection risks, and security vulnerabilities
disable-model-invocation: false
allowed-tools: Read, Grep, Glob, Bash
---

Review only changed or newly created files for security risks.

## Step 1: Identify changed files

```bash
git diff --name-only HEAD && git diff --name-only --cached && git ls-files --others --exclude-standard
```

Collect all changed, staged, and untracked files. Only these files are the review target. Ignore test files, documentation, and config files that cannot contain security issues.

## Step 2: Review each changed file against the checklist

For each changed file, check only the applicable items:

1. **Hardcoded secrets**: Search the changed files for API keys, passwords, tokens, or connection strings. Look for patterns like `api_key =`, `password =`, `token =`, `secret =`, `Bearer `, `sk-`, `key-`.

2. **Environment variables**: If a changed file uses secrets, verify they are loaded via `pydantic-settings` (app/config.py) and environment variables, never hardcoded.

3. **Injection risks**: In changed files, check for SQL injection (raw Cypher queries in Neo4j), command injection (subprocess calls), XSS (unescaped user input in frontend), and path traversal (file upload handling).

4. **Input validation**: If changed files include API endpoints, verify they validate input with Pydantic models. No raw `request.body` parsing.

5. **LLM prompt injection**: If changed files build LLM prompts, check that user-provided text is not directly concatenated into system prompts without sanitization.

Report all findings with file paths and line numbers. Fix critical issues immediately.
