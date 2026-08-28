"""ucapi-framework setup flow for Apple TV discovery and Companion pairing."""

from __future__ import annotations

import logging
import socket
from typing import Any

import pyatv
from pyatv.const import Protocol
from pyatv.interface import BaseConfig, PairingHandler
from ucapi import (
    AbortDriverSetup,
    DriverSetupRequest,
    IntegrationSetupError,
    RequestUserInput,
    SetupAction,
    SetupError,
    SetupDriver,
    UserDataResponse,
)
from ucapi_framework import BaseSetupFlow

from config import AppleTVConfig

_LOG = logging.getLogger(__name__)


class AppleTVSetupFlow(BaseSetupFlow[AppleTVConfig]):
    """Framework setup flow with pyatv Companion PIN pairing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._selected_device: BaseConfig | None = None
        self._pairing: PairingHandler | None = None

    async def handle_driver_setup(self, msg: SetupDriver) -> SetupAction:
        if isinstance(msg, (DriverSetupRequest, AbortDriverSetup)):
            await self._close_pairing()
            self._selected_device = None
        return await super().handle_driver_setup(msg)

    async def get_restore_prompt_text(self) -> str:
        return (
            "Configure an Apple TV for Remote keyboard input. "
            "Continue to discover or manually enter an Apple TV, or restore a "
            "previous ucapi-framework configuration backup."
        )

    def get_manual_entry_form(self) -> RequestUserInput:
        current = self.selected_config_entry
        return RequestUserInput(
            {"en": "Apple TV Keyboard"},
            [
                {
                    "id": "info",
                    "label": {"en": "Apple TV"},
                    "field": {
                        "label": {
                            "value": {
                                "en": (
                                    "Enter the Apple TV IPv4 address. The integration "
                                    "uses the Companion protocol only."
                                )
                            }
                        }
                    },
                },
                {
                    "id": "address",
                    "label": {"en": "Apple TV IP address"},
                    "field": {
                        "text": {
                            "value": current.address if current is not None else ""
                        }
                    },
                },
                {
                    "id": "name",
                    "label": {"en": "Name (optional)"},
                    "field": {
                        "text": {
                            "value": current.name if current is not None else ""
                        }
                    },
                },
            ],
        )

    async def prepare_input_from_discovery(
        self, discovered, additional_input: dict
    ) -> dict:
        data = await super().prepare_input_from_discovery(
            discovered, additional_input
        )
        data["name"] = additional_input.get("name") or discovered.name
        return data

    def get_additional_discovery_fields(self) -> list[dict]:
        return [
            {
                "id": "name",
                "label": {"en": "Name (optional)"},
                "field": {"text": {"value": ""}},
            }
        ]

    async def query_device(
        self, input_values: dict[str, Any]
    ) -> AppleTVConfig | SetupError | RequestUserInput:
        address = str(input_values.get("address", "")).strip()
        identifier = str(input_values.get("identifier", "")).strip()

        if not address:
            _LOG.warning("Apple TV address is required")
            return self.get_manual_entry_form()

        try:
            devices = await pyatv.scan(
                self.driver.loop,
                hosts=[address],
                timeout=5,
                protocol=Protocol.Companion,
            )
        except Exception:
            _LOG.exception("Could not scan Apple TV at %s", address)
            return SetupError(
                error_type=IntegrationSetupError.CONNECTION_REFUSED
            )

        if identifier:
            selected = next(
                (device for device in devices if device.identifier == identifier),
                None,
            )
        else:
            selected = devices[0] if devices else None

        if selected is None or selected.get_service(Protocol.Companion) is None:
            _LOG.warning("No Companion-capable Apple TV found at %s", address)
            return SetupError(error_type=IntegrationSetupError.NOT_FOUND)
        if not selected.identifier:
            return SetupError(error_type=IntegrationSetupError.NOT_FOUND)

        self._selected_device = selected
        name = str(input_values.get("name", "")).strip() or selected.name or "Apple TV"
        return AppleTVConfig(
            identifier=str(selected.identifier),
            name=name,
            address=str(selected.address),
            companion_credentials="",
        )

    async def get_additional_configuration_screen(
        self,
        device_config: AppleTVConfig,
        previous_input: dict[str, Any],
    ) -> RequestUserInput | None:
        _ = previous_input
        await self._close_pairing()

        selected = self._selected_device
        if selected is None or selected.identifier != device_config.identifier:
            devices = await pyatv.scan(
                self.driver.loop,
                identifier=device_config.identifier,
                hosts=[device_config.address],
                timeout=5,
                protocol=Protocol.Companion,
            )
            selected = devices[0] if devices else None

        if selected is None:
            raise ConnectionError("Apple TV disappeared before pairing")

        try:
            self._pairing = await pyatv.pair(
                selected,
                Protocol.Companion,
                self.driver.loop,
                name=f"UC Keyboard {socket.gethostname().split('.', 1)[0]}",
            )
            await self._pairing.begin()
        except Exception:
            _LOG.exception("Could not start Apple TV Companion pairing")
            await self._close_pairing()
            raise

        if not self._pairing.device_provides_pin:
            await self._close_pairing()
            raise RuntimeError(
                "Apple TV Companion pairing did not provide a tvOS PIN flow"
            )

        return RequestUserInput(
            {"en": "Pair Apple TV"},
            [
                {
                    "id": "pin",
                    "label": {"en": "PIN shown on Apple TV"},
                    "field": {
                        "number": {
                            "min": 0,
                            "max": 9999,
                            "value": 0,
                        }
                    },
                }
            ],
        )

    async def handle_additional_configuration_response(
        self, msg: UserDataResponse
    ) -> AppleTVConfig | SetupAction | None:
        if self._pairing is None or self._pending_device_config is None:
            return SetupError(
                error_type=IntegrationSetupError.AUTHORIZATION_ERROR
            )

        try:
            pin = int(msg.input_values.get("pin", ""))
            self._pairing.pin(pin)
            await self._pairing.finish()

            credentials = self._pairing.service.credentials
            if not self._pairing.has_paired or not credentials:
                raise RuntimeError("Pairing did not return Companion credentials")

            self._pending_device_config.companion_credentials = str(credentials)
            _LOG.info(
                "Companion pairing completed for %s",
                self._pending_device_config.name,
            )
            return None
        except (TypeError, ValueError):
            _LOG.warning("Invalid Apple TV pairing PIN")
            return SetupError(
                error_type=IntegrationSetupError.AUTHORIZATION_ERROR
            )
        except Exception:
            _LOG.exception("Apple TV Companion pairing failed")
            return SetupError(
                error_type=IntegrationSetupError.AUTHORIZATION_ERROR
            )
        finally:
            await self._close_pairing()
            self._selected_device = None

    async def _close_pairing(self) -> None:
        pairing = self._pairing
        self._pairing = None
        if pairing is not None:
            try:
                await pairing.close()
            except Exception:
                _LOG.debug("Error closing pyatv pairing handler", exc_info=True)
