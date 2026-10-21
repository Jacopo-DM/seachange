"""Creation of the EA database file."""

from pathlib import Path

from rich.console import Console
from sqlalchemy import Engine, create_engine
from sqlmodel import SQLModel

from seachange.ea_settings import DBHandlingMode


def setup_database(
    db_file_path: Path,
    db_handling: DBHandlingMode,
    console: Console,
) -> Engine:
    """Create (or clear) the SQLite database and return its engine.

    The parent directory is created if it does not already exist. When a
    database file is already present at ``db_file_path``, behaviour is
    controlled by ``db_handling``.

    Parameters
    ----------
    db_file_path : Path
        Destination path for the SQLite database file.
    db_handling : DBHandlingMode
        ``"delete"`` removes any existing file before creating a fresh
        database. ``"halt"`` raises ``FileExistsError`` immediately.
    console : Console
        Where the warning about an existing file is logged.

    Returns
    -------
    Engine
        A SQLAlchemy engine connected to the database, with all
        SQLModel tables created.

    Raises
    ------
    FileExistsError
        If a file already exists at ``db_file_path`` and
        ``db_handling`` is ``"halt"``.
    """
    db_file_path.parent.mkdir(parents=True, exist_ok=True)

    if db_file_path.exists():
        msg = f"Database at {db_file_path!r} - handling: {db_handling!r}"
        match db_handling:
            case "delete":
                console.log(f"⚠️  {msg} → deleting", style="yellow")
                db_file_path.unlink()
            case "halt":
                msg = f"⚠️  {msg} → halted"
                raise FileExistsError(msg)

    engine = create_engine(f"sqlite:///{db_file_path}")
    SQLModel.metadata.create_all(engine)
    return engine
