aiosfstream
===========

.. image:: https://badge.fury.io/py/aiosfstream.svg
    :target: https://badge.fury.io/py/aiosfstream
    :alt: PyPI package

.. image:: https://readthedocs.org/projects/aiosfstream/badge/?version=latest
    :target: http://aiosfstream.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://github.com/carlinix/aiosfstream/actions/workflows/ci.yml/badge.svg?branch=develop
    :target: https://github.com/carlinix/aiosfstream/actions/workflows/ci.yml
    :alt: Build status

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
    :target: https://opensource.org/licenses/MIT
    :alt: MIT license

aiosfstream is a `Salesforce Streaming API <api_>`_ client for asyncio_. It can
be used to receive push notifications about changes on Salesforce objects or
notifications of general events sent through the `Streaming API <api_>`_.

For detailed guidance on how to work with `PushTopics <PushTopic_>`_ or how
to create `Generic Streaming Channels <GenericStreaming_>`_ please consult the
`Streaming API documentation <api_>`_.
For working with `Platform Events <PlatformEvents_>`_ or
`Change Data Capture events <ChangeDataCapture_>`_ check out the linked
documentation.

Features
--------

- Supported authentication types:
   - using a username and password
   - using a refresh token
- Subscribe to and receive messages on:
    - `PushTopics <PushTopic_>`_
    - `Generic Streaming Channels <GenericStreaming_>`_
    - `Platform Events <PlatformEvents_>`_
    - `Change Data Capture events <ChangeDataCapture_>`_
- Support for `durable messages and replay of events <replay_>`_
- Automatic recovery from replay errors

Usage
-----

.. code-block:: python

    import asyncio

    from aiosfstream import SalesforceStreamingClient


    async def stream_events():
        # Connect to the Streaming API.
        async with SalesforceStreamingClient(
                consumer_key="<consumer key>",
                consumer_secret="<consumer secret>",
                username="<username>",
                password="<password>") as client:

            # Subscribe to topics.
            await client.subscribe("/topic/one")
            await client.subscribe("/topic/two")

            # Listen for incoming messages.
            async for message in client:
                topic = message["channel"]
                data = message["data"]
                print(f"{topic}: {data}")

    if __name__ == "__main__":
        asyncio.run(stream_events())

Documentation
-------------

http://aiosfstream.readthedocs.io/

Install
-------

.. code-block:: bash

    pip install aiosfstream

Requirements
------------

- Python 3.11+
- aiohttp_
- aiocometd_

Development
-----------

The repository uses uv_ for dependency management and command execution. The
lockfile contains the exact development environment:

.. code-block:: bash

    uv sync --all-groups

Run the same checks as continuous integration before opening a pull request:

.. code-block:: bash

    uv run ruff check .
    uv run ruff format --check .
    uv run coverage run -m pytest
    uv run coverage report
    uv run sphinx-build -E -W --keep-going -b html docs/source docs/build/html
    uv build --no-sources
    uv run twine check --strict dist/*
    uv run check-wheel-contents dist/*.whl

Releasing
---------

The release workflow accepts an existing unprefixed SemVer tag that matches the
version in ``pyproject.toml``. It builds the distributions once, then reuses the
same artifacts for every enabled registry and the GitHub Release.

Publishing is disabled by default:

- Set ``ENABLE_PYPI_PUBLISH`` to ``true`` after configuring the ``pypi``
  Trusted Publisher environment.
- Set ``ENABLE_GCP_PUBLISH`` to ``true`` after configuring the
  ``GCP_WORKLOAD_IDENTITY_PROVIDER`` and ``GCP_SERVICE_ACCOUNT`` secrets. The
  service account must be able to write to the ``avid-python-packages``
  Artifact Registry repository.

Publish ``aiocometd`` 1.0.0 to each package registry before enabling the
corresponding publication target for this project. The uv Git source is used
only for development and CI resolution.

.. _aiohttp: https://github.com/aio-libs/aiohttp/
.. _aiocometd: https://github.com/carlinix/aiocometd/
.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _uv: https://docs.astral.sh/uv/
.. _api: https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/intro_stream.htm
.. _PushTopic: https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/working_with_pushtopics.htm
.. _GenericStreaming: https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/generic_streaming_intro.htm#generic_streaming_intro
.. _replay: https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/using_streaming_api_durability.htm
.. _PlatformEvents: https://developer.salesforce.com/docs/atlas.en-us.platform_events.meta/platform_events/platform_events_intro.htm
.. _ChangeDataCapture: https://developer.salesforce.com/docs/atlas.en-us.change_data_capture.meta/change_data_capture/cdc_intro.htm
