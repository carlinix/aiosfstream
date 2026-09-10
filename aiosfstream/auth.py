"""Authenticator class implementations"""

import json
import reprlib
import time
from abc import abstractmethod
from http import HTTPStatus
from os import PathLike
from pathlib import Path

from aiocometd import AuthExtension
from aiocometd.typing_utils import Headers, JsonDumper, JsonLoader, JsonObject, Payload
from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientError

from aiosfstream.exceptions import AuthenticationError

try:
    import jwt
except ImportError:  # pragma: no cover
    jwt = None  # type: ignore[assignment]

TOKEN_URL = "https://login.salesforce.com/services/oauth2/token"
SANDBOX_TOKEN_URL = "https://test.salesforce.com/services/oauth2/token"
AUDIENCE_URL = "https://login.salesforce.com"
SANDBOX_AUDIENCE_URL = "https://test.salesforce.com"
JWT_BEARER_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"
JWT_ALGORITHM = "RS256"
#: Lifetime of a JWT assertion in seconds. The assertion is used once, right
#: after it is signed, so a short window costs nothing and limits the value of
#: a leaked assertion.
JWT_EXPIRATION = 180


class AuthenticatorBase(AuthExtension):
    """Abstract base class to serve as a base for implementing concrete
    authenticators"""

    def __init__(
        self,
        sandbox: bool = False,
        json_dumps: JsonDumper = json.dumps,
        json_loads: JsonLoader = json.loads,
    ) -> None:
        """
        :param sandbox: Marks whether the authentication has to be done \
        for a sandbox org or for a production org
        :param json_dumps: Function for JSON serialization, the default is \
        :func:`json.dumps`
        :param json_loads: Function for JSON deserialization, the default is \
        :func:`json.loads`
        """
        #: Marks whether the authentication has to be done for a sandbox org \
        #: or for a production org
        self._sandbox = sandbox
        #: Salesforce session ID that can be used with the web services API
        self.access_token: str | None = None
        #: Value is Bearer for all responses that include an access token
        self.token_type: str | None = None
        #: A URL indicating the instance of the user’s org
        self.instance_url: str | None = None
        #: Identity URL that can be used to both identify the user and query \
        #: for more information about the user
        self.id: str | None = None
        #: Base64-encoded HMAC-SHA256 signature signed with the consumer’s \
        #: private key containing the concatenated ID and issued_at. Use to \
        #: verify that the identity URL hasn’t changed since the server sent it
        self.signature: str | None = None
        #: Timestamp when the signature was created
        self.issued_at: str | None = None
        #: Function for JSON serialization
        self.json_dumps = json_dumps
        #: Function for JSON deserialization
        self.json_loads = json_loads

    @property
    def _token_url(self) -> str:
        """The URL that should be used for token requests"""
        if self._sandbox:
            return SANDBOX_TOKEN_URL
        return TOKEN_URL

    async def outgoing(self, payload: Payload, headers: Headers) -> None:
        """Process outgoing *payload* and *headers*

        Called just before a payload is sent to insert the ``Authorization`` \
        header value.

        :param payload: List of outgoing messages
        :param headers: Headers to send
        :raise AuthenticationError: If the value of :py:attr:`~token_type` or \
        :py:attr:`~access_token` is ``None``. In other words, it's raised if \
        the method is called without authenticating first.
        """
        if self.token_type is None or self.access_token is None:
            raise AuthenticationError(
                "Unknown token_type and access_token "
                "values. Method called without "
                "authenticating first."
            )
        headers["Authorization"] = self.token_type + " " + self.access_token

    async def incoming(self, payload: Payload, headers: Headers | None = None) -> None:
        pass

    async def authenticate(self) -> None:
        """Called on initialization and after a failed authentication attempt

        :raise AuthenticationError: If the server rejects the authentication \
        request or if a network failure occurs
        """
        try:
            status_code, response_data = await self._authenticate()
        except ClientError as error:
            raise AuthenticationError("Network request failed") from error

        if status_code != HTTPStatus.OK:
            self._clear_credentials()
            raise AuthenticationError("Authentication failed", response_data)

        self.__dict__.update(response_data)

    def _clear_credentials(self) -> None:
        """Discard the values obtained from a previous authentication

        Called when an authentication attempt fails, so that a stale session
        can't outlive it and keep getting signed into outgoing requests.
        """
        self.access_token = None
        self.token_type = None
        self.instance_url = None
        self.id = None
        self.signature = None
        self.issued_at = None

    @abstractmethod
    async def _authenticate(self) -> tuple[int, JsonObject]:
        """Authenticate the user

        :return: The status code and response data from the server's response
        :raise aiohttp.client_exceptions.ClientError: If a network failure \
        occurs
        """


