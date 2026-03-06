from seekout_mcp_search.server import create_server
from seekout_mcp_search.config import Settings

settings = Settings()
mcp = create_server(settings)
mcp.run(
    transport="streamable-http",
    host="0.0.0.0",
    port=settings.mcp_port,
    stateless_http=False,
)
