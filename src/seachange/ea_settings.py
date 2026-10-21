"""Settings of the EA engine."""

from pathlib import Path
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings

type DBHandlingMode = Literal["delete", "halt"]


# -- Settings ------------------------------------------------------------------


class EASettings(BaseSettings):
    """
    Global configuration for the EA engine.

    Consumed by both ``EA`` and ``EAOperation``. Values can be overridden via
    environment variables or a ``.env`` file thanks to ``pydantic-settings``.

    Parameters
    ----------
    quiet : bool, optional
        Suppress Rich console output during the run. Default is ``False``.
    is_maximisation : bool, optional
        ``True`` for maximisation problems, ``False`` for minimisation.
        Default is ``True``.
    first_generation_id : int, optional
        Generation counter value assigned to the initial population.
        Default is ``0``.
    num_steps : int, optional
        Total number of generational steps ``EA.run`` will execute.
        Default is ``100``.
    target_population_size : int, optional
        Soft target used by survivor-selection operators to decide how many
        individuals to retain each generation. Default is ``100``.
    output_folder : Path, optional
        Directory under which the database file is created. Created
        automatically if it does not exist. Default is
        ``Path.cwd() / "__data__"``.
    db_file_name : str, optional
        File name of the SQLite database. Default is ``"database.db"``.
    db_handling : DBHandlingMode, optional
        Behaviour when a database with the same path already exists.

        ``"delete"``
            Delete the existing file and start fresh.
        ``"halt"``
            Raise ``FileExistsError`` without modifying anything.

        Default is ``"delete"``.
    """

    quiet: bool = False
    is_maximisation: bool = True
    first_generation_id: int = 0
    num_steps: int = 100
    target_population_size: int = 100
    output_folder: Path = Path.cwd() / "__data__"
    db_file_name: str = "database.db"
    db_handling: DBHandlingMode = "delete"

    @computed_field  # type: ignore[prop-decorator]  # mypy cannot type a decorated property; pydantic documents this ignore
    @property
    def db_file_path(self) -> Path:
        """Absolute path to the SQLite database file.

        Returns
        -------
        Path
            ``output_folder / db_file_name``.
        """
        return self.output_folder / self.db_file_name


config: EASettings = EASettings()