class PasswordAuthenticator(AuthenticatorBase):
    """Authenticator for using the OAuth 2.0 Username-Password Flow"""

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        username: str,
        password: str,
        sandbox: bool = False,
        json_dumps: JsonDumper = json.dumps,
        json_loads: JsonLoader = json.loads,
    ) -> None:
        """
        :param consumer_key: Consumer key from the Salesforce connected \
        app definition
        :param consumer_secret: Consumer secret from the Salesforce \
        connected app definition
        :param username: Salesforce username
        :param password: Salesforce password
        :param sandbox: Marks whether the authentication has to be done \
        for a sandbox org or for a production org
        :param json_dumps: Function for JSON serialization, the default is \
        :func:`json.dumps`
        :param json_loads: Function for JSON deserialization, the default is \
        :func:`json.loads`
        """
        super().__init__(sandbox=sandbox, json_dumps=json_dumps, json_loads=json_loads)
        #: OAuth2 client id
        self.client_id = consumer_key
        #: OAuth2 client secret
        self.client_secret = consumer_secret
        #: Salesforce username
        self.username = username
        #: Salesforce password
        self.password = password

    def __repr__(self) -> str:
        """Formal string representation"""
        cls_name = type(self).__name__
        return (
            f"{cls_name}(consumer_key={reprlib.repr(self.client_id)},"
            f"consumer_secret={reprlib.repr(self.client_secret)}, "
            f"username={reprlib.repr(self.username)}, "
            f"password={reprlib.repr(self.password)})"
        )

    async def _authenticate(self) -> tuple[int, JsonObject]:
        async with ClientSession(json_serialize=self.json_dumps) as session:
            data = {
                "grant_type": "password",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": self.username,
                "password": self.password,
            }
            response = await session.post(self._token_url, data=data)
            response_data = await response.json(loads=self.json_loads)
            return response.status, response_data


class RefreshTokenAuthenticator(AuthenticatorBase):
    """Authenticator for using the OAuth 2.0 Refresh Token Flow"""

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        refresh_token: str,
        sandbox: bool = False,
        json_dumps: JsonDumper = json.dumps,
        json_loads: JsonLoader = json.loads,
    ) -> None:
        """
        :param consumer_key: Consumer key from the Salesforce connected \
        app definition
        :param consumer_secret: Consumer secret from the Salesforce \
        connected app definition
        :param refresh_token: A refresh token obtained from Salesforce \
        by using one of its authentication methods (for example with the \
        OAuth 2.0 Web Server Authentication Flow)
        :param sandbox: Marks whether the authentication has to be done \
        for a sandbox org or for a production org
        :param json_dumps: Function for JSON serialization, the default is \
        :func:`json.dumps`
        :param json_loads: Function for JSON deserialization, the default is \
        :func:`json.loads`
        """
        super().__init__(sandbox=sandbox, json_dumps=json_dumps, json_loads=json_loads)
        #: OAuth2 client id
        self.client_id = consumer_key
        #: OAuth2 client secret
        self.client_secret = consumer_secret
        #: Salesforce refresh token
        self.refresh_token = refresh_token

    def __repr__(self) -> str:
        """Formal string representation"""
        cls_name = type(self).__name__
        return (
            f"{cls_name}(consumer_key={reprlib.repr(self.client_id)},"
            f"consumer_secret={reprlib.repr(self.client_secret)}, "
            f"refresh_token={reprlib.repr(self.refresh_token)})"
        )

    async def _authenticate(self) -> tuple[int, JsonObject]:
        async with ClientSession(json_serialize=self.json_dumps) as session:
            data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
            }
            response = await session.post(self._token_url, data=data)
            response_data = await response.json(loads=self.json_loads)
            return response.status, response_data


