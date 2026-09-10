Installation
============

aiosfstream requires Python 3.11 or newer.

.. code-block:: bash

    pip install aiosfstream

Development environment
-----------------------

The repository uses uv_ and a committed lockfile to provide a reproducible
development environment. Install every development dependency group with:

.. code-block:: bash

    uv sync --all-groups

Run individual checks through uv:

.. code-block:: bash

    uv run pytest
    uv run ruff check .
    uv run ruff format --check .
    uv run sphinx-build -W --keep-going -b html docs/source docs/build/html

.. _uv: https://docs.astral.sh/uv/
