from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "EchoShoal"
    debug: bool = True

    # LLM Settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    default_heavy_provider: str = "claude"  # "claude" or "openai"

    # e-Stat API
    estat_api_key: str = ""

    # Neo4j Settings
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # Redis Settings
    redis_url: str = "redis://localhost:6379"

    # Simulation Defaults
    max_rounds: int = 36
    default_rounds: int = 24
    agent_activation_rate: float = 0.7  # 各ラウンドでアクティブになるエージェントの割合
    max_actions_per_agent: int = 2
    max_llm_calls: int = 5000

    # Market Research
    market_research_enabled: bool = True
    market_research_timeout: int = 30  # seconds
    github_api_token: str = ""  # optional, raises rate limit

    # OASIS Integration
    oasis_platform: str = "reddit"  # "twitter" or "reddit"
    oasis_max_agents: int = 200
    oasis_rounds_per_step: int = 2  # 1ラウンドあたりのLLMアクション機会（多いほど議論が活発）
    oasis_message_window_size: int = 20  # 直近N件のメッセージのみ保持
    oasis_context_token_limit: int = 16384  # コンテキストウィンドウのトークン上限（qwen3:14b=32K対応）
    oasis_max_output_tokens: int = 512  # LLM出力トークン上限

    # Rate Limiting
    max_concurrent_simulations: int = 3
    rate_limit_per_minute: int = 10

    model_config = {"env_prefix": "ECHOSHOAL_", "env_file": ".env"}


settings = Settings()
