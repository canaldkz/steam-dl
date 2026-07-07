"""Exception hierarchy for the pipeline."""

from __future__ import annotations


class SteamDlError(Exception):
    """Base class for all recoverable pipeline failures."""


class ValidationError(SteamDlError):
    """A stage's post-condition (assertion) was not met."""


class EnvironmentError_(SteamDlError):
    """Required tools, prefixes or Steam installs are missing."""


class TimeoutError_(SteamDlError):
    """A watcher exceeded its deadline."""
