"""Test: restarting an EA and its edge cases."""

from pathlib import Path
from typing import Literal, cast

import pytest
from sqlmodel import SQLModel, create_engine

from seachange import EA, DBHandlingMode, config
from tests.ea_helpers import (
    FIRST_GENERATION_ID,
    make_ea,
    make_pop,
    noop,
)

pytestmark = pytest.mark.usefixtures("dispose_engines")

RESTART_STEPS = 3
RESTART_GENERATION = 1


def _finished_run(tmp_path: Path) -> Path:
    # Run a few generations and return the database that was written.
    ea = make_ea(tmp_path, num_steps=RESTART_STEPS)
    ea.run()
    return tmp_path / "test.db"


def _restart(
    tmp_path: Path,
    source: Path | tuple[Path, int],
    *,
    name: str = "restarted.db",
) -> EA:
    return EA(
        restart=source,
        operations=[noop],
        db_file_path=tmp_path / name,
        quiet=True,
    )


def test_restart_continues_after_the_last_generation(tmp_path: Path) -> None:
    """Restarting from a path alone resumes after the latest generation."""
    source = _finished_run(tmp_path / "first")
    ea = _restart(tmp_path / "second", source)
    assert ea.current_generation >= RESTART_STEPS
    assert ea.size > 0


def test_restart_from_a_chosen_generation(tmp_path: Path) -> None:
    """A (path, generation) pair restarts from that generation."""
    source = _finished_run(tmp_path / "first")
    ea = _restart(tmp_path / "second", (source, RESTART_GENERATION))
    assert ea.current_generation == RESTART_GENERATION + 1


def test_restart_from_a_string_path(tmp_path: Path) -> None:
    """A path may be given as a string."""
    source = _finished_run(tmp_path / "first")
    ea = EA(
        restart=str(source),
        operations=[noop],
        db_file_path=tmp_path / "second" / "restarted.db",
        quiet=True,
    )
    assert ea.size > 0


def test_restart_database_must_exist(tmp_path: Path) -> None:
    """A missing source database is an error."""
    with pytest.raises(FileNotFoundError, match="Restart database not found"):
        _restart(tmp_path, tmp_path / "missing.db")


def test_restart_from_an_empty_database_fails(tmp_path: Path) -> None:
    """A database without individuals cannot be restarted from."""
    empty = tmp_path / "empty.db"
    engine = create_engine(f"sqlite:///{empty}")
    SQLModel.metadata.create_all(engine)
    engine.dispose()
    with pytest.raises(ValueError, match="contains no individuals"):
        _restart(tmp_path, empty)


def test_restart_from_a_generation_without_individuals(tmp_path: Path) -> None:
    """A generation that no evaluated individual lived through is an error."""
    source = _finished_run(tmp_path / "first")
    with pytest.raises(ValueError, match="No evaluated individuals"):
        _restart(tmp_path / "second", (source, RESTART_STEPS * 100))


def test_unknown_db_handling_keeps_the_existing_file(tmp_path: Path) -> None:
    """A handling mode that is neither delete nor halt changes nothing."""
    first = make_ea(tmp_path)
    del first
    second = EA(
        population=make_pop(),
        operations=[noop],
        db_file_path=tmp_path / "test.db",
        db_handling=cast("DBHandlingMode", "keep"),
        quiet=True,
    )
    # Both populations are in the file: the old one was not deleted.
    assert second.size == 2 * len(make_pop())


def test_get_solution_with_an_unknown_mode_raises(tmp_path: Path) -> None:
    """A typo in the mode fails at once and names the valid modes."""
    ea = make_ea(tmp_path)
    mode = cast("Literal['best']", "bset")
    with pytest.raises(ValueError, match="'best', 'median' or 'worst'"):
        ea.get_solution(mode)


def test_fetch_population_can_include_dead_and_unevaluated(
    tmp_path: Path,
) -> None:
    """The filters of fetch_population are optional."""
    ea = make_ea(tmp_path)
    ea.fetch_population(only_alive=False, requires_eval=None)
    assert ea.population.size == len(make_pop())
    ea.fetch_population(only_alive=True, requires_eval=True)
    assert ea.population.size == 0


def test_restart_keeps_an_explicit_first_generation(tmp_path: Path) -> None:
    """first_generation_id overrides the generation derived from the restart."""
    source = _finished_run(tmp_path / "first")
    ea = EA(
        restart=source,
        operations=[noop],
        db_file_path=tmp_path / "second" / "restarted.db",
        first_generation_id=FIRST_GENERATION_ID,
        quiet=True,
    )
    assert ea.current_generation == FIRST_GENERATION_ID


@pytest.mark.parametrize("db_handling", ["delete", "halt"])
def test_restart_onto_its_own_default_file_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_handling: DBHandlingMode,
) -> None:
    """Without db_file_path the default file is the source: refuse."""
    source = _finished_run(tmp_path)
    before = source.read_bytes()
    monkeypatch.setattr(config, "output_folder", tmp_path)
    monkeypatch.setattr(config, "db_file_name", source.name)
    with pytest.raises(ValueError, match="same file"):
        EA(
            restart=source,
            operations=[noop],
            db_handling=db_handling,
            quiet=True,
        )
    assert source.read_bytes() == before


def test_restart_onto_its_own_file_by_another_path_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relative and an absolute path to the same file are caught."""
    source = _finished_run(tmp_path)
    before = source.read_bytes()
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="same file"):
        EA(
            restart=source.name,
            operations=[noop],
            db_file_path=source.resolve(),
            quiet=True,
        )
    assert source.read_bytes() == before
