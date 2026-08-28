"""Apple TV Companion device implemented with ucapi-framework."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pyatv
from pyatv.const import KeyboardFocusState, Protocol
from pyatv.interface import AppleTV, DeviceListener, KeyboardListener
from ucapi_framework import ExternalClientDevice

from config import AppleTVConfig

_LOG = logging.getLogger(__name__)


class _DeviceListener(DeviceListener):
    def __init__(self, device: "AppleTVKeyboardDevice") -> None:
        self._device = device

    def connection_lost(self, exception: Exception) -> None:
        _LOG.warning("[%s] Apple TV connection lost: %s", self._device.log_id, exception)
        self._device.on_client_disconnected()

    def connection_closed(self) -> None:
        _LOG.debug("[%s] Apple TV connection closed", self._device.log_id)
        self._device.on_client_disconnected()


class _KeyboardListener(KeyboardListener):
    def __init__(self, device: "AppleTVKeyboardDevice") -> None:
        self._device = device

    def focusstate_update(
        self,
        old_state: KeyboardFocusState,
        new_state: KeyboardFocusState,
    ) -> None:
        _LOG.debug(
            "[%s] Apple TV keyboard focus: %s -> %s",
            self._device.log_id,
            old_state,
            new_state,
        )
        self._device.focus_state = new_state
        self._device.push_update()


class AppleTVKeyboardDevice(ExternalClientDevice):
    """Framework-managed pyatv Companion connection."""

    def __init__(
        self,
        device_config: AppleTVConfig,
        loop: asyncio.AbstractEventLoop | None = None,
        config_manager: Any | None = None,
        driver: Any | None = None,
    ) -> None:
        super().__init__(
            device_config,
            loop,
            enable_watchdog=True,
            watchdog_interval=10,
            reconnect_delay=2,
            max_reconnect_attempts=0,
            config_manager=config_manager,
            driver=driver,
        )
        self.focus_state = KeyboardFocusState.Unknown
        self._pyatv_connected = False
        self._device_listener = _DeviceListener(self)
        self._keyboard_listener = _KeyboardListener(self)

    @property
    def config(self) -> AppleTVConfig:
        return self._device_config

    @property
    def identifier(self) -> str:
        return self.config.identifier

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def address(self) -> str:
        return self.config.address

    @property
    def log_id(self) -> str:
        return f"AppleTVKeyboard[{self.name}]"

    async def create_client(self) -> AppleTV:
        """Resolve the configured device and create a Companion-only pyatv client."""
        hosts = [self.address] if self.address else None
        devices = await pyatv.scan(
            self._loop,
            identifier=self.identifier,
            hosts=hosts,
            timeout=5,
            protocol=Protocol.Companion,
        )
        if not devices and hosts:
            devices = await pyatv.scan(
                self._loop,
                identifier=self.identifier,
                timeout=5,
                protocol=Protocol.Companion,
            )
        if not devices:
            raise ConnectionError(f"Apple TV {self.identifier} was not found")

        config = devices[0]
        if config.get_service(Protocol.Companion) is None:
            raise ConnectionError("Apple TV does not expose the Companion protocol")
        if not config.set_credentials(
            Protocol.Companion, self.config.companion_credentials
        ):
            raise ConnectionError("Could not apply Apple TV Companion credentials")

        client = await pyatv.connect(
            config,
            self._loop,
            protocol=Protocol.Companion,
        )

        new_address = str(config.address)
        if new_address and new_address != self.config.address:
            self.update_config(address=new_address)

        return client

    async def connect_client(self) -> None:
        """Attach pyatv listeners after the framework creates the client."""
        if self._client is None:
            raise ConnectionError("pyatv client was not created")

        self._client.listener = self._device_listener
        self._client.keyboard.listener = self._keyboard_listener
        self._pyatv_connected = True
        self.focus_state = self._client.keyboard.text_focus_state
        self._state = "READY"
        self.push_update()

    async def disconnect_client(self) -> None:
        """Close the pyatv client."""
        client = self._client
        self._pyatv_connected = False
        self.focus_state = KeyboardFocusState.Unknown
        self._state = "UNAVAILABLE"
        self.push_update()

        if client is None:
            return

        pending = client.close()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def check_client_connected(self) -> bool:
        """Return the connection state tracked by pyatv callbacks."""
        return self._client is not None and self._pyatv_connected

    def on_client_disconnected(self) -> None:
        """Handle connection loss reported by pyatv."""
        self._pyatv_connected = False
        self.focus_state = KeyboardFocusState.Unknown
        self._state = "UNAVAILABLE"
        self.push_update()

    async def current_focus(self) -> KeyboardFocusState:
        """Return current tvOS keyboard focus, reconnecting when necessary."""
        if not self.is_connected:
            connected = await self.connect()
            if not connected or self._client is None:
                return KeyboardFocusState.Unknown

        try:
            self.focus_state = self._client.keyboard.text_focus_state
        except Exception:
            _LOG.debug("[%s] Could not read keyboard focus", self.log_id, exc_info=True)
            return KeyboardFocusState.Unknown
        return self.focus_state

    async def set_text(self, text: str) -> tuple[bool, str]:
        """Replace the focused tvOS text field with the supplied text."""
        focus = await self.current_focus()
        if not self.is_connected or self._client is None:
            return False, "Apple TV is unavailable"
        if focus != KeyboardFocusState.Focused:
            return False, "Apple TV keyboard is not focused"

        try:
            await self._client.keyboard.text_set(text)
            return True, "Text sent to Apple TV"
        except Exception:
            _LOG.exception("[%s] Failed to send Apple TV keyboard text", self.log_id)
            return False, "Could not send text to Apple TV"
