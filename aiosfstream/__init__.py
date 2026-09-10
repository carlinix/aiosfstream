"""Salesforce Streaming API client for asyncio"""

import logging
from importlib.metadata import version as distribution_version

from aiosfstream.auth import (
    ClientCredentialsAuthenticator,
    JWTBearerAuthenticator,
    PasswordAuthenticator,
    RefreshTokenAuthenticator,
)
from aiosfstream.client import (
    Client,
    ReplayMarkerStoragePolicy,
    SalesforceStreamingClient,
)
from aiosfstream.replay import (
    ConstantReplayId,
    DefaultMappingStorage,
    MappingStorage,
    ReplayMarker,
    ReplayMarkerStorage,
    ReplayOption,
)

__version__ = distribution_version("aiosfstream")

__all__ = [
    "Client",
    "ClientCredentialsAuthenticator",
    "ConstantReplayId",
    "DefaultMappingStorage",
    "JWTBearerAuthenticator",
    "MappingStorage",
    "PasswordAuthenticator",
    "RefreshTokenAuthenticator",
    "ReplayMarker",
    "ReplayMarkerStorage",
    "ReplayMarkerStoragePolicy",
    "ReplayOption",
    "SalesforceStreamingClient",
    "__version__",
]

# Create a default handler to avoid warnings in applications without logging
# configuration
logging.getLogger(__name__).addHandler(logging.NullHandler())
