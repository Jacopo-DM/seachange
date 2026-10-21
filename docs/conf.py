"""Sphinx configuration.

Name and version are read from ``pyproject.toml``, so nothing here changes
from one library to the next. Build with ``uv-docs build``; preview with
``uv-docs``.
"""

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class _Project(BaseModel):
    """The ``[project]`` fields this file needs."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str
    version: str


class _Pyproject(BaseModel):
    """The part of ``pyproject.toml`` this file reads."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    project: _Project


_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
_META = _Pyproject.model_validate(tomllib.loads(_PYPROJECT.read_text("utf-8")))

project = _META.project.name
release = _META.project.version
author = "jmdm"
project_copyright = f"{project} authors"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
]

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
exclude_patterns = ["_build"]
html_theme = "furo"

# Markdown sources (MyST). Docstrings stay numpy style, as in core.md.
myst_enable_extensions = ["colon_fence", "deflist"]
napoleon_google_docstring = False
napoleon_numpy_docstring = True

autosummary_generate = True
autodoc_typehints = "description"
autodoc_member_order = "bysource"
intersphinx_mapping = {"python": ("https://docs.python.org/3.13", None)}
