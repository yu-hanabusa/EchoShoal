from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "EchoShoal"
    debug: bool = True

    # LLM Settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    default_heavy_provider: str = "claude"  # "claude" or "openai"

    # Neo4j Settings
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # Redis Settings
    redis_url: str = "redis://localhost:6379"

    # Simulation Defaults
    max_rounds: int = 36
    default_rounds: int = 24
    agent_activation_rate: float = 0.4
    max_actions_per_agent: int = 2
    max_llm_calls: int = 5000

    # Rate Limiting
    max_concurrent_simulations: int = 3
    rate_limit_per_minute: int = 10

    model_config = {"env_prefix": "ECHOSHOAL_", "env_file": ".env"}


settings = Settings()
