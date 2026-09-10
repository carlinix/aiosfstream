"""Sphinx configuration for the aiosfstream documentation."""

from importlib.metadata import version as distribution_version

project = "aiosfstream"
author = "Ricardo Carlini Sperandio"
copyright = "2018–2025, Róbert Márki; 2025–2026, Ricardo Carlini Sperandio"
release = distribution_version("aiosfstream")
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
]

autoclass_content = "both"
autodoc_typehints = "description"
exclude_patterns = []
html_static_path = ["_static"]
html_theme = "alabaster"
intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
language = "en"
pygments_style = "sphinx"
root_doc = "index"
templates_path = ["_templates"]

htmlhelp_basename = "aiosfstreamdoc"
latex_documents = [
    (root_doc, "aiosfstream.tex", "aiosfstream Documentation", author, "manual"),
]
man_pages = [
    (root_doc, "aiosfstream", "aiosfstream Documentation", [author], 1),
]
texinfo_documents = [
    (
        root_doc,
        "aiosfstream",
        "aiosfstream Documentation",
        author,
        "aiosfstream",
        "Salesforce Streaming API client for asyncio.",
        "Miscellaneous",
    ),
]
