"""Authentication verifiers for the MCP server.

CompositeVerifier dispatches between API-key auth (internal agents)
and JWT auth (external OAuth clients) based on the token format.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from fastmcp.server.auth.providers.jwt import (
    AccessToken,
    JWTVerifier,
    TokenVerifier,
)


class CompositeVerifier(TokenVerifier):
    """Dispatches auth to either API-key or JWT verification.

    - If the Bearer token matches the configured internal API key,
      returns a service-account AccessToken immediately.
    - Otherwise, delegates to JWTVerifier for JWKS-based JWT validation.
    """

    def __init__(
        self,
        *,
        internal_api_key: str | None = None,
        jwks_uri: str,
        issuer: str,
        audience: str,
        resource_url: str = "",
        authorization_server: str = "",
    ):
        super().__init__()
        self._internal_api_key = internal_api_key
        self._jwt_verifier = JWTVerifier(
            jwks_uri=jwks_uri,
            issuer=issuer,
            audience=audience,
        )
        self._resource_url = resource_url
        self._authorization_server = authorization_server or issuer

    async def verify_token(self, token: str) -> AccessToken | None:
        # Fast path: internal API key
        if self._internal_api_key and token == self._internal_api_key:
            return AccessToken(
                token=token,
                client_id="internal-agent",
                scopes=["mcp:tools"],
            )

        # JWT path
        return await self._jwt_verifier.verify_token(token)

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        """Serve RFC 9728 protected resource metadata."""
        if not self._resource_url:
            return []

        resource_url = self._resource_url
        auth_server = self._authorization_server

        async def protected_resource_metadata(request: Request) -> JSONResponse:
            return JSONResponse({
                "resource": resource_url,
                "authorization_servers": [auth_server],
                "scopes_supported": ["mcp:tools"],
                "bearer_methods_supported": ["header"],
            })

        path = "/.well-known/oauth-protected-resource"
        if mcp_path:
            path = f"/.well-known/oauth-protected-resource{mcp_path}"

        return [Route(path, endpoint=protected_resource_metadata, methods=["GET"])]
