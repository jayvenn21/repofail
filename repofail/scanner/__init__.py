"""Repo scanner — parses repo structure and produces RepoProfile."""

from .repo import scan_repo
from .host import inspect_host

__all__ = ["scan_repo", "inspect_host"]
