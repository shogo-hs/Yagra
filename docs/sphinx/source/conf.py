"""Sphinx configuration for Yagra documentation."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
project_meta = pyproject["project"]

project = "Yagra"
author = ", ".join(item["name"] for item in project_meta.get("authors", []))
copyright = "2026, Yagra contributors"
version = project_meta["version"]
release = version

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
]

autosummary_generate = True
autodoc_typehints = "description"
autoclass_content = "class"

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

myst_enable_extensions = [
    "colon_fence",
    "deflist",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Internationalization
language = "en"
locale_dirs = ["locale/"]
gettext_compact = False

html_theme = "furo"
html_title = f"{project} Documentation"
html_static_path = ["_static"]

# Furo theme options for language switcher
html_theme_options = {
    "top_of_page_buttons": ["view", "edit"],
}
