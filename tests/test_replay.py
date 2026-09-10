import reprlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiocometd.constants import MetaChannel

from aiosfstream.exceptions import ReplayError
from aiosfstream.replay import (
    ConstantReplayId,
    DefaultMappingStorage,
    DefaultReplayIdMixin,
    MappingStorage,
    ReplayMarker,
    ReplayMarkerStorage,
    ReplayMarkerStorageContextManager,
)


class ReplayMarkerStorageStub(ReplayMarkerStorage):
    async def set_replay_marker(self, subscription, replay_marker):
        pass

    async def get_replay_marker(self, subscription):
        pass


@pytest.fixture
def replay_storage():
    return ReplayMarkerStorageStub()


@pytest.mark.asyncio
async def test_incoming_doesnt_extracts_replay_id(replay_storage):
    replay_storage.extract_replay_id = AsyncMock()
    message = {"channel": "/foo/bar"}

    await replay_storage.incoming([message])
    replay_storage.extract_replay_id.assert_not_called()


@pytest.mark.asyncio
async def test_outgoing_with_subscribe(replay_storage):
    replay_storage.insert_replay_id = AsyncMock()
    message = {"channel": MetaChannel.SUBSCRIBE}

    await replay_storage.outgoing([message], {})
    replay_storage.insert_replay_id.assert_called_with(message)


@pytest.mark.asyncio
async def test_get_replay_id(replay_storage):
    marker = ReplayMarker(date="", replay_id="id")
    replay_storage.get_replay_marker = AsyncMock(return_value=marker)
    subscription = "/foo/bar"

    result = await replay_storage.get_replay_id(subscription)

    assert result == marker.replay_id
    replay_storage.get_replay_marker.assert_awaited_with(subscription)


@pytest.mark.asyncio
async def test_get_replay_id_none_marker(replay_storage):
    replay_storage.get_replay_marker = AsyncMock(return_value=None)
    subscription = "/foo/bar"

    result = await replay_storage.get_replay_id(subscription)

    assert result is None
    replay_storage.get_replay_marker.assert_awaited_with(subscription)


@pytest.mark.asyncio
async def test_insert_replay_id_inserts_correct_value(replay_storage):
    replay_id = "id"
    replay_storage.get_replay_id = AsyncMock(return_value=replay_id)
    message = {
        "channel": MetaChannel.SUBSCRIBE,
        "subscription": "/foo/bar",
        "ext": {},
    }

    await replay_storage.insert_replay_id(message)
    assert message["ext"]["replay"][message["subscription"]] == replay_id


@pytest.mark.asyncio
async def test_insert_replay_id_with_replay_fallback(replay_storage):
    replay_storage.get_replay_id = AsyncMock()
    replay_storage.replay_fallback = "fallback"
    message = {
        "channel": MetaChannel.SUBSCRIBE,
        "subscription": "/foo/bar",
        "ext": {},
    }

    await replay_storage.insert_replay_id(message)
    assert message["ext"]["replay"][message["subscription"]] == "fallback"
    replay_storage.get_replay_id.assert_not_awaited()


def test_get_message_date_variants(replay_storage):
    date = datetime.now(UTC).isoformat()

    push_topic = {
        "channel": "/foo/bar",
        "data": {"event": {"createdDate": date, "replayId": "id"}},
    }
    assert replay_storage.get_message_date(push_topic) == date

    platform_event = {
        "channel": "/foo/bar",
        "data": {
            "payload": {"CreatedDate": date},
            "event": {"replayId": "id"},
        },
    }
    assert replay_storage.get_message_date(platform_event) == date

    cdc = {
        "channel": "/foo/bar",
        "data": {
            "payload": {"ChangeEventHeader": {"commitTimestamp": 12345}},
            "event": {"replayId": "id"},
        },
    }
    assert replay_storage.get_message_date(cdc) == "12345"

    with pytest.raises(ReplayError, match="No message creation date found."):
        replay_storage.get_message_date({})


@pytest.mark.asyncio
async def test_extract_replay_id_on_no_previous_id(replay_storage):
    replay_storage.set_replay_marker = AsyncMock()
    replay_storage.get_replay_marker = AsyncMock(return_value=None)
    date = datetime.now(UTC).isoformat()
    replay_storage.get_message_date = MagicMock(return_value=date)

    message = {
        "channel": "/foo/bar",
        "data": {"event": {"createdDate": date, "replayId": "id"}},
    }
    await replay_storage.extract_replay_id(message)

    replay_storage.set_replay_marker.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_replay_id_on_previous_newer(replay_storage):
    replay_storage.set_replay_marker = AsyncMock()
    prev_marker = ReplayMarker(
        date=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
        replay_id="newer_id",
    )
    replay_storage.get_replay_marker = AsyncMock(return_value=prev_marker)
    date = datetime.now(UTC).isoformat()
    replay_storage.get_message_date = MagicMock(return_value=date)

    message = {
        "channel": "/foo/bar",
        "data": {"event": {"createdDate": date, "replayId": "id"}},
    }

    await replay_storage.extract_replay_id(message)
    replay_storage.set_replay_marker.assert_not_awaited()


def test_call_returns_context_manager(replay_storage):
    message = object()
    result = replay_storage(message)
    assert isinstance(result, ReplayMarkerStorageContextManager)
    assert result.replay_storage is replay_storage
    assert result.message is message


# ----- MappingStorage tests -----


@pytest.mark.asyncio
async def test_mapping_storage_set_and_get():
    mapping = {}
    storage = MappingStorage(mapping)
    subscription = "/foo/bar"
    marker = ReplayMarker(date="", replay_id="id")

    await storage.set_replay_marker(subscription, marker)
    assert mapping[subscription] == marker

    result = await storage.get_replay_marker(subscription)
    assert result == marker


def test_mapping_storage_repr():
    mapping = {"a": 1}
    storage = MappingStorage(mapping)
    cls_name = type(storage).__name__
    assert repr(storage) == f"{cls_name}(mapping={reprlib.repr(mapping)})"


@pytest.mark.asyncio
async def test_constant_replay_id():
    storage = ConstantReplayId(1)
    assert await storage.get_replay_id("sub") == 1
    assert await storage.get_replay_marker("sub") is None
    await storage.set_replay_marker("sub", ReplayMarker("", ""))
    assert "ConstantReplayId" in repr(storage)


@pytest.mark.asyncio
async def test_default_replay_id_mixin_behavior():
    storage = DefaultReplayIdMixin("default_id")
    marker = ReplayMarker("", "custom_id")
    storage.get_replay_marker = AsyncMock(return_value=marker)

    result = await storage.get_replay_id("sub")
    assert result == "custom_id"

    storage.get_replay_marker = AsyncMock(return_value=None)
    result = await storage.get_replay_id("sub")
    assert result == "default_id"


def test_default_mapping_storage_repr():
    mapping = {}
    replay_id = "id"
    storage = DefaultMappingStorage(mapping, replay_id)
    cls_name = type(storage).__name__
    assert repr(storage) == (
        f"{cls_name}(mapping={reprlib.repr(mapping)}, "
        f"default_id={reprlib.repr(replay_id)})"
    )
