"""Print the structure numbers of the restructure pass (goal 10).

Run from the repo root::

    uv run --no-sync python tools/measure_structure.py

It prints, for the tracked Python files in ``src``, ``tests``, ``examples``
and ``tools``: the file and line counts, the files over ``LINE_LIMIT`` lines,
how many other ``seachange`` modules each package module imports (the ones
over ``IMPORT_LIMIT``), the imports that reach past another package's entry
point (its ``__init__.py``), and jscpd's clone count and duplicated-lines
percentage over ``src``. jscpd is a global tool, not a project dependency;
without it the clone lines say so. ``tools/compress_images.py`` and
``tools/run_notebooks.py`` are template copies and are listed, not counted
as targets.
"""

import ast
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # runs git and jscpd with fixed arguments
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict

LINE_LIMIT = 400
IMPORT_LIMIT = 5
FOLDERS = ("src", "tests", "examples", "tools")
TEMPLATES = {"tools/compress_images.py", "tools/run_notebooks.py"}
PACKAGE = "seachange"
SOURCE = Path("src")
JSCPD_ARGS = ("--min-lines", "8", "--min-tokens", "70")


class Clones(BaseModel):
    """The part of jscpd's JSON report this script reads.

    Attributes
    ----------
    clones
        Number of clone pairs.
    percentage
        Duplicated lines as a percentage of all lines.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    clones: int
    percentage: float


def tracked_files() -> list[Path]:
    """List the tracked Python files in ``FOLDERS``.

    Returns
    -------
    list[Path]
        The files, in git's order.
    """
    listing = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # fixed argv
        ["git", "ls-files", "--", *(f"{f}/*.py" for f in FOLDERS)],  # ruff: ignore[start-process-with-partial-path]  # git from PATH
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(line) for line in listing.stdout.splitlines()]


def module_name(path: Path) -> str:
    """Return the dotted module name of a file under ``src``.

    Returns
    -------
    str
        For example ``seachange.generators.sampling``; a package's
        ``__init__.py`` gives the package name.
    """
    parts = list(path.relative_to(SOURCE).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_modules(path: Path) -> set[str]:
    """Return the ``seachange`` modules that ``path`` imports.

    Returns
    -------
    set[str]
        Dotted names as written in the import statements.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        found.update(n for n in names if n.split(".")[0] == PACKAGE)
    return found


def reaches_past_entry(importer: str, imported: str) -> bool:
    """Tell whether an import goes past another package's ``__init__``.

    ``seachange.generators.sampling`` imported from outside
    ``seachange.generators`` does; the top-level modules of ``seachange``
    are its own modules and do not.

    Returns
    -------
    bool
        True when ``imported`` lies inside a subpackage that ``importer``
        is not part of.
    """
    parts = imported.split(".")
    if len(parts) <= 2:  # ruff: ignore[magic-value-comparison]  # seachange or seachange.x
        return False
    package = ".".join(parts[:2])
    return not (importer == package or importer.startswith(package + "."))


def clones() -> Clones | None:
    """Run jscpd over ``src`` and read its totals.

    Returns
    -------
    Clones or None
        The totals, or None when jscpd is not installed.
    """
    jscpd = shutil.which("jscpd")
    if jscpd is None:
        return None
    with tempfile.TemporaryDirectory() as folder:
        subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # fixed argv
            [
                jscpd,
                *JSCPD_ARGS,
                "--reporters",
                "json",
                "--silent",
                "--output",
                folder,
                str(SOURCE),
            ],
            capture_output=True,
            check=True,
        )
        report = json.loads(
            (Path(folder) / "jscpd-report.json").read_text(encoding="utf-8")
        )
    total = report["statistics"]["total"]
    return Clones(clones=total["clones"], percentage=total["percentage"])


def main() -> None:
    """Print the numbers."""
    out = sys.stdout
    files = tracked_files()
    lines = {
        path: len(path.read_text(encoding="utf-8").splitlines())
        for path in files
    }
    for folder in FOLDERS:
        mine = [p for p in files if p.parts[0] == folder]
        out.write(
            f"{folder:<9} {len(mine):>3} files"
            f" {sum(lines[p] for p in mine):>6} lines\n"
        )
    out.write(
        f"{'total':<9} {len(files):>3} files {sum(lines.values()):>6} lines\n"
    )

    big = sorted(
        (p for p in files if lines[p] > LINE_LIMIT), key=lines.__getitem__
    )
    targets = [p for p in big if str(p) not in TEMPLATES]
    out.write(
        f"\nfiles over {LINE_LIMIT} lines: {len(targets)}"
        " (templates left out)\n"
    )
    for path in big:
        note = "  (template)" if str(path) in TEMPLATES else ""
        out.write(f"  {lines[path]:>5}  {path}{note}\n")

    package_files = [p for p in files if p.parts[0] == "src"]
    imports = {module_name(p): imported_modules(p) for p in package_files}
    counts = {
        name: len({i for i in found if i != name})
        for name, found in imports.items()
    }
    wide = [n for n, c in counts.items() if c > IMPORT_LIMIT]
    out.write(
        f"\nmodules importing more than {IMPORT_LIMIT} seachange modules:"
        f" {len(wide)}\n"
    )
    for name, count in sorted(counts.items(), key=lambda kv: -kv[1])[:6]:
        out.write(f"  {count:>2}  {name}\n")

    out.write("\nimports past another package's entry point:\n")
    past = sorted(
        f"  {name} -> {target}"
        for name, found in imports.items()
        for target in found
        if reaches_past_entry(name, target)
    )
    out.write("\n".join(past) + "\n" if past else "  none\n")

    found_clones = clones()
    if found_clones is None:
        out.write("\nclones: jscpd not installed\n")
    else:
        out.write(
            f"\nclones in src: {found_clones.clones},"
            f" {found_clones.percentage:.2f}% of lines duplicated\n"
        )


if __name__ == "__main__":
    main()
