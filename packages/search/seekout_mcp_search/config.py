from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "", "case_sensitive": False, "env_file": ".env"}

    # Server
    spot_env: str = "production"
    mcp_port: int = 8001

    # SeekOut Runtime API
    seekout_runtime_api_endpoint: str = "http://localhost:9000"
    seekout_runtime_api_key: str = ""

    # Auth — JWT (external clients)
    seekout_jwks_uri: str = ""
    seekout_oauth_issuer: str = ""
    seekout_mcp_audience: str = "seekout-mcp-server"
    seekout_mcp_resource_url: str = ""

    # Auth — API key (internal agents)
    mcp_internal_api_key: str = ""

    # Redis (required — used for result caching and rate limiting)
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 3600

    # Rate limiting
    rate_limit_daily: int = 1000
    rate_limit_per_second: int = 10

    # Query Store (for generating SeekOut app links)
    query_store_endpoint: str = "https://recruit-querystore-func-prod.azurewebsites.net/api/StoreQuery"
    query_store_api_key: str = ""
