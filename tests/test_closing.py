"""Test: EA and Archive release their database connection when closed.

This module does not use the ``dispose_engines`` fixture, so a connection
left open fails the test through the filters in ``pytest.ini``.
"""

import gc
from pathlib import Path

from seachange import EA, Archive
from tests.ea_helpers import make_pop, noop


def test_ea_close_releases_the_connection(tmp_path: Path) -> None:
    """close() disposes the engine; nothing is left for the collector."""
    ea = EA(
        population=make_pop(),
        operations=[noop],
        db_file_path=tmp_path / "run.db",
        quiet=True,
    )
    ea.close()
    del ea
    gc.collect()


def test_ea_as_context_manager(tmp_path: Path) -> None:
    """``with EA(...) as ea`` gives the EA and closes it on exit."""
    with EA(
        population=make_pop(),
        operations=[noop],
        db_file_path=tmp_path / "run.db",
        quiet=True,
        num_steps=2,
    ) as ea:
        ea.run()
        size = ea.size
    del ea
    gc.collect()
    assert size == len(make_pop())


def test_archive_as_context_manager(tmp_path: Path) -> None:
    """``with Archive(...) as archive`` reads a run and closes on exit."""
    db = tmp_path / "run.db"
    with EA(
        population=make_pop(),
        operations=[noop],
        db_file_path=db,
        quiet=True,
    ):
        pass
    with Archive(db) as archive:
        size = archive.size
    del archive
    gc.collect()
    assert size == len(make_pop())


def test_archive_close_releases_the_connection(tmp_path: Path) -> None:
    """Archive.close() disposes the engine."""
    db = tmp_path / "run.db"
    with EA(
        population=make_pop(),
        operations=[noop],
        db_file_path=db,
        quiet=True,
    ):
        pass
    archive = Archive(db)
    assert archive.size == len(make_pop())
    archive.close()
    del archive
    gc.collect()
