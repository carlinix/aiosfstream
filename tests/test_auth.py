import reprlib
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.client_exceptions import ClientError

from aiosfstream.auth import (
    SANDBOX_TOKEN_URL,
    TOKEN_URL,
    AuthenticatorBase,
    ClientCredentialsAuthenticator,
    PasswordAuthenticator,
    RefreshTokenAuthenticator,
)
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
    authenticator._authenticate = AsyncMock(
        return_value=(HTTPStatus.BAD_REQUEST, response)
    )

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
#  ClientCredentialsAuthenticator tests
# ---------------------------------------------------------------------


@pytest.fixture
def client_credentials_auth():
    return ClientCredentialsAuthenticator(
        consumer_key="id",
        consumer_secret="secret",
        domain="mycompany.my",
    )


def test_client_credentials_init(client_credentials_auth):
    a = client_credentials_auth
    assert a.client_id == "id"
    assert a.client_secret == "secret"
    assert a.domain == "mycompany.my"
    assert a.access_token is None
    assert a.token_type is None
    assert a.instance_url is None


def test_client_credentials_token_url_uses_my_domain(client_credentials_auth):
    """The whole point of the override: never login/test.salesforce.com."""
    assert client_credentials_auth._token_url == (
        "https://mycompany.my.salesforce.com/services/oauth2/token"
    )
    assert client_credentials_auth._token_url != TOKEN_URL
    assert client_credentials_auth._token_url != SANDBOX_TOKEN_URL


def test_client_credentials_sandbox_domain_is_just_another_domain():
    """A sandbox is named by its own My Domain, not by a sandbox flag."""
    auth = ClientCredentialsAuthenticator(
        consumer_key="id",
        consumer_secret="secret",
        domain="mycompany--dev.sandbox.my",
    )
    assert auth._token_url == (
        "https://mycompany--dev.sandbox.my.salesforce.com/services/oauth2/token"
    )


@pytest.mark.parametrize("domain", ["", "   ", "/"])
def test_client_credentials_rejects_empty_domain(domain):
    with pytest.raises(ValueError, match="domain is required"):
        ClientCredentialsAuthenticator(
            consumer_key="id", consumer_secret="secret", domain=domain
        )


@pytest.mark.parametrize(
    "domain",
    [
        "https://mycompany.my.salesforce.com",
        "http://mycompany.my",
    ],
)
def test_client_credentials_rejects_url_domain(domain):
    with pytest.raises(ValueError, match="not a URL"):
        ClientCredentialsAuthenticator(
            consumer_key="id", consumer_secret="secret", domain=domain
        )


def test_client_credentials_rejects_salesforce_com_suffix():
    with pytest.raises(ValueError, match="salesforce.com"):
        ClientCredentialsAuthenticator(
            consumer_key="id",
            consumer_secret="secret",
            domain="mycompany.my.salesforce.com",
        )


@pytest.mark.parametrize("domain", ["login", "test"])
def test_client_credentials_rejects_login_and_test(domain):
    with pytest.raises(ValueError, match="My Domain"):
        ClientCredentialsAuthenticator(
            consumer_key="id", consumer_secret="secret", domain=domain
        )


def test_client_credentials_strips_trailing_slash():
    auth = ClientCredentialsAuthenticator(
        consumer_key="id", consumer_secret="secret", domain="  mycompany.my/ "
    )
    assert auth.domain == "mycompany.my"


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_client_credentials_authenticate(mock_session, client_credentials_auth):
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

    result = await client_credentials_auth._authenticate()

    assert result == (status, response_data)
    mock_session.assert_called_with(json_serialize=client_credentials_auth.json_dumps)
    session.post.assert_awaited_with(
        client_credentials_auth._token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_credentials_auth.client_id,
            "client_secret": client_credentials_auth.client_secret,
        },
    )
    session.__aenter__.assert_awaited()
    session.__aexit__.assert_awaited()


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_client_credentials_sends_no_user_credentials(
    mock_session, client_credentials_auth
):
    """No username/password may reach the wire; that flow is retired."""
    response_obj = MagicMock()
    response_obj.json = AsyncMock(return_value={})
    response_obj.status = HTTPStatus.OK

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    session.post = AsyncMock(return_value=response_obj)
    mock_session.return_value = session

    await client_credentials_auth._authenticate()

    sent = session.post.await_args.kwargs["data"]
    assert "username" not in sent
    assert "password" not in sent
    assert sent["grant_type"] == "client_credentials"


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_client_credentials_populates_instance_url(
    mock_session, client_credentials_auth
):
    """Client.open() builds the CometD URL from instance_url."""
    response_obj = MagicMock()
    response_obj.json = AsyncMock(
        return_value={
            "access_token": "token",
            "token_type": "Bearer",
            "instance_url": "https://mycompany.my.salesforce.com",
        }
    )
    response_obj.status = HTTPStatus.OK

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    session.post = AsyncMock(return_value=response_obj)
    mock_session.return_value = session

    await client_credentials_auth.authenticate()

    assert client_credentials_auth.access_token == "token"
    assert client_credentials_auth.token_type == "Bearer"
    assert client_credentials_auth.instance_url == (
        "https://mycompany.my.salesforce.com"
    )


def test_client_credentials_repr_hides_secret(client_credentials_auth):
    result = repr(client_credentials_auth)
    a = client_credentials_auth
    cls = type(a).__name__
    assert result == (
        f"{cls}(consumer_key={reprlib.repr(a.client_id)}, "
        f"consumer_secret={reprlib.repr(a.client_secret)}, "
        f"domain={reprlib.repr(a.domain)})"
    )
