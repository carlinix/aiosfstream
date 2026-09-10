Changelog
=========

Unreleased
----------

- Replace ``setup.py``, Tox, Flake8, Pylint, and Travis CI with a centralized
  ``pyproject.toml``, uv, Ruff, and GitHub Actions workflows.
- Require Python 3.11 or newer, test Python 3.11 through 3.14, and add
  cross-platform checks on macOS and Windows.
- Validate distribution metadata and wheel contents, smoke-test the installed
  wheel, and provide opt-in PyPI and GCP Artifact Registry publishing.
- Use the maintained ``aiocometd`` 1.0.0 source from the ``carlinix``
  repository for reproducible development and CI environments.
- Update project ownership to Ricardo Carlini Sperandio from 2025 onward.

0.5.0 (2019-03-08)
------------------

- Add support for Change Data Capture events
- Fix some typos in the documentation

0.4.0 (2019-01-06)
------------------

- Add type hints
- Configurable replay storage behavior

0.3.0 (2018-11-07)
------------------

- Add support for sandbox orgs

0.2.5 (2018-11-06)
------------------

- Add missing changelog entries

0.2.4 (2018-11-06)
------------------

- Fix platform event message creation date extraction issue

0.2.3 (2018-09-19)
------------------

- Fix asynchronous iterator bug in python 3.7

0.2.2 (2018-06-15)
------------------

- Update aiocometd dependency to 0.3.1

0.2.1 (2018-05-25)
------------------

- Fix replay issues on mass record delete operations
- Improve the documentation of the Client.publish method

0.2.0 (2018-05-05)
------------------

- Enable the usage of third party JSON libraries
- Expose authentication results as public attributes in Authenticator classes

0.1.0 (2018-04-26)
------------------

- Supported authentication types:
   - using a username and password
   - using a refresh token
- Subscribe to and receive messages on:
    - `PushTopics <PushTopic_>`_
    - `Generic Streaming Channels <GenericStreaming_>`_
- Support for `durable messages and replay of events <replay_>`_
- Automatic recovery from replay errors

.. _aiohttp: https://github.com/aio-libs/aiohttp/
.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _api: https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/intro_stream.htm
.. _PushTopic: https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/working_with_pushtopics.htm
.. _GenericStreaming: https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/generic_streaming_intro.htm#generic_streaming_intro
.. _replay: https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/using_streaming_api_durability.htm
