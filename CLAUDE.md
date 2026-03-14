# EchoShoal

AI-powered IT labor market prediction simulator for Japan.
Agent-based simulation engine that predicts how the Japanese IT industry
(SIer, SES, freelance) will evolve based on scenario inputs.

## Tech Stack

- **Backend**: FastAPI (Python 3.13) with uv
- **Frontend**: React 18 + TypeScript + Vite with pnpm
- **Graph DB**: Neo4j Community Edition
- **Cache/Queue**: Redis
- **LLM (light)**: Ollama (qwen2.5:14b / gemma3:12b)
- **LLM (heavy)**: Claude API / OpenAI API
- **NLP**: GiNZA (spaCy) + SudachiPy
- **Testing**: pytest + pytest-asyncio + httpx

## Project Structure

```
EchoShoal/
├── backend/          # FastAPI application
│   ├── app/          # Application code
│   │   ├── api/      # API routes
│   │   ├── core/     # LLM, NLP, Graph clients
│   │   ├── simulation/  # Simulation engine
│   │   ├── prediction/  # Quantitative prediction
│   │   └── reports/     # Report generation
│   └── tests/        # Test suite (unit/integration/e2e)
├── frontend/         # React SPA
└── docker-compose.yml
```

## Development Commands

### Backend
```bash
cd backend
uv run pytest                    # Run all tests
uv run pytest tests/unit         # Run unit tests only
uv run pytest -x -v              # Stop on first failure, verbose
uv run python -m app.main        # Start dev server
```

### Frontend
```bash
cd frontend
pnpm dev                         # Start dev server
pnpm build                       # Production build
pnpm test                        # Run tests
```

### Infrastructure
```bash
docker compose up -d             # Start Neo4j + Redis
docker compose down              # Stop services
```

## Development Guidelines

- TDD: Write tests first, then implement
- All agent behavior decisions use Ollama (local LLM)
- Report generation and ontology design use Claude API
- Japanese NLP uses GiNZA (rule-based NER), not LLM
- Keep simulation constraints minimal to preserve emergent behavior

## Security Rules

- **NEVER** hardcode API keys, passwords, tokens, or secrets in source files
- All secrets must be loaded via environment variables through pydantic-settings (app/config.py)
- .env files are in .gitignore and must never be committed
- .env.example contains key names only, never real values
- After every feature implementation, run `/security-review` before committing
- Validate all user input with Pydantic models at API boundaries
- Sanitize user text before injecting into LLM prompts

## Slash Commands

- `/security-review` — Scan for hardcoded secrets, injection risks, and security vulnerabilities
- `/refactor` — Review code quality, duplication, type safety, and test coverage
- `/test` — Run the full test suite and fix any failures
