"""Shared pytest setup: the Hypothesis profile and engine disposal."""

import os
from collections.abc import Iterator

import pytest
import sqlalchemy
from hypothesis import settings
from sqlalchemy import Engine

import seachange.archive
import seachange.ea
import seachange.ea_database

settings.register_profile("default", deadline=None)
settings.register_profile("ci", deadline=None, derandomize=True)
settings.load_profile("ci" if os.environ.get("CI") else "default")


@pytest.fixture
def dispose_engines(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Dispose every engine the package creates during a test.

    Test modules that build an ``EA`` or ``Archive`` opt in with
    ``pytestmark = pytest.mark.usefixtures("dispose_engines")``.

    Without this, each ``EA`` and ``Archive`` leaves a pooled SQLite
    connection for the garbage collector, which warns about it.

    Yields
    ------
    None
        Control to the test.
    """
    engines: list[Engine] = []

    def recording_create_engine(url: str) -> Engine:
        engine = sqlalchemy.create_engine(url)
        engines.append(engine)
        return engine

    for module in (seachange.archive, seachange.ea, seachange.ea_database):
        monkeypatch.setattr(module, "create_engine", recording_create_engine)
    yield
    for engine in engines:
        engine.dispose()