class ClientCredentialsAuthenticator(AuthenticatorBase):
    """Authenticator for using the OAuth 2.0 Client Credentials Flow

    Unlike the username-password and refresh token flows, this flow sends no \
    user credentials. The user that the integration acts as is configured on \
    the Salesforce side, on the external client app or connected app.

    Salesforce only issues client credentials tokens from an org's My Domain \
    host, so *domain* is required, and ``login`` and ``test`` are rejected.
    """

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        domain: str,
        json_dumps: JsonDumper = json.dumps,
        json_loads: JsonLoader = json.loads,
    ) -> None:
        """
        :param consumer_key: Consumer key from the Salesforce external \
        client app or connected app definition
        :param consumer_secret: Consumer secret from the Salesforce \
        external client app or connected app definition
        :param domain: The org's My Domain name, without a scheme and \
        without the ``.salesforce.com`` suffix, such as ``mycompany.my``
        :param json_dumps: Function for JSON serialization, the default is \
        :func:`json.dumps`
        :param json_loads: Function for JSON deserialization, the default is \
        :func:`json.loads`
        :raise ValueError: If *domain* is empty, looks like a URL, carries \
        the ``.salesforce.com`` suffix, or is ``login`` or ``test``
        """
        super().__init__(json_dumps=json_dumps, json_loads=json_loads)
        #: OAuth2 client id
        self.client_id = consumer_key
        #: OAuth2 client secret
        self.client_secret = consumer_secret
        #: The org's My Domain name
        self.domain = self._validate_domain(domain)

    @staticmethod
    def _validate_domain(domain: str) -> str:
        """Check that *domain* can name a My Domain host

        The value is used to build the token URL, so a URL or a value with
        the ``.salesforce.com`` suffix would produce a malformed endpoint,
        and ``login``/``test`` would point at a host that does not serve
        this flow. Failing here gives a clearer error than a 404 later.

        :param domain: The domain value to check
        :return: The validated domain
        :raise ValueError: If the value cannot name a My Domain host
        """
        value = domain.strip().strip("/")
        if not value:
            raise ValueError("domain is required for the client credentials flow")
        if "://" in value:
            raise ValueError(
                f"domain must be a bare My Domain name, not a URL: {domain!r}"
            )
        if value.endswith(".salesforce.com"):
            raise ValueError(
                f"domain must not carry the .salesforce.com suffix: {domain!r}"
            )
        if value in ("login", "test"):
            raise ValueError(
                "the client credentials flow requires an "
                f"org's My Domain host, not {value!r}"
            )
        return value

    @property
    def _token_url(self) -> str:
        """The URL that should be used for token requests"""
        return f"https://{self.domain}.salesforce.com/services/oauth2/token"

    def __repr__(self) -> str:
        """Formal string representation"""
        cls_name = type(self).__name__
        return (
            f"{cls_name}(consumer_key={reprlib.repr(self.client_id)}, "
            f"consumer_secret={reprlib.repr(self.client_secret)}, "
            f"domain={reprlib.repr(self.domain)})"
        )

    async def _authenticate(self) -> tuple[int, JsonObject]:
        async with ClientSession(json_serialize=self.json_dumps) as session:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            response = await session.post(self._token_url, data=data)
            response_data = await response.json(loads=self.json_loads)
            return response.status, response_data


