"""Creation of the EA database file."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

from rich.console import Console
from sqlalchemy import Engine, PoolProxiedConnection, create_engine, event
from sqlalchemy.pool import ConnectionPoolEntry
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

    The engine's connections write in WAL mode with ``synchronous=NORMAL``
    (DESIGN.md Decisions, goal 13): a commit does not wait for the disk, so
    a power cut can lose the last commit or two, but never corrupts the
    file. While the database is open, SQLite keeps ``-wal`` and ``-shm``
    files beside it.

    Parameters
    ----------
    db_file_path : Path
        Destination path for the SQLite database file.
    db_handling : DBHandlingMode
        ``"delete"`` removes any existing file, with its ``-wal`` and
        ``-shm`` files, before creating a fresh database. ``"halt"`` raises
        ``FileExistsError`` immediately.
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
                # An old journal must not meet the new file
                for suffix in ("-wal", "-shm"):
                    Path(f"{db_file_path}{suffix}").unlink(missing_ok=True)
            case "halt":
                msg = f"⚠️  {msg} → halted"
                raise FileExistsError(msg)

    engine = create_engine(f"sqlite:///{db_file_path}")
    event.listen(engine, "connect", _write_ahead)
    SQLModel.metadata.create_all(engine)
    return engine


def _write_ahead(
    connection: PoolProxiedConnection, _record: ConnectionPoolEntry
) -> None:
    # Each new connection: write-ahead log, no disk sync at each commit
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def leave_write_ahead(engine: Engine) -> None:
    """Switch the database of ``engine`` back from WAL to a rollback journal.

    A WAL file can be read only where SQLite may create its ``-shm`` file,
    so a closed run would not open in a read-only folder. Call it after
    ``engine.dispose()``. While another connection (an open ``Archive``,
    say) is reading the file, or the file or its folder is read-only, it
    stays in WAL mode: ``close`` must not fail or wait because someone
    reads the run. Does nothing when the file is gone.

    Parameters
    ----------
    engine : Engine
        The engine ``setup_database`` returned.

    Raises
    ------
    sqlite3.OperationalError
        If SQLite fails for another reason, such as a disk error.
    """
    path = Path(str(engine.url.database))
    # Switching writes the file, and creates and removes files beside it
    writable = os.access(path, os.W_OK) and os.access(path.parent, os.W_OK)
    if not path.exists() or not writable:
        return
    with closing(sqlite3.connect(path, timeout=0)) as connection:
        try:
            connection.execute("PRAGMA journal_mode=DELETE")
        except sqlite3.OperationalError as error:
            # A reader holds the file
            if "locked" not in str(error):
                raise
