import pytest
import aiocometd.exceptions as cometd_exc
import aiosfstream.exceptions as exc


# -------------------------
#  Exception Hierarchy Tests
# -------------------------

def test_root_exception():
    assert issubclass(exc.AiosfstreamException, cometd_exc.AiocometdException)


def test_authentication_error():
    assert issubclass(exc.AuthenticationError, exc.AiosfstreamException)


def test_transport_invalid_operation():
    assert issubclass(exc.TransportInvalidOperation, exc.AiosfstreamException)
    assert issubclass(exc.TransportInvalidOperation, exc.TransportError)
    assert issubclass(exc.TransportInvalidOperation, cometd_exc.TransportInvalidOperation)


def test_transport_timeout():
    assert issubclass(exc.TransportTimeoutError, exc.AiosfstreamException)
    assert issubclass(exc.TransportTimeoutError, exc.TransportError)
    assert issubclass(exc.TransportTimeoutError, cometd_exc.TransportTimeoutError)


def test_connection_closed():
    assert issubclass(exc.TransportConnectionClosed, exc.AiosfstreamException)
    assert issubclass(exc.TransportConnectionClosed, exc.TransportError)
    assert issubclass(exc.TransportConnectionClosed, cometd_exc.TransportConnectionClosed)


def test_server_error():
    assert issubclass(exc.ServerError, exc.AiosfstreamException)
    assert issubclass(exc.ServerError, cometd_exc.ServerError)


def test_client_error():
    assert issubclass(exc.ClientError, exc.AiosfstreamException)
    assert issubclass(exc.ClientError, cometd_exc.ClientError)


def test_client_invalid_operation():
    assert issubclass(exc.ClientInvalidOperation, exc.AiosfstreamException)
    assert issubclass(exc.ClientInvalidOperation, exc.ClientError)
    assert issubclass(exc.ClientInvalidOperation, cometd_exc.ClientInvalidOperation)


# -------------------------
#  translate_errors() Tests
# -------------------------

def test_translate_returns_result_on_no_error():
    return_value = object()
    result = exc.translate_errors(lambda: return_value)()
    assert result is return_value


@pytest.mark.asyncio
async def test_async_translate_returns_result_on_no_error():
    return_value = object()

    async def func():
        return return_value

    result = await exc.translate_errors(func)()
