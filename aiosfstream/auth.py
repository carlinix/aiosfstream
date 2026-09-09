"""Authenticatior class implementations"""
from abc import abstractmethod
from http import HTTPStatus
import reprlib
import json
from typing import Optional, Tuple

from aiocometd import AuthExtension
from aiocometd.typing_utils import JsonObject, JsonLoader, JsonDumper, Payload, \
    Headers
from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientError

from aiosfstream.exceptions import AuthenticationError


TOKEN_URL = "https://login.salesforce.com/services/oauth2/token"
SANDBOX_TOKEN_URL = "https://test.salesforce.com/services/oauth2/token"


# pylint: disable=too-many-instance-attributes

class AuthenticatorBase(AuthExtension):
    """Abstract base class to serve as a base for implementing concrete
    authenticators"""
    def __init__(self, sandbox: bool = False,
                 json_dumps: JsonDumper = json.dumps,
                 json_loads: JsonLoader = json.loads) -> None:
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
        self.access_token: Optional[str] = None
        #: Value is Bearer for all responses that include an access token
        self.token_type: Optional[str] = None
        #: A URL indicating the instance of the user’s org
        self.instance_url: Optional[str] = None
        #: Identity URL that can be used to both identify the user and query \
        #: for more information about the user
        self.id: Optional[str] = None  # pylint: disable=invalid-name
        #: Base64-encoded HMAC-SHA256 signature signed with the consumer’s \
        #: private key containing the concatenated ID and issued_at. Use to \
        #: verify that the identity URL hasn’t changed since the server sent it
        self.signature: Optional[str] = None
        #: Timestamp when the signature was created
        self.issued_at: Optional[str] = None
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
            raise AuthenticationError("Unknown token_type and access_token "
                                      "values. Method called without "
                                      "authenticating first.")
        headers["Authorization"] = self.token_type + " " + self.access_token

    async def incoming(self, payload: Payload,
                       headers: Optional[Headers] = None) -> None:
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
            self.access_token = None
            self.token_type = None
            self.instance_url = None
            self.id = None
            self.signature = None
            self.issued_at = None
            raise AuthenticationError("Authentication failed", response_data)

        self.__dict__.update(response_data)

    @abstractmethod
    async def _authenticate(self) -> Tuple[int, JsonObject]:
        """Authenticate the user

        :return: The status code and response data from the server's response
        :raise aiohttp.client_exceptions.ClientError: If a network failure \
        occurs
        """

# pylint: enable=too-many-instance-attributes
# pylint: disable=too-many-arguments


class PasswordAuthenticator(AuthenticatorBase):
    """Authenticator for using the OAuth 2.0 Username-Password Flow"""
    def __init__(self, consumer_key: str, consumer_secret: str,
                 username: str, password: str, sandbox: bool = False,
                 json_dumps: JsonDumper = json.dumps,
                 json_loads: JsonLoader = json.loads) -> None:
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
        super().__init__(sandbox=sandbox,
                         json_dumps=json_dumps,
                         json_loads=json_loads)
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
        return f"{cls_name}(consumer_key={reprlib.repr(self.client_id)}," \
               f"consumer_secret={reprlib.repr(self.client_secret)}, " \
               f"username={reprlib.repr(self.username)}, " \
               f"password={reprlib.repr(self.password)})"

    async def _authenticate(self) -> Tuple[int, JsonObject]:
        async with ClientSession(json_serialize=self.json_dumps) as session:
            data = {
                "grant_type": "password",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": self.username,
                "password": self.password
            }
            response = await session.post(self._token_url, data=data)
            response_data = await response.json(loads=self.json_loads)
            return response.status, response_data


class RefreshTokenAuthenticator(AuthenticatorBase):
    """Authenticator for using the OAuth 2.0 Refresh Token Flow"""
    def __init__(self, consumer_key: str, consumer_secret: str,
                 refresh_token: str, sandbox: bool = False,
                 json_dumps: JsonDumper = json.dumps,
                 json_loads: JsonLoader = json.loads) -> None:
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
        super().__init__(sandbox=sandbox,
                         json_dumps=json_dumps,
                         json_loads=json_loads)
        #: OAuth2 client id
        self.client_id = consumer_key
        #: OAuth2 client secret
        self.client_secret = consumer_secret
        #: Salesforce refresh token
        self.refresh_token = refresh_token

    def __repr__(self) -> str:
        """Formal string representation"""
        cls_name = type(self).__name__
        return f"{cls_name}(consumer_key={reprlib.repr(self.client_id)}," \
               f"consumer_secret={reprlib.repr(self.client_secret)}, " \
               f"refresh_token={reprlib.repr(self.refresh_token)})"

    async def _authenticate(self) -> Tuple[int, JsonObject]:
        async with ClientSession(json_serialize=self.json_dumps) as session:
            data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token
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
    def __init__(self, consumer_key: str, consumer_secret: str,
                 domain: str,
                 json_dumps: JsonDumper = json.dumps,
                 json_loads: JsonLoader = json.loads) -> None:
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
            raise ValueError("domain is required for the client "
                             "credentials flow")
        if "://" in value:
            raise ValueError("domain must be a bare My Domain name, "
                             f"not a URL: {domain!r}")
        if value.endswith(".salesforce.com"):
            raise ValueError("domain must not carry the .salesforce.com "
                             f"suffix: {domain!r}")
        if value in ("login", "test"):
            raise ValueError("the client credentials flow requires an "
                             f"org's My Domain host, not {value!r}")
        return value

    @property
    def _token_url(self) -> str:
        """The URL that should be used for token requests"""
        return f"https://{self.domain}.salesforce.com/services/oauth2/token"

    def __repr__(self) -> str:
        """Formal string representation"""
        cls_name = type(self).__name__
        return f"{cls_name}(consumer_key={reprlib.repr(self.client_id)}, " \
               f"consumer_secret={reprlib.repr(self.client_secret)}, " \
               f"domain={reprlib.repr(self.domain)})"

    async def _authenticate(self) -> Tuple[int, JsonObject]:
        async with ClientSession(json_serialize=self.json_dumps) as session:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            response = await session.post(self._token_url, data=data)
            response_data = await response.json(loads=self.json_loads)
            return response.status, response_data


# pylint: enable=too-many-arguments
