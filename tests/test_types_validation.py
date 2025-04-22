import pytest
from pydantic import ValidationError
from fastapi import Depends

from fastapi_mcp.types import (
    OAuthMetadata,
    AuthConfig,
)


class TestOAuthMetadata:
    def test_non_empty_lists_validation(self):
        for field in [
            "scopes_supported",
            "response_types_supported",
            "grant_types_supported",
            "token_endpoint_auth_methods_supported",
            "code_challenge_methods_supported",
        ]:
            with pytest.raises(ValidationError, match=f"{field} cannot be empty"):
                OAuthMetadata(
                    issuer="https://example.com",
                    authorization_endpoint="https://example.com/auth",
                    token_endpoint="https://example.com/token",
                    **{field: []},
                )

    def test_authorization_endpoint_required_for_authorization_code(self):
        with pytest.raises(ValidationError) as exc_info:
            OAuthMetadata(
                issuer="https://example.com",
                token_endpoint="https://example.com/token",
                grant_types_supported=["authorization_code", "client_credentials"],
            )
        assert "authorization_endpoint is required when authorization_code grant type is supported" in str(
            exc_info.value
        )

        OAuthMetadata(
            issuer="https://example.com",
            token_endpoint="https://example.com/token",
            authorization_endpoint="https://example.com/auth",
            grant_types_supported=["client_credentials"],
        )

    def test_model_dump_excludes_none(self):
        metadata = OAuthMetadata(
            issuer="https://example.com",
            authorization_endpoint="https://example.com/auth",
            token_endpoint="https://example.com/token",
        )

        dumped = metadata.model_dump()

        assert "registration_endpoint" not in dumped


class TestAuthConfig:
    def test_required_fields_validation(self):
        with pytest.raises(
            ValidationError, match="at least one of 'issuer', 'custom_oauth_metadata' or 'dependencies' is required"
        ):
            AuthConfig()

        AuthConfig(issuer="https://example.com")

        AuthConfig(
            custom_oauth_metadata={
                "issuer": "https://example.com",
                "authorization_endpoint": "https://example.com/auth",
                "token_endpoint": "https://example.com/token",
            },
        )

        def dummy_dependency():
            pass

        AuthConfig(dependencies=[Depends(dummy_dependency)])

    def test_client_id_required_for_setup_proxies(self):
        with pytest.raises(ValidationError, match="'client_id' is required when 'setup_proxies' is True"):
            AuthConfig(
                issuer="https://example.com",
                setup_proxies=True,
            )

        AuthConfig(
            issuer="https://example.com",
            setup_proxies=True,
            client_id="test-client-id",
            client_secret="test-client-secret",
        )

    def test_client_secret_required_for_fake_registration(self):
        with pytest.raises(
            ValidationError, match="'client_secret' is required when 'setup_fake_dynamic_registration' is True"
        ):
            AuthConfig(
                issuer="https://example.com",
                setup_proxies=True,
                client_id="test-client-id",
                setup_fake_dynamic_registration=True,
            )

        AuthConfig(
            issuer="https://example.com",
            setup_proxies=True,
            client_id="test-client-id",
            client_secret="test-client-secret",
            setup_fake_dynamic_registration=True,
        )
