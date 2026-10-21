"""Run the functional notebooks in ``tests/functional/`` and report each one.

The shared runner for a project's functional notebooks. It runs from
pre-commit (staged notebooks at commit, all notebooks at push), and by hand::

    uv run python tools/run_notebooks.py
    uv run python tools/run_notebooks.py tests/functional/rendering.ipynb
    uv run python tools/run_notebooks.py --include-slow --timeout 900
    uv run python tools/run_notebooks.py --save tests/functional/search.ipynb

(``nbclient``, ``nbformat`` and ``ipykernel`` are dev dependencies of the
project; ``pydantic`` is a dependency of every project. Run it from the
project root.)

Each notebook runs top to bottom in a fresh kernel whose working folder is a
temporary folder, so it cannot depend on files in the project or write into
it. When ``pytest.ini`` sets ``pythonpath``, the kernel gets the same folders
in ``PYTHONPATH``, so notebooks import the project the way the tests do. The
kernel also gets ``MPLBACKEND=agg`` unless you set one, so no window opens.

One line is printed per notebook: name, ``PASS``, ``FAIL`` or ``SKIP``, and the
seconds it took. A failure adds the number of the cell (counting from 1, over
all cells) and the error. The exit code is 1 when any notebook failed. A skip
is not a failure.

With file arguments only those notebooks run, slow or not. With none, every
``tests/functional/*.ipynb`` runs except notebooks marked slow, unless
``--include-slow`` is given.

Notebook metadata the runner reads (the ``metadata`` object of the notebook):

* ``"slow": true`` leaves the notebook out of runs that name no files, unless
    ``--include-slow`` is given.
* ``"requires": ["display"]`` skips the notebook, with the reason, when the
    machine lacks that. ``display`` is detected (macOS, Windows, or ``DISPLAY``
    or ``WAYLAND_DISPLAY`` set). Any other name, such as ``gpu`` or ``network``,
    counts as present only when the environment variable
    ``RUN_NOTEBOOKS_HAS_<NAME>`` (upper case) is ``1``.

A notebook is never edited unless ``--save`` is given. Then the executed
notebook, with its new outputs, replaces the file, but only when it passed.
"""

import argparse
import asyncio
import configparser
import contextlib
import os
import sys
import tempfile
import time
from collections.abc import Generator, Sequence
from pathlib import Path
from typing import Literal

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError, DeadKernelError
from nbformat import NotebookNode
from pydantic import BaseModel, ConfigDict

NOTEBOOK_DIR = Path("tests/functional")
DEFAULT_TIMEOUT = 300
NO_DISPLAY_PLATFORMS = {"linux", "freebsd", "openbsd"}
DISPLAY_VARIABLES = ("DISPLAY", "WAYLAND_DISPLAY")
REQUIREMENT_VARIABLE = "RUN_NOTEBOOKS_HAS_"
NAME_WIDTH = 32


class Model(BaseModel):
    """Base class for the records of this tool: frozen, no extra fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


type Status = Literal["PASS", "FAIL", "SKIP"]


class Outcome(Model):
    """What happened to one notebook.

    Attributes
    ----------
    name
        The file name of the notebook.
    status
        Pass, fail or skip.
    seconds
        Wall-clock time spent on it.
    detail
        For a failure, the cell number and error; for a skip, the reason.
    """

    name: str
    status: Status
    seconds: float
    detail: str = ""


class NotebookMeta(BaseModel):
    """The notebook metadata this runner reads; other keys are ignored.

    Attributes
    ----------
    slow
        True when the notebook takes about a minute or more.
    requires
        Names of things the machine must have for the notebook to run.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    slow: bool = False
    requires: list[str] = []


def read_notebook(path: Path) -> NotebookNode:
    """Read a notebook file as nbformat version 4.

    nbformat has no type annotations, so this wrapper is the one place that
    calls it for reading.

    Parameters
    ----------
    path
        The notebook file.

    Returns
    -------
    NotebookNode
        The notebook.
    """
    notebook: NotebookNode = nbformat.read(path, as_version=4)  # type: ignore[no-untyped-call]  # nbformat is untyped
    return notebook


