"""Settings of the EA engine."""

from pathlib import Path
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

type DBHandlingMode = Literal["delete", "halt"]
type Direction = Literal["max", "min"]


# -- Settings ------------------------------------------------------------------


class EASettings(BaseSettings):
    """
    Global configuration for the EA engine.

    Consumed by both ``EA`` and ``EAOperation``. Each field can be overridden
    by an environment variable named ``SEACHANGE_`` plus the field name, for
    example ``SEACHANGE_NUM_STEPS=50``.

    Parameters
    ----------
    quiet : bool, optional
        Suppress Rich console output during the run. Default is ``False``.
    direction : {"max", "min"}, optional
        ``"max"`` when higher fitness is better, ``"min"`` when lower is.
        Default is ``"max"``.
    first_generation_id : int, optional
        Generation counter value assigned to the initial population.
        Default is ``0``.
    num_steps : int, optional
        Total number of generational steps ``EA.run`` will execute.
        Default is ``100``.
    output_folder : Path, optional
        Directory under which the database file is created. Created
        automatically if it does not exist. A relative path is taken from
        the working directory at the time ``db_file_path`` is read, which
        for a run is when the ``EA`` is created. Default is ``"__data__"``.
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

    model_config = SettingsConfigDict(env_prefix="SEACHANGE_")

    quiet: bool = False
    direction: Direction = "max"
    first_generation_id: int = 0
    num_steps: int = 100
    output_folder: Path = Path("__data__")
    db_file_name: str = "database.db"
    db_handling: DBHandlingMode = "delete"

    @computed_field  # type: ignore[prop-decorator]  # mypy cannot type a decorated property; pydantic documents this ignore
    @property
    def db_file_path(self) -> Path:
        """Absolute path to the SQLite database file.

        Returns
        -------
        Path
            ``output_folder / db_file_name``, with a relative
            ``output_folder`` taken from the current working directory.
        """
        return Path.cwd() / self.output_folder / self.db_file_name


config: EASettings = EASettings()
