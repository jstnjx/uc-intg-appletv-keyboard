"""Apple TV Companion connection and keyboard handling."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pyatv
from pyatv.const import KeyboardFocusState, Protocol
from pyatv.interface import AppleTV, DeviceListener, KeyboardListener

from config import AppleTVConfig

_LOG = logging.getLogger(__name__)


class _DeviceListener(DeviceListener):
    def __init__(self, client: "AppleTVKeyboardClient") -> None:
        self._client = client

    def connection_lost(self, exception: Exception) -> None:
        _LOG.warning("Apple TV connection lost: %s", exception)
        self._client.mark_disconnected()

    def connection_closed(self) -> None:
        _LOG.debug("Apple TV connection closed")
        self._client.mark_disconnected()


class _KeyboardListener(KeyboardListener):
    def __init__(self, client: "AppleTVKeyboardClient") -> None:
        self._client = client

    def focusstate_update(
        self,
        old_state: KeyboardFocusState,
        new_state: KeyboardFocusState,
    ) -> None:
        _LOG.debug("Apple TV keyboard focus: %s -> %s", old_state, new_state)
        self._client.focus_state = new_state


class AppleTVKeyboardClient:
    """Maintains one pyatv Companion connection."""

    def __init__(self, config: AppleTVConfig, loop: asyncio.AbstractEventLoop) -> None:
        self.config = config
        self.loop = loop
        self.atv: AppleTV | None = None
        self.focus_state = KeyboardFocusState.Unknown
        self._connect_lock = asyncio.Lock()
        self._device_listener = _DeviceListener(self)
        self._keyboard_listener = _KeyboardListener(self)

    @property
    def connected(self) -> bool:
        return self.atv is not None

    def mark_disconnected(self) -> None:
        self.atv = None
        self.focus_state = KeyboardFocusState.Unknown

    async def connect(self) -> bool:
        """Connect to the configured Apple TV, resolving it by ID first."""
        if self.atv is not None:
            return True

        async with self._connect_lock:
            if self.atv is not None:
                return True

            hosts = [self.config.address] if self.config.address else None
            try:
                devices = await pyatv.scan(
                    self.loop,
                    identifier=self.config.identifier,
                    hosts=hosts,
                    timeout=5,
                )
                if not devices and hosts:
                    # DHCP address may have changed. Fall back to mDNS/identifier discovery.
                    devices = await pyatv.scan(
                        self.loop,
                        identifier=self.config.identifier,
                        timeout=5,
                    )
                if not devices:
                    _LOG.warning("Configured Apple TV not found: %s", self.config.identifier)
                    return False

                device = devices[0]
                if not device.set_credentials(
                    Protocol.Companion, self.config.companion_credentials
                ):
                    _LOG.error("Apple TV does not expose the Companion protocol")
                    return False

                atv = await pyatv.connect(device, self.loop)
                atv.listener = self._device_listener
                atv.keyboard.listener = self._keyboard_listener
                self.atv = atv
                self.focus_state = atv.keyboard.text_focus_state
                self.config.address = str(device.address)
                _LOG.info(
                    "Connected to Apple TV %s (%s), keyboard focus=%s",
                    self.config.name,
                    device.address,
                    self.focus_state.name,
                )
                return True
            except Exception:  # pyatv exposes several transport/auth exceptions
                _LOG.exception("Failed to connect to Apple TV")
                self.mark_disconnected()
                return False

    async def disconnect(self) -> None:
        atv = self.atv
        self.mark_disconnected()
        if atv is None:
            return
        try:
            pending = atv.close()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        except Exception:
            _LOG.debug("Error while closing Apple TV connection", exc_info=True)

    async def current_focus(self) -> KeyboardFocusState:
        """Return the latest keyboard focus state after ensuring a connection."""
        if not await self.connect() or self.atv is None:
            return KeyboardFocusState.Unknown
        # Read the property every time instead of relying only on callbacks. This is
        # deliberately redundant because keyboard focus push updates have had tvOS/
        # pyatv edge cases in the past.
        self.focus_state = self.atv.keyboard.text_focus_state
        return self.focus_state

    async def set_text(self, text: str) -> tuple[bool, str]:
        """Replace the active Apple TV text field with *text*."""
        if not await self.connect() or self.atv is None:
            return False, "Apple TV is unavailable"

        focus = await self.current_focus()
        if focus != KeyboardFocusState.Focused:
            return False, "Apple TV keyboard is not focused"

        try:
            await self.atv.keyboard.text_set(text)
            return True, "Text sent to Apple TV"
        except Exception:
            _LOG.exception("Failed to send Apple TV keyboard text")
            return False, "Could not send text to Apple TV"
