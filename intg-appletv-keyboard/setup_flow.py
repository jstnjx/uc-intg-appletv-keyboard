"""Dynamic setup: discover one Apple TV and pair Companion."""

from __future__ import annotations

import asyncio
from enum import IntEnum
import logging
import socket
from typing import Callable

import pyatv
from pyatv.const import Protocol
from pyatv.interface import BaseConfig, PairingHandler
from ucapi import (
    AbortDriverSetup,
    DriverSetupRequest,
    IntegrationSetupError,
    RequestUserInput,
    SetupAction,
    SetupComplete,
    SetupDriver,
    SetupError,
    UserDataResponse,
)

from config import AppleTVConfig, ConfigStore

_LOG = logging.getLogger(__name__)


class Step(IntEnum):
    INIT = 0
    DISCOVER = 1
    CHOOSE = 2
    PAIR = 3


class SetupFlow:
    """Single-device setup flow."""

    def __init__(
        self,
        store: ConfigStore,
        loop: asyncio.AbstractEventLoop,
        on_configured: Callable[[AppleTVConfig], None],
    ) -> None:
        self.store = store
        self.loop = loop
        self.on_configured = on_configured
        self.step = Step.INIT
        self.devices: list[BaseConfig] = []
        self.selected: BaseConfig | None = None
        self.pairing: PairingHandler | None = None

    def setup_data_schema(self) -> dict:
        existing = self.store.load()
        suffix = f" Current device: {existing.name}." if existing else ""
        return {
            "title": {"en": "Apple TV Keyboard setup"},
            "settings": [
                {
                    "id": "info",
                    "label": {"en": "Keyboard bridge"},
                    "field": {
                        "label": {
                            "value": {
                                "en": (
                                    "Select and pair an Apple TV. The integration uses only the "
                                    "Companion protocol and exposes a media-player search field as "
                                    "the Remote keyboard." + suffix
                                )
                            }
                        }
                    },
                }
            ],
        }

    async def __call__(self, msg: SetupDriver) -> SetupAction:
        if isinstance(msg, AbortDriverSetup):
            await self._close_pairing()
            self.step = Step.INIT
            return SetupError(error_type=IntegrationSetupError.OTHER)

        if isinstance(msg, DriverSetupRequest):
            await self._close_pairing()
            self.step = Step.DISCOVER
            return self._request_address(msg.reconfigure)

        if not isinstance(msg, UserDataResponse):
            return SetupError()

        if self.step == Step.DISCOVER:
            return await self._discover(msg)
        if self.step == Step.CHOOSE:
            return await self._choose(msg)
        if self.step == Step.PAIR:
            return await self._finish_pairing(msg)
        return SetupError()

    def _request_address(self, reconfigure: bool) -> RequestUserInput:
        current = self.store.load()
        current_label = (
            f"Currently configured: {current.name} ({current.address})" if current else "No Apple TV configured yet."
        )
        return RequestUserInput(
            {"en": "Find Apple TV"},
            [
                {
                    "id": "info",
                    "label": {"en": "Device"},
                    "field": {"label": {"value": {"en": current_label}}},
                },
                {
                    "id": "address",
                    "label": {"en": "IP address (optional)"},
                    "field": {"text": {"value": current.address if current and reconfigure else ""}},
                },
            ],
        )

    async def _discover(self, msg: UserDataResponse) -> SetupAction:
        address = msg.input_values.get("address", "").strip()
        hosts = [address] if address else None
        try:
            self.devices = await pyatv.scan(self.loop, hosts=hosts, timeout=5)
        except Exception:
            _LOG.exception("Apple TV discovery failed")
            return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)

        choices = []
        usable: list[BaseConfig] = []
        for device in self.devices:
            if not device.identifier:
                continue
            if device.get_service(Protocol.Companion) is None:
                continue
            usable.append(device)
            choices.append(
                {
                    "id": device.identifier,
                    "label": {"en": f"{device.name} ({device.address})"},
                }
            )
        self.devices = usable
        if not choices:
            return SetupError(error_type=IntegrationSetupError.NOT_FOUND)

        self.step = Step.CHOOSE
        return RequestUserInput(
            {"en": "Choose Apple TV"},
            [
                {
                    "id": "choice",
                    "label": {"en": "Apple TV"},
                    "field": {
                        "dropdown": {
                            "value": choices[0]["id"],
                            "items": choices,
                        }
                    },
                }
            ],
        )

    async def _choose(self, msg: UserDataResponse) -> SetupAction:
        identifier = msg.input_values.get("choice", "")
        self.selected = next(
            (device for device in self.devices if device.identifier == identifier), None
        )
        if self.selected is None:
            return SetupError(error_type=IntegrationSetupError.NOT_FOUND)

        try:
            self.pairing = await pyatv.pair(
                self.selected,
                Protocol.Companion,
                self.loop,
                name=f"UC Keyboard {socket.gethostname().split('.', 1)[0]}",
            )
            await self.pairing.begin()
        except Exception:
            _LOG.exception("Could not start Companion pairing")
            await self._close_pairing()
            return SetupError(error_type=IntegrationSetupError.AUTHORIZATION_ERROR)

        self.step = Step.PAIR
        return RequestUserInput(
            {"en": "Pair Apple TV"},
            [
                {
                    "id": "pin",
                    "label": {"en": "PIN shown on Apple TV"},
                    "field": {"number": {"min": 0, "max": 9999, "value": 0}},
                }
            ],
        )

    async def _finish_pairing(self, msg: UserDataResponse) -> SetupAction:
        if self.pairing is None or self.selected is None:
            return SetupError(error_type=IntegrationSetupError.AUTHORIZATION_ERROR)

        try:
            pin = int(msg.input_values.get("pin", ""))
            self.pairing.pin(pin)
            await self.pairing.finish()
            credentials = self.pairing.service.credentials
            if not self.pairing.has_paired or not credentials:
                raise RuntimeError("Pairing did not return Companion credentials")

            stored = AppleTVConfig(
                identifier=str(self.selected.identifier),
                name=self.selected.name,
                address=str(self.selected.address),
                companion_credentials=str(credentials),
            )
            self.store.save(stored)
            self.on_configured(stored)
            _LOG.info("Configured Apple TV keyboard bridge for %s", stored.name)
            return SetupComplete()
        except (ValueError, TypeError):
            return SetupError(error_type=IntegrationSetupError.AUTHORIZATION_ERROR)
        except Exception:
            _LOG.exception("Companion pairing failed")
            return SetupError(error_type=IntegrationSetupError.AUTHORIZATION_ERROR)
        finally:
            await self._close_pairing()
            self.step = Step.INIT

    async def _close_pairing(self) -> None:
        pairing = self.pairing
        self.pairing = None
        if pairing is not None:
            try:
                await pairing.close()
            except Exception:
                _LOG.debug("Error closing pairing handler", exc_info=True)
