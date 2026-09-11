import reprlib
import time
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch
from xml.etree import ElementTree

import jwt
import pytest
from aiohttp.client_exceptions import ClientError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from aiosfstream.auth import (
    AUDIENCE_URL,
    JWT_ALGORITHM,
    JWT_BEARER_GRANT_TYPE,
    JWT_EXPIRATION,
    LOGIN_DOMAIN,
    SANDBOX_AUDIENCE_URL,
    SANDBOX_LOGIN_DOMAIN,
    SANDBOX_TOKEN_URL,
    SOAP_API_VERSION,
    TOKEN_URL,
    AuthenticatorBase,
    ClientCredentialsAuthenticator,
    JWTBearerAuthenticator,
    PasswordAuthenticator,
    RefreshTokenAuthenticator,
    SOAPAuthenticator,
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


# ---------------------------------------------------------------------
#  JWTBearerAuthenticator tests
# ---------------------------------------------------------------------

# Generated once: 2048 bit key generation is slow enough to notice when
# repeated for every test in this section.
PRIVATE_KEY_OBJECT = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_KEY = PRIVATE_KEY_OBJECT.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
PUBLIC_KEY = (
    PRIVATE_KEY_OBJECT.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)


def decode_assertion(assertion, audience=AUDIENCE_URL):
    return jwt.decode(
        assertion, PUBLIC_KEY, algorithms=[JWT_ALGORITHM], audience=audience
    )


def post_session(mock_session, response_data=None, status=HTTPStatus.OK):
    response_obj = MagicMock()
    response_obj.json = AsyncMock(return_value=response_data or {})
    response_obj.status = status

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    session.post = AsyncMock(return_value=response_obj)
    mock_session.return_value = session
    return session


@pytest.fixture
def jwt_auth():
    return JWTBearerAuthenticator(
        consumer_key="id",
        username="user@example.com",
        private_key=PRIVATE_KEY,
    )


def test_jwt_init(jwt_auth):
    assert jwt_auth.client_id == "id"
    assert jwt_auth.username == "user@example.com"
    assert jwt_auth.private_key == PRIVATE_KEY
    assert jwt_auth.audience == AUDIENCE_URL
    assert jwt_auth.expiration == JWT_EXPIRATION
    assert jwt_auth.access_token is None
    assert jwt_auth.token_type is None


def test_jwt_reads_private_key_from_path(tmp_path):
    key_file = tmp_path / "server.key"
    # write_bytes, not write_text: the latter would rewrite the line endings
    # on Windows, so the assertion below would compare CRLF against LF.
    key_file.write_bytes(PRIVATE_KEY.encode())

    auth = JWTBearerAuthenticator(
        consumer_key="id",
        username="user@example.com",
        private_key_path=key_file,
    )

    assert auth.private_key == PRIVATE_KEY.encode()
    assert decode_assertion(auth._create_assertion())["iss"] == "id"


def test_jwt_missing_key_path_fails_on_init(tmp_path):
    """A bad key path must not surface as an authentication failure later."""
    with pytest.raises(OSError):
        JWTBearerAuthenticator(
            consumer_key="id",
            username="user@example.com",
            private_key_path=tmp_path / "absent.key",
        )


def test_jwt_rejects_no_key():
    with pytest.raises(ValueError, match="exactly one of private_key"):
        JWTBearerAuthenticator(consumer_key="id", username="user@example.com")


def test_jwt_rejects_both_keys(tmp_path):
    with pytest.raises(ValueError, match="exactly one of private_key"):
        JWTBearerAuthenticator(
            consumer_key="id",
            username="user@example.com",
            private_key=PRIVATE_KEY,
            private_key_path=tmp_path / "server.key",
        )


@pytest.mark.parametrize("expiration", [0, -1])
def test_jwt_rejects_non_positive_expiration(expiration):
    with pytest.raises(ValueError, match="must be positive"):
        JWTBearerAuthenticator(
            consumer_key="id",
            username="user@example.com",
            private_key=PRIVATE_KEY,
            expiration=expiration,
        )


def test_jwt_without_pyjwt_installed():
    with (
        patch("aiosfstream.auth.jwt", None),
        pytest.raises(ImportError, match=r"aiosfstream\[jwt\]"),
    ):
        JWTBearerAuthenticator(
            consumer_key="id",
            username="user@example.com",
            private_key=PRIVATE_KEY,
        )


def test_jwt_audience_defaults_to_production():
    auth = JWTBearerAuthenticator(
        consumer_key="id", username="user@example.com", private_key=PRIVATE_KEY
    )
    assert auth.audience == AUDIENCE_URL
    assert auth._token_url == TOKEN_URL


def test_jwt_audience_follows_sandbox_flag():
    """The aud claim and the token endpoint must name the same org."""
    auth = JWTBearerAuthenticator(
        consumer_key="id",
        username="user@example.com",
        private_key=PRIVATE_KEY,
        sandbox=True,
    )
    assert auth.audience == SANDBOX_AUDIENCE_URL
    assert auth._token_url == SANDBOX_TOKEN_URL


def test_jwt_audience_override():
    """Experience Cloud sites are addressed by their own URL."""
    auth = JWTBearerAuthenticator(
        consumer_key="id",
        username="user@example.com",
        private_key=PRIVATE_KEY,
        audience="https://site.force.com/customers",
    )
    assert auth.audience == "https://site.force.com/customers"


def test_jwt_assertion_claims(jwt_auth):
    before = int(time.time())

    claims = decode_assertion(jwt_auth._create_assertion())

    assert claims["iss"] == "id"
    assert claims["sub"] == "user@example.com"
    assert claims["aud"] == AUDIENCE_URL
    assert before + JWT_EXPIRATION <= claims["exp"] <= int(time.time()) + JWT_EXPIRATION


def test_jwt_assertion_is_signed_with_the_private_key(jwt_auth):
    other_key = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(
            jwt_auth._create_assertion(),
            other_key,
            algorithms=[JWT_ALGORITHM],
            audience=AUDIENCE_URL,
        )


def test_jwt_assertion_uses_a_custom_expiration():
    auth = JWTBearerAuthenticator(
        consumer_key="id",
        username="user@example.com",
        private_key=PRIVATE_KEY,
        expiration=30,
    )
    before = int(time.time())

    claims = decode_assertion(auth._create_assertion())

    assert before + 30 <= claims["exp"] <= int(time.time()) + 30


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_jwt_authenticate(mock_session, jwt_auth):
    response_data = {"ok": True}
    session = post_session(mock_session, response_data)

    status, data = await jwt_auth._authenticate()

    assert (status, data) == (HTTPStatus.OK, response_data)
    mock_session.assert_called_with(json_serialize=jwt_auth.json_dumps)
    session.post.assert_awaited_once()
    (url,) = session.post.await_args.args
    assert url == jwt_auth._token_url
    sent = session.post.await_args.kwargs["data"]
    assert sent["grant_type"] == JWT_BEARER_GRANT_TYPE
    assert decode_assertion(sent["assertion"])["iss"] == jwt_auth.client_id
    session.__aenter__.assert_awaited()
    session.__aexit__.assert_awaited()


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_jwt_sends_no_secret_and_no_password(mock_session, jwt_auth):
    """The point of the flow: only a signed assertion goes over the wire."""
    session = post_session(mock_session)

    await jwt_auth._authenticate()

    sent = session.post.await_args.kwargs["data"]
    assert set(sent) == {"grant_type", "assertion"}
    assert PRIVATE_KEY not in sent["assertion"]


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_jwt_signs_a_fresh_assertion_per_attempt(mock_session, jwt_auth):
    """A re-authentication after an expired token must not replay the old one."""
    session = post_session(mock_session)

    await jwt_auth._authenticate()
    first = session.post.await_args.kwargs["data"]["assertion"]
    jwt_auth.expiration += 1
    await jwt_auth._authenticate()
    second = session.post.await_args.kwargs["data"]["assertion"]

    assert first != second


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_jwt_populates_instance_url(mock_session, jwt_auth):
    """Client.open() builds the CometD URL from instance_url."""
    post_session(
        mock_session,
        {
            "access_token": "token",
            "token_type": "Bearer",
            "instance_url": "https://mycompany.my.salesforce.com",
            "id": "id_url",
            "scope": "api",
        },
    )

    await jwt_auth.authenticate()

    assert jwt_auth.access_token == "token"
    assert jwt_auth.token_type == "Bearer"
    assert jwt_auth.instance_url == "https://mycompany.my.salesforce.com"

    headers = {}
    await jwt_auth.outgoing([], headers)
    assert headers["Authorization"] == "Bearer token"


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_jwt_authentication_failure(mock_session, jwt_auth):
    post_session(
        mock_session,
        {"error": "invalid_grant", "error_description": "user hasn't approved"},
        status=HTTPStatus.BAD_REQUEST,
    )

    with pytest.raises(AuthenticationError, match="Authentication failed"):
        await jwt_auth.authenticate()

    assert jwt_auth.access_token is None
    assert jwt_auth.token_type is None


def test_jwt_repr_hides_the_private_key(jwt_auth):
    result = repr(jwt_auth)
    cls = type(jwt_auth).__name__

    assert result == (
        f"{cls}(consumer_key={reprlib.repr(jwt_auth.client_id)}, "
        f"username={reprlib.repr(jwt_auth.username)}, "
        f"audience={reprlib.repr(jwt_auth.audience)})"
    )
    assert "PRIVATE KEY" not in result
    assert PRIVATE_KEY.splitlines()[1][:16] not in result


# ---------------------------------------------------------------------
#  SOAPAuthenticator tests
# ---------------------------------------------------------------------

LOGIN_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns="urn:partner.soap.sforce.com"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body>
    <loginResponse>
      <result>
        <metadataServerUrl>https://mycompany.my.salesforce.com/services/Soap/m/59.0/00D0EAA</metadataServerUrl>
        <passwordExpired>false</passwordExpired>
        <sandbox>false</sandbox>
        <serverUrl>https://mycompany.my.salesforce.com/services/Soap/u/59.0/00D0EAA</serverUrl>
        <sessionId>00D000000000000!AQ4AQExample</sessionId>
        <userId>005000000000000AAA</userId>
      </result>
    </loginResponse>
  </soapenv:Body>
</soapenv:Envelope>"""

LOGIN_FAULT = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:sf="urn:fault.partner.soap.sforce.com"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body>
    <soapenv:Fault>
      <faultcode>sf:INVALID_LOGIN</faultcode>
      <faultstring>INVALID_LOGIN: Invalid username, password,
        security token; or user locked out.</faultstring>
      <detail>
        <sf:LoginFault xsi:type="sf:LoginFault">
          <sf:exceptionCode>INVALID_LOGIN</sf:exceptionCode>
          <sf:exceptionMessage>Invalid username, password,
            security token; or user locked out.</sf:exceptionMessage>
        </sf:LoginFault>
      </detail>
    </soapenv:Fault>
  </soapenv:Body>
</soapenv:Envelope>"""


def soap_session(mock_session, body=LOGIN_RESPONSE, status=HTTPStatus.OK):
    response_obj = MagicMock()
    response_obj.text = AsyncMock(return_value=body)
    response_obj.status = status

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    session.post = AsyncMock(return_value=response_obj)
    mock_session.return_value = session
    return session


@pytest.fixture
def soap_auth():
    return SOAPAuthenticator(username="user@acme.com", password="password")


def test_soap_init(soap_auth):
    assert soap_auth.username == "user@acme.com"
    assert soap_auth.password == "password"
    assert soap_auth.security_token == ""
    assert soap_auth.domain == LOGIN_DOMAIN
    assert soap_auth.access_token is None


def test_soap_login_url(soap_auth):
    assert soap_auth._token_url == (
        f"https://login.salesforce.com/services/Soap/u/{SOAP_API_VERSION}"
    )


def test_soap_sandbox_login_url():
    auth = SOAPAuthenticator(username="user@acme.com.uat", password="p", sandbox=True)
    assert auth.domain == SANDBOX_LOGIN_DOMAIN
    assert auth._token_url == (
        f"https://test.salesforce.com/services/Soap/u/{SOAP_API_VERSION}"
    )


def test_soap_explicit_domain_wins_over_sandbox():
    auth = SOAPAuthenticator(
        username="user@acme.com",
        password="p",
        domain="mycompany.my",
        sandbox=True,
    )
    assert auth._token_url == (
        f"https://mycompany.my.salesforce.com/services/Soap/u/{SOAP_API_VERSION}"
    )


def test_soap_strips_trailing_slash():
    auth = SOAPAuthenticator(
        username="user@acme.com", password="p", domain="  mycompany.my/ "
    )
    assert auth.domain == "mycompany.my"


@pytest.mark.parametrize("domain", ["", "   ", "/"])
def test_soap_rejects_empty_domain(domain):
    with pytest.raises(ValueError, match="must not be empty"):
        SOAPAuthenticator(username="u", password="p", domain=domain)


def test_soap_rejects_url_domain():
    with pytest.raises(ValueError, match="not a URL"):
        SOAPAuthenticator(
            username="u", password="p", domain="https://mycompany.my.salesforce.com"
        )


def test_soap_rejects_salesforce_com_suffix():
    with pytest.raises(ValueError, match="salesforce.com"):
        SOAPAuthenticator(
            username="u", password="p", domain="mycompany.my.salesforce.com"
        )


def test_soap_envelope_appends_the_security_token(soap_auth):
    soap_auth.security_token = "XyZ123"

    envelope = soap_auth._create_envelope()

    assert "<n1:password>passwordXyZ123</n1:password>" in envelope
    assert "<n1:username>user@acme.com</n1:username>" in envelope


def test_soap_envelope_escapes_credentials():
    """A password holding & or < would otherwise produce malformed XML."""
    auth = SOAPAuthenticator(
        username="a&b@acme.com", password="p<a>ss&", security_token="t&t"
    )

    envelope = auth._create_envelope()

    assert "<n1:username>a&amp;b@acme.com</n1:username>" in envelope
    assert "<n1:password>p&lt;a&gt;ss&amp;t&amp;t</n1:password>" in envelope
    ElementTree.fromstring(envelope)


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_soap_authenticate_sends_the_envelope(mock_session, soap_auth):
    session = soap_session(mock_session)

    status, data = await soap_auth._authenticate()

    assert status == HTTPStatus.OK
    assert data["access_token"] == "00D000000000000!AQ4AQExample"
    (url,) = session.post.await_args.args
    assert url == soap_auth._token_url
    assert (
        session.post.await_args.kwargs["data"] == soap_auth._create_envelope().encode()
    )
    headers = session.post.await_args.kwargs["headers"]
    assert headers["SOAPAction"] == "login"
    assert headers["Content-Type"] == "text/xml; charset=UTF-8"
    session.__aenter__.assert_awaited()
    session.__aexit__.assert_awaited()


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_soap_populates_the_session(mock_session, soap_auth):
    """instance_url is the origin of serverUrl, not the whole endpoint."""
    soap_session(mock_session)

    await soap_auth.authenticate()

    assert soap_auth.access_token == "00D000000000000!AQ4AQExample"
    assert soap_auth.token_type == "Bearer"
    assert soap_auth.instance_url == "https://mycompany.my.salesforce.com"

    headers = {}
    await soap_auth.outgoing([], headers)
    assert headers["Authorization"] == "Bearer 00D000000000000!AQ4AQExample"


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_soap_translates_a_fault(mock_session, soap_auth):
    soap_session(
        mock_session, body=LOGIN_FAULT, status=HTTPStatus.INTERNAL_SERVER_ERROR
    )

    status, data = await soap_auth._authenticate()

    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert data["error"] == "INVALID_LOGIN"
    assert "Invalid username" in data["error_description"]


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_soap_fault_raises_and_clears_the_session(mock_session, soap_auth):
    soap_auth.access_token = "stale"
    soap_auth.token_type = "Bearer"
    soap_session(
        mock_session, body=LOGIN_FAULT, status=HTTPStatus.INTERNAL_SERVER_ERROR
    )

    with pytest.raises(AuthenticationError, match="Authentication failed"):
        await soap_auth.authenticate()

    assert soap_auth.access_token is None
    assert soap_auth.token_type is None
    assert soap_auth.instance_url is None


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_soap_fault_without_detail_falls_back_to_faultstring(
    mock_session, soap_auth
):
    body = (
        "<soapenv:Envelope xmlns:soapenv="
        '"http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
        "<soapenv:Fault><faultcode>soapenv:Client</faultcode>"
        "<faultstring>content type not allowed</faultstring>"
        "</soapenv:Fault></soapenv:Body></soapenv:Envelope>"
    )
    soap_session(mock_session, body=body, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    _, data = await soap_auth._authenticate()

    assert data["error"] == "unknown_error"
    assert data["error_description"] == "content type not allowed"


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_soap_ok_without_a_session_clears_and_raises(mock_session, soap_auth):
    """A 200 that carries no sessionId must not leave a stale session behind."""
    soap_auth.access_token = "stale"
    soap_auth.token_type = "Bearer"
    body = (
        "<soapenv:Envelope xmlns:soapenv="
        '"http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
        "<loginResponse><result/></loginResponse>"
        "</soapenv:Body></soapenv:Envelope>"
    )
    soap_session(mock_session, body=body)

    with pytest.raises(AuthenticationError, match="carries no session"):
        await soap_auth.authenticate()

    assert soap_auth.access_token is None
    assert soap_auth.token_type is None


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_soap_non_xml_response_clears_and_raises(mock_session, soap_auth):
    soap_auth.access_token = "stale"
    # An HTML error page from a proxy in front of the org: not well formed,
    # because of the unclosed <br>.
    soap_session(mock_session, body="<html><body>502 Bad Gateway<br></body></html>")

    with pytest.raises(AuthenticationError, match="not valid XML"):
        await soap_auth.authenticate()

    assert soap_auth.access_token is None


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_soap_network_error(mock_session, soap_auth):
    mock_session.side_effect = ClientError()

    with pytest.raises(AuthenticationError, match="Network request failed"):
        await soap_auth.authenticate()


def test_soap_repr_hides_the_password():
    auth = SOAPAuthenticator(
        username="user@acme.com", password="s3cret", security_token="XyZ123"
    )

    result = repr(auth)

    assert result == (
        f"SOAPAuthenticator(username={reprlib.repr(auth.username)}, "
        f"domain={reprlib.repr(auth.domain)})"
    )
    assert "s3cret" not in result
    assert "XyZ123" not in result


@pytest.mark.asyncio
@patch("aiosfstream.auth.ClientSession")
async def test_soap_keeps_api_inside_the_host(mock_session, soap_auth):
    """simple-salesforce's unanchored "-api" strip would corrupt this host."""
    soap_session(mock_session, body=LOGIN_RESPONSE.replace("mycompany", "acme-apidev"))

    await soap_auth.authenticate()

    assert soap_auth.instance_url == "https://acme-apidev.my.salesforce.com"
