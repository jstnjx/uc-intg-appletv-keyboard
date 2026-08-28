"""Typed configuration for the Apple TV Keyboard integration."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class AppleTVConfig:
    """Persisted Apple TV Companion configuration."""

    identifier: str
    name: str
    address: str
    companion_credentials: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        """Normalize configurations loaded from older or interrupted setups."""
        self.identifier = str(self.identifier).strip()
        self.name = str(self.name).strip() or "Apple TV"
        self.address = str(self.address).strip()
        self.companion_credentials = str(self.companion_credentials).strip()
