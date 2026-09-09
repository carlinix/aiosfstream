import pytest
import reprlib
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp.client_exceptions import ClientError

from aiosfstream.auth import (
    AuthenticatorBase,
    PasswordAuthenticator,
    RefreshTokenAuthenticator,
    TOKEN_URL,
    SANDBOX_TOKEN_URL,
)
from aiosfstream.client import API_VERSION, COMETD_PATH, Client
from aiosfstream.exceptions import AuthenticationError


class Authenticator(AuthenticatorBase):
    async def _authenticate(self):
        return {}


@pytest.fixture
def authenticator():
    return Authenticator()


# ---------------------------------------------------------------------
#  AuthenticatorBase tests
# ---------------------------------------------------------------------

def test_init():
    jd, jl = object(), object()
    auth = Authenticator(json_dumps=jd, json_loads=jl)
    assert auth.json_dumps is jd
    assert auth.json_loads is jl


@pytest.mark.asyncio
async def test_outgoing_sets_header(authenticator):
    authenticator.token_type = "Bearer"
    authenticator.access_token = "token"
    headers = {}

    await authenticator.outgoing([], headers)
    assert headers["Authorization"] == "Bearer token"


@pytest.mark.asyncio
async def test_outgoing_without_auth_raises(authenticator):
    with pytest.raises(AuthenticationError, match="without authenticating"):
        await authenticator.outgoing([], {})


@pytest.mark.asyncio
async def test_authenticate_success(monkeypatch, authenticator):
    response = {
        "id": "id_url",
        "issued_at": "1278448832702",
        "instance_url": "https://yourInstance.salesforce.com/",
        "signature": "signature_value",
        "access_token": "token",
        "token_type": "Bearer",
    }
    status = HTTPStatus.OK
    authenticator._authenticate = AsyncMock(return_value=(status, response))

    await authenticator.authenticate()

    assert authenticator.id == response["id"]
    assert authenticator.issued_at == response["issued_at"]
    assert authenticator.instance_url == response["instance_url"]
    assert authenticator.signature == response["signature"]
    assert authenticator.access_token == response["access_token"]
    assert authenticator.token_type == response["token_type"]


@pytest.mark.asyncio
async def test_authenticate_non_ok_status_code(authenticator):
    response = {"access_token": "bad"}
    authenticator._authenticate = AsyncMock(return_value=(HTTPStatus.BAD_REQUEST, response))

    with pytest.raises(AuthenticationError, match="Authentication failed"):
        await authenticator.authenticate()

    assert authenticator.access_token is None
    assert authenticator.token_type is None


@pytest.mark.asyncio
async def test_authenticate_on_network_error(authenticator):
    authenticator._authenticate = AsyncMock(side_effect=ClientError())

    with pytest.raises(AuthenticationError, match="Network request failed"):
        await authenticator.authenticate()

    assert authenticator.access_token is None
    assert authenticator.token_type is None


@pytest.mark.asyncio
async def test_incoming_noop(authenticator):
    payload, headers = [], {}
    await authenticator.incoming(payload, headers)
    assert not payload
    assert not headers


def test_token_url_non_sandbox():
    assert Authenticator()._token_url == TOKEN_URL


def test_token_url_sandbox():
    assert Authenticator(sandbox=True)._token_url == SANDBOX_TOKEN_URL


# ---------------------------------------------------------------------
#  PasswordAuthenticator tests
# ---------------------------------------------------------------------

@pytest.fixture
def password_auth():
    return PasswordAuthenticator(
        consumer_key="id",
        consumer_secret="secret",
        username="username",
        password="password",
    )


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_password_authenticate(mock_session, password_auth):
    status = object()
    response_data = {"ok": True}
    response_obj = MagicMock()
    response_obj.json = AsyncMock(return_value=response_data)
    response_obj.status = status

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    session.post = AsyncMock(return_value=response_obj)
    mock_session.return_value = session

    result = await password_auth._authenticate()

    assert result == (status, response_data)
    mock_session.assert_called_with(json_serialize=password_auth.json_dumps)
    session.post.assert_awaited_with(
        password_auth._token_url,
        data={
            "grant_type": "password",
            "client_id": password_auth.client_id,
            "client_secret": password_auth.client_secret,
            "username": password_auth.username,
            "password": password_auth.password,
        },
    )
    response_obj.json.assert_awaited_with(loads=password_auth.json_loads)
    session.__aenter__.assert_awaited()
    session.__aexit__.assert_awaited()


def test_password_repr(password_auth):
    result = repr(password_auth)
    cls = type(password_auth).__name__
    a = password_auth
    assert result == (
        f"{cls}(consumer_key={reprlib.repr(a.client_id)},"
        f"consumer_secret={reprlib.repr(a.client_secret)}, "
        f"username={reprlib.repr(a.username)}, "
        f"password={reprlib.repr(a.password)})"
    )


# ---------------------------------------------------------------------
#  RefreshTokenAuthenticator tests
# ---------------------------------------------------------------------

@pytest.fixture
def refresh_auth():
    return RefreshTokenAuthenticator(
        consumer_key="id",
        consumer_secret="secret",
        refresh_token="refresh_token",
    )


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_refresh_token_authenticate(mock_session, refresh_auth):
    status = object()
    response_data = {"ok": True}
    response_obj = MagicMock()
    response_obj.json = AsyncMock(return_value=response_data)
    response_obj.status = status

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    session.post = AsyncMock(return_value=response_obj)
    mock_session.return_value = session

    result = await refresh_auth._authenticate()

    assert result == (status, response_data)
    mock_session.assert_called_with(json_serialize=refresh_auth.json_dumps)
    session.post.assert_awaited_with(
        refresh_auth._token_url,
        data={
            "grant_type": "refresh_token",
            "client_id": refresh_auth.client_id,
            "client_secret": refresh_auth.client_secret,
            "refresh_token": refresh_auth.refresh_token,
        },
    )
    response_obj.json.assert_awaited_with(loads=refresh_auth.json_loads)
    session.__aenter__.assert_awaited()
    session.__aexit__.assert_awaited()


def test_refresh_repr(refresh_auth):
    result = repr(refresh_auth)
    cls = type(refresh_auth).__name__
    a = refresh_auth
    assert result == (
        f"{cls}(consumer_key={reprlib.repr(a.client_id)},"
        f"consumer_secret={reprlib.repr(a.client_secret)}, "
        f"refresh_token={reprlib.repr(a.refresh_token)})"
    )


# ---------------------------------------------------------------------
#  CometD URL tests
# ---------------------------------------------------------------------

def test_api_version_matches_simple_salesforce_default():
    """Both Salesforce clients must target one API version.

    simple_salesforce.api.DEFAULT_API_VERSION is 59.0 on the 1.12.10 pin
    used alongside this library. The assertion is deliberately literal so
    that bumping one library without the other fails here, instead of
    silently splitting the integration across two API versions.
    """
    assert API_VERSION == "59.0"


def test_get_cometd_url():
    assert Client.get_cometd_url("https://mycompany.my.salesforce.com") == (
        "https://mycompany.my.salesforce.com/cometd/59.0"
    )


def test_get_cometd_url_uses_module_constants():
    url = Client.get_cometd_url("https://example.my.salesforce.com")
    assert url.endswith(f"/{COMETD_PATH}/{API_VERSION}")
