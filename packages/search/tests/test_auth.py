import pytest
from unittest.mock import AsyncMock, patch

from seekout_mcp_search.auth import CompositeVerifier
from fastmcp.server.auth.providers.jwt import AccessToken


@pytest.fixture
def verifier():
    """CompositeVerifier with a known API key and dummy JWKS config."""
    return CompositeVerifier(
        internal_api_key="test-api-key-abc",
        jwks_uri="https://example.com/.well-known/jwks.json",
        issuer="https://example.com",
        audience="test-audience",
        resource_url="https://mcp.example.com/mcp",
        authorization_server="https://example.com",
    )


@pytest.fixture
def verifier_no_api_key():
    """CompositeVerifier without an internal API key."""
    return CompositeVerifier(
        internal_api_key=None,
        jwks_uri="https://example.com/.well-known/jwks.json",
        issuer="https://example.com",
        audience="test-audience",
    )


class TestApiKeyAuth:
    @pytest.mark.asyncio
    async def test_valid_api_key_returns_access_token(self, verifier):
        result = await verifier.verify_token("test-api-key-abc")

        assert result is not None
        assert result.client_id == "internal-agent"
        assert result.scopes == ["mcp:tools"]

    @pytest.mark.asyncio
    async def test_wrong_api_key_delegates_to_jwt(self, verifier):
        with patch.object(
            verifier._jwt_verifier, "verify_token", new_callable=AsyncMock
        ) as mock_jwt:
            mock_jwt.return_value = None
            result = await verifier.verify_token("wrong-key")

            mock_jwt.assert_called_once_with("wrong-key")
            assert result is None

    @pytest.mark.asyncio
    async def test_no_api_key_configured_delegates_to_jwt(self, verifier_no_api_key):
        with patch.object(
            verifier_no_api_key._jwt_verifier, "verify_token", new_callable=AsyncMock
        ) as mock_jwt:
            mock_jwt.return_value = None
            await verifier_no_api_key.verify_token("any-token")

            mock_jwt.assert_called_once_with("any-token")


class TestJwtDelegation:
    @pytest.mark.asyncio
    async def test_jwt_token_delegated_to_jwt_verifier(self, verifier):
        fake_access = AccessToken(
            token="jwt-token",
            client_id="user@example.com",
            scopes=["mcp:tools"],
        )
        with patch.object(
            verifier._jwt_verifier, "verify_token", new_callable=AsyncMock
        ) as mock_jwt:
            mock_jwt.return_value = fake_access
            result = await verifier.verify_token("jwt-token")

            assert result is not None
            assert result.client_id == "user@example.com"

    @pytest.mark.asyncio
    async def test_invalid_jwt_returns_none(self, verifier):
        with patch.object(
            verifier._jwt_verifier, "verify_token", new_callable=AsyncMock
        ) as mock_jwt:
            mock_jwt.return_value = None
            result = await verifier.verify_token("invalid.jwt.token")

            assert result is None


class TestProtectedResourceMetadata:
    def test_routes_returned_when_resource_url_set(self, verifier):
        routes = verifier.get_routes(mcp_path="/mcp")

        assert len(routes) == 1
        assert routes[0].path == "/.well-known/oauth-protected-resource/mcp"

    def test_no_routes_when_resource_url_empty(self, verifier_no_api_key):
        routes = verifier_no_api_key.get_routes(mcp_path="/mcp")

        assert len(routes) == 0

    def test_routes_without_mcp_path(self, verifier):
        routes = verifier.get_routes(mcp_path=None)

        assert len(routes) == 1
        assert routes[0].path == "/.well-known/oauth-protected-resource"
