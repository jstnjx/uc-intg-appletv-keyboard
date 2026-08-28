"""Apple TV discovery backed by pyatv."""

from __future__ import annotations

import asyncio
import logging

import pyatv
from pyatv.const import Protocol
from ucapi_framework import BaseDiscovery, DiscoveredDevice

_LOG = logging.getLogger(__name__)


class AppleTVDiscovery(BaseDiscovery):
    """Discover Apple TVs exposing the Companion protocol."""

    async def discover(self) -> list[DiscoveredDevice]:
        self._discovered_devices.clear()
        try:
            devices = await pyatv.scan(
                asyncio.get_running_loop(),
                timeout=self.timeout,
                protocol=Protocol.Companion,
            )
        except Exception:
            _LOG.exception("Apple TV discovery failed")
            return self._discovered_devices

        seen: set[str] = set()
        for device in devices:
            identifier = device.identifier
            if not identifier or identifier in seen:
                continue
            if device.get_service(Protocol.Companion) is None:
                continue
            seen.add(identifier)
            self._discovered_devices.append(
                DiscoveredDevice(
                    identifier=str(identifier),
                    name=device.name or "Apple TV",
                    address=str(device.address),
                )
            )

        _LOG.info(
            "Apple TV discovery complete: found %d device(s)",
            len(self._discovered_devices),
        )
        return self._discovered_devices