def write_notebook(notebook: NotebookNode, path: Path) -> None:
    """Write ``notebook`` to ``path`` (nbformat is untyped, see above).

    Parameters
    ----------
    notebook
        The notebook to write.
    path
        The notebook file.
    """
    nbformat.write(notebook, path)  # type: ignore[no-untyped-call]  # nbformat is untyped


def pythonpath(root: Path) -> str:
    """Build the ``PYTHONPATH`` value the way ``pytest.ini`` sets it.

    Parameters
    ----------
    root
        The project root.

    Returns
    -------
    str
        The ``pythonpath`` folders of ``pytest.ini`` as absolute paths joined
        with the path separator, or an empty string when there are none.
    """
    config = configparser.ConfigParser()
    config.read(root / "pytest.ini")
    names = config.get("pytest", "pythonpath", fallback="").split()
    return os.pathsep.join(str(root / name) for name in names)


@contextlib.contextmanager
def kernel_environment(root: Path) -> Generator[None]:
    """Set the environment the kernel will inherit, then restore it.

    Parameters
    ----------
    root
        The project root, used to resolve ``pythonpath``.

    Yields
    ------
    None
        While ``PYTHONPATH`` and ``MPLBACKEND`` are set.
    """
    saved = dict(os.environ)
    try:
        folders = pythonpath(root)
        if folders:
            existing = os.environ.get("PYTHONPATH")
            os.environ["PYTHONPATH"] = (
                folders if not existing else folders + os.pathsep + existing
            )
        os.environ.setdefault("MPLBACKEND", "agg")
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


def _has_display() -> bool:
    """Tell whether this machine can show a window.

    Returns
    -------
    bool
        True on macOS and Windows, and on other systems when ``DISPLAY`` or
        ``WAYLAND_DISPLAY`` is set.
    """
    if not sys.platform.startswith(tuple(NO_DISPLAY_PLATFORMS)):
        return True
    return any(os.environ.get(name) for name in DISPLAY_VARIABLES)


def unmet_requirements(requires: Sequence[str]) -> list[str]:
    """List the requirements this machine does not meet.

    Parameters
    ----------
    requires
        The ``requires`` names from the notebook metadata.

    Returns
    -------
    list[str]
        The names that are not met, in the order given.
    """
    missing: list[str] = []
    for name in requires:
        if name == "display":
            met = _has_display()
        else:
            variable = REQUIREMENT_VARIABLE + name.upper()
            met = os.environ.get(variable) == "1"
        if not met:
            missing.append(name)
    return missing


def first_line(source: str) -> str:
    """Return the first line of a cell's source, for error messages.

    Parameters
    ----------
    source
        The source of a notebook cell.

    Returns
    -------
    str
        The first line, or an empty string for an empty cell.
    """
    lines = source.strip().splitlines()
    return lines[0] if lines else ""


def _execute(notebook: NotebookNode, timeout: int) -> str:
    """Execute ``notebook`` in a clean kernel inside a temporary folder.

    The notebook is updated in place with the new outputs.

    Parameters
    ----------
    notebook
        A notebook read with nbformat.
    timeout
        Seconds allowed for the whole notebook.

    Returns
    -------
    str
        An empty string on success; otherwise the failing cell number and
        the error.
    """
    current: list[int] = [0]

    def remember(*, cell_index: int, **_: object) -> None:
        current[0] = cell_index

    started = time.monotonic()
    with tempfile.TemporaryDirectory() as folder:
        client = NotebookClient(
            notebook,
            resources={"metadata": {"path": folder}},
            on_cell_start=remember,
        )
        try:
            asyncio.run(asyncio.wait_for(client.async_execute(), timeout))
        except CellExecutionError as error:
            problem = f"{error.ename}: {error.evalue}"
        except DeadKernelError:
            # nbclient reports the cancelled run (our timeout) as a dead kernel.
            timed_out = time.monotonic() - started >= timeout
            problem = (
                f"timed out after {timeout} s"
                if timed_out
                else "the kernel died"
            )
        else:
            return ""
    cell = notebook.cells[current[0]]
    return (
        f"cell {current[0] + 1} ({first_line(str(cell.source))!r}): {problem}"
    )


def run_notebook(
    path: Path, *, root: Path, timeout: int, save: bool = False
) -> Outcome:
    """Run one notebook and say what happened.

    Parameters
    ----------
    path
        The notebook file.
    root
        The project root, used to resolve ``pythonpath``.
    timeout
        Seconds allowed for the whole notebook.
    save
        Write the executed notebook back to ``path`` when it passed.

    Returns
    -------
    Outcome
        PASS, FAIL (unreadable, bad metadata, a failing cell, a timeout, a
        dead kernel) or SKIP (a requirement is not met).
    """
    started = time.monotonic()

    def outcome(status: Status, detail: str = "") -> Outcome:
        seconds = time.monotonic() - started
        return Outcome(
            name=path.name, status=status, seconds=seconds, detail=detail
        )

    try:
        notebook = read_notebook(path)
        meta = NotebookMeta.model_validate(dict(notebook.metadata))
    except (OSError, ValueError) as error:
        return outcome("FAIL", f"cannot read the notebook: {error}")
    missing = unmet_requirements(meta.requires)
    if missing:
        return outcome("SKIP", "requires " + ", ".join(missing))
    with kernel_environment(root):
        problem = _execute(notebook, timeout)
    if problem:
        return outcome("FAIL", problem)
    if save:
        write_notebook(notebook, path)
    return outcome("PASS")


def _is_slow(path: Path) -> bool:
    """Tell whether a notebook is marked ``"slow": true``.

    Parameters
    ----------
    path
        The notebook file.

    Returns
    -------
    bool
        True when marked slow; False when not, or when the file or its
        metadata cannot be read (the run then reports the problem).
    """
    try:
        notebook = read_notebook(path)
        return NotebookMeta.model_validate(dict(notebook.metadata)).slow
    except (OSError, ValueError):
        return False


def select_notebooks(
    files: Sequence[Path], *, root: Path, include_slow: bool
) -> list[Path]:
    """Choose the notebooks to run.

    Parameters
    ----------
    files
        Notebooks named on the command line.
    root
        The project root.
    include_slow
        Keep slow notebooks when no files are named.

    Returns
    -------
    list[Path]
        ``files`` as given when there are any. Otherwise the notebooks in
        ``tests/functional`` in name order, without the slow ones unless
        ``include_slow``.
    """
    if files:
        return list(files)
    found = sorted((root / NOTEBOOK_DIR).glob("*.ipynb"))
    return [path for path in found if include_slow or not _is_slow(path)]


def _report(outcome: Outcome) -> str:
    """Format an outcome as the line or lines printed for it.

    Parameters
    ----------
    outcome
        The result of one notebook.

    Returns
    -------
    str
        ``name  STATUS  seconds``, followed by an indented detail line for
        a failure or a skip.
    """
    name = f"{outcome.name:<{NAME_WIDTH}}"
    line = f"{name} {outcome.status}  {outcome.seconds:6.1f}s"
    if outcome.detail:
        line += f"\n    {outcome.detail}"
    return line


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    """Read the command line.

    Parameters
    ----------
    argv
        The arguments, or None for ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Run the functional notebooks and report each one.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="notebooks to run (default: all in tests/functional, no slow)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="seconds allowed per notebook (default: %(default)s)",
    )
    parser.add_argument(
        "--include-slow",
        action="store_true",
        help="also run notebooks marked slow when no files are named",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="write the new outputs back into notebooks that pass",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected notebooks and print one line for each.

    Parameters
    ----------
    argv
        The arguments, or None for ``sys.argv``.

    Returns
    -------
    int
        0 when no notebook failed, 1 otherwise.
    """
    args = _parse(argv)
    root = Path.cwd()
    paths = select_notebooks(
        args.files, root=root, include_slow=args.include_slow
    )
    if not paths:
        sys.stdout.write("No notebooks to run.\n")
        return 0
    failed = False
    for path in paths:
        outcome = run_notebook(
            path, root=root, timeout=args.timeout, save=args.save
        )
        sys.stdout.write(_report(outcome) + "\n")
        sys.stdout.flush()
        failed = failed or outcome.status == "FAIL"
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
