Review all changed or newly created files for security risks.

## Checklist

1. **Hardcoded secrets**: Search for API keys, passwords, tokens, or connection strings hardcoded in source files. Use `grep -rn` for patterns like `api_key =`, `password =`, `token =`, `secret =`, `Bearer `, `sk-`, `key-` across all non-.env files.

2. **Environment variables**: Verify all secrets are loaded via `pydantic-settings` (app/config.py) and environment variables, never from source code.

3. **.gitignore coverage**: Confirm `.env`, `.env.local`, and any files that might contain secrets are in `.gitignore`.

4. **.env.example safety**: Ensure `.env.example` contains only key names with empty values, no real credentials.

5. **Injection risks**: Check for SQL injection (raw Cypher queries in Neo4j), command injection (subprocess calls), XSS (unescaped user input in frontend), and path traversal (file upload handling).

6. **Input validation**: Verify all API endpoints validate input with Pydantic models. No raw `request.body` parsing.

7. **CORS configuration**: Ensure CORS is not set to `allow_origins=["*"]` in production config.

8. **Dependency vulnerabilities**: Run `uv pip audit` or check for known vulnerable packages.

9. **File upload safety**: If file uploads exist, verify file type validation, size limits, and safe storage paths.

10. **LLM prompt injection**: Check that user-provided text is not directly concatenated into system prompts without sanitization.

Report all findings with file paths and line numbers. Fix critical issues immediately.
