# EchoShoal

AI-powered Service Business Impact Simulator.
Agent-based simulation engine that predicts whether a specific service
will succeed and what impact it will have on the market, using
stakeholder-driven "what-if" scenario analysis.

## Environment

- **OS**: Windows 11 native (WSL不要)
- **Python**: 3.13 with uv
- **Node**: v22+ with pnpm
- **Docker**: Docker Desktop for Windows (Neo4j + Redis)
- **Ollama**: Windows native (qwen2.5:14b)

## Tech Stack

- **Backend**: FastAPI (Python 3.13) with uv
- **Frontend**: React 19 + TypeScript + Vite with pnpm
- **Graph DB**: Neo4j Community Edition
- **Cache/Queue**: Redis
- **LLM (light)**: Ollama (qwen2.5:14b)
- **LLM (heavy)**: Claude API / OpenAI API
- **NLP**: ルールベース辞書 + LLM
- **Testing**: pytest + pytest-asyncio + httpx

## Project Structure

```
EchoShoal/
├── backend/          # FastAPI application
│   ├── app/          # Application code
│   │   ├── api/      # API routes
│   │   ├── core/     # LLM, NLP, Graph clients
│   │   ├── simulation/  # Simulation engine
│   │   │   └── agents/  # 8 stakeholder agent types
│   │   ├── oasis/       # OASIS SNS simulation engine
│   │   ├── prediction/  # Quantitative prediction
│   │   ├── reports/     # Report generation
│   │   └── evaluation/  # Benchmark evaluation
│   └── tests/        # Test suite (unit/integration/e2e)
├── frontend/         # React SPA
└── docker-compose.yml
```

## Domain Model

### Stakeholder Types (Agents)
- **Enterprise** — large, medium, startup companies
- **Freelancer** — service as extension of contract work
- **IndieDevloper** — self-initiated products
- **Government** — regulations, subsidies
- **Investor/VC** — funding, market signals
- **Platformer** — AWS/Google/etc (sudden competitors)
- **Community** — industry groups, OSS communities
- **EndUser** — existing/potential/switching users

### Market Dimensions (tracked per round)
user_adoption, revenue_potential, tech_maturity, competitive_pressure,
regulatory_risk, market_awareness, ecosystem_health, funding_climate

### External Factors (environment, not agents)
Economic changes, technology trends, regulatory changes, social shifts, disasters

## Startup (Windows Native)

```bash
# 1. Infrastructure (Docker Desktop must be running)
docker compose up -d             # Start Neo4j + Redis

# 2. Backend (separate terminal)
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Frontend (separate terminal)
cd frontend
pnpm dev                         # localhost:5173

# Shutdown
docker compose down              # Stop Neo4j + Redis
```

## Development Commands

### Backend
```bash
cd backend
uv run pytest                    # Run all tests
uv run pytest tests/unit         # Run unit tests only
uv run pytest -x -v              # Stop on first failure, verbose
```

### Frontend
```bash
cd frontend
pnpm dev                         # Start dev server
pnpm build                       # Production build
pnpm test                        # Run tests
```

## Development Guidelines

- TDD: Write tests first, then implement
- All agent behavior decisions use Ollama (local LLM)
- Report generation and ontology design use Claude API
- Tech/policy NLP uses rule-based dictionaries; org extraction uses LLM
- Keep simulation constraints minimal to preserve emergent behavior

### Post-Implementation Workflow (MANDATORY)

After completing any feature implementation, you MUST run the following in order before reporting completion to the user:

1. `/test` — Run the full test suite. Fix any failures before proceeding.
2. `/security-review` — Scan for hardcoded secrets, injection risks, and vulnerabilities. Fix critical issues.
3. `/refactor` — Review code quality, duplication, and type safety. Fix issues found.

Only after all three pass with no critical issues, report the implementation as complete.
If the user asks to commit, use `/commit`.

## Security Rules

- **NEVER** hardcode API keys, passwords, tokens, or secrets in source files
- All secrets must be loaded via environment variables through pydantic-settings (app/config.py)
- .env files are in .gitignore and must never be committed
- .env.example contains key names only, never real values
- After every feature implementation, run `/security-review` before committing
- Validate all user input with Pydantic models at API boundaries
- Sanitize user text before injecting into LLM prompts

## Slash Commands

- `/test` — Run the full test suite and fix any failures
- `/security-review` — Scan for hardcoded secrets, injection risks, and security vulnerabilities
- `/refactor` — Review code quality, duplication, type safety, and test coverage
- `/commit` — Run test + security-review + refactor, then commit (manual invocation only)