class JWTBearerAuthenticator(AuthenticatorBase):
    """Authenticator for using the OAuth 2.0 JWT Bearer Flow

    No password and no client secret ever reach the wire. The client proves \
    its identity by signing a short lived assertion with the private key \
    whose certificate is uploaded to the Salesforce app definition, and the \
    user named by *username* has to be pre-authorized for that app.

    Signing requires `PyJWT <https://pyjwt.readthedocs.io/>`_ with its \
    cryptography backend, which is not a hard dependency of this package. \
    Install it with the ``jwt`` extra::

        pip install aiosfstream[jwt]
    """

    def __init__(
        self,
        consumer_key: str,
        username: str,
        private_key: str | bytes | None = None,
        private_key_path: str | PathLike[str] | None = None,
        audience: str | None = None,
        expiration: int = JWT_EXPIRATION,
        sandbox: bool = False,
        json_dumps: JsonDumper = json.dumps,
        json_loads: JsonLoader = json.loads,
    ) -> None:
        """
        :param consumer_key: Consumer key from the Salesforce external \
        client app or connected app definition
        :param username: Salesforce username of the user that the \
        integration acts as
        :param private_key: The RSA private key in PEM format, matching the \
        certificate uploaded to the app definition. Mutually exclusive with \
        *private_key_path*
        :param private_key_path: Path of a file holding the RSA private key \
        in PEM format. The file is read on initialization. Mutually \
        exclusive with *private_key*
        :param audience: Value of the assertion's ``aud`` claim. The default \
        is :py:data:`AUDIENCE_URL`, or :py:data:`SANDBOX_AUDIENCE_URL` if \
        *sandbox* is ``True``. Pass the site's URL to authenticate against \
        an Experience Cloud site
        :param expiration: Lifetime of the assertion in seconds
        :param sandbox: Marks whether the authentication has to be done \
        for a sandbox org or for a production org
        :param json_dumps: Function for JSON serialization, the default is \
        :func:`json.dumps`
        :param json_loads: Function for JSON deserialization, the default is \
        :func:`json.loads`
        :raise ImportError: If PyJWT is not installed
        :raise ValueError: If neither or both of *private_key* and \
        *private_key_path* are given, or if *expiration* is not positive
        """
        if jwt is None:
            raise ImportError(
                "The JWT Bearer flow requires PyJWT with its cryptography "
                "backend. Install it with the 'jwt' extra: "
                "pip install aiosfstream[jwt]"
            )
        if (private_key is None) == (private_key_path is None):
            raise ValueError(
                "exactly one of private_key and private_key_path is required"
            )
        if expiration <= 0:
            raise ValueError(f"expiration must be positive, got {expiration!r}")

        super().__init__(sandbox=sandbox, json_dumps=json_dumps, json_loads=json_loads)
        #: OAuth2 client id
        self.client_id = consumer_key
        #: Salesforce username
        self.username = username
        #: The RSA private key in PEM format. Read eagerly from \
        #: *private_key_path*, so that a missing or unreadable key fails here \
        #: rather than on the first authentication attempt, and so that no \
        #: blocking file access happens while authenticating
        self.private_key: str | bytes = (
            private_key
            if private_key is not None
            else Path(private_key_path).read_bytes()  # type: ignore[arg-type]
        )
        #: Value of the assertion's ``aud`` claim
        self.audience = audience if audience is not None else self._default_audience
        #: Lifetime of the assertion in seconds
        self.expiration = expiration

    @property
    def _default_audience(self) -> str:
        """The audience matching the org that :py:attr:`~_token_url` points at"""
        if self._sandbox:
            return SANDBOX_AUDIENCE_URL
        return AUDIENCE_URL

    def __repr__(self) -> str:
        """Formal string representation

        The private key is omitted rather than shortened, since an
        abbreviated key would still disclose part of the secret.
        """
        cls_name = type(self).__name__
        return (
            f"{cls_name}(consumer_key={reprlib.repr(self.client_id)}, "
            f"username={reprlib.repr(self.username)}, "
            f"audience={reprlib.repr(self.audience)})"
        )

    def _create_assertion(self) -> str:
        """Create a signed JWT assertion for the token request

        :return: The encoded assertion
        """
        claims = {
            "iss": self.client_id,
            "sub": self.username,
            "aud": self.audience,
            "exp": int(time.time()) + self.expiration,
        }
        return jwt.encode(claims, self.private_key, algorithm=JWT_ALGORITHM)

    async def _authenticate(self) -> tuple[int, JsonObject]:
        async with ClientSession(json_serialize=self.json_dumps) as session:
            data = {
                "grant_type": JWT_BEARER_GRANT_TYPE,
                "assertion": self._create_assertion(),
            }
            response = await session.post(self._token_url, data=data)
            response_data = await response.json(loads=self.json_loads)
            return response.status, response_data
