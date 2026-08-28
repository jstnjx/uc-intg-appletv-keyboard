"""Persistent configuration for the Apple TV Keyboard integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AppleTVConfig:
    """Stored Apple TV pairing information."""

    identifier: str
    name: str
    address: str
    companion_credentials: str


class ConfigStore:
    """Very small JSON backed configuration store."""

    def __init__(self, config_dir: str | Path):
        self._path = Path(config_dir) / "appletv_keyboard.json"

    def load(self) -> AppleTVConfig | None:
        if not self._path.exists():
            return None
        try:
            data: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
            return AppleTVConfig(
                identifier=str(data["identifier"]),
                name=str(data["name"]),
                address=str(data.get("address", "")),
                companion_credentials=str(data["companion_credentials"]),
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def save(self, config: AppleTVConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def clear(self) -> None:
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass
