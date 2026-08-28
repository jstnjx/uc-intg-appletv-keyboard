"""Typed configuration for the Apple TV Keyboard integration."""

from dataclasses import dataclass


@dataclass(slots=True)
class AppleTVConfig:
    """Persisted Apple TV Companion configuration."""

    identifier: str
    name: str
    address: str
    companion_credentials: str = ""
