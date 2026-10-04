"""Offline reports derived solely from one analysis result."""

from .html import render_html
from .markdown import render_markdown

__all__ = ["render_html", "render_markdown"]
