from fastapi.testclient import TestClient

from fastapi import FastAPI

from fastapi_mcp.auth.proxy import setup_oauth_fake_dynamic_register_endpoint


def test_fake_dynamic_registration_does_not_return_client_secret():
    app = FastAPI()
    setup_oauth_fake_dynamic_register_endpoint(
        app=app,
        client_id="test-client-id",
        client_secret="super-secret-value",
    )

    client = TestClient(app)
    response = client.post(
        "/oauth/register",
        json={
            "redirect_uris": ["https://client.example.com/callback"],
            "client_name": "Test Client",
            "token_endpoint_auth_method": "client_secret_post",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["client_id"] == "test-client-id"
    assert "client_secret" not in payload
    assert payload["token_endpoint_auth_method"] == "none"
