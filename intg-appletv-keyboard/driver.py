#!/usr/bin/env python3
"""Unfolded Circle Apple TV Keyboard integration."""

from __future__ import annotations

import asyncio
import logging
import os

import ucapi
import ucapi.api as uc

from apple_tv import AppleTVKeyboardClient
from config import AppleTVConfig, ConfigStore
from media_player import AppleTVKeyboardMediaPlayer
from setup_flow import SetupFlow

_LOG = logging.getLogger("driver")
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)
api = uc.IntegrationAPI(_LOOP)
store = ConfigStore(api.config_dir_path)
client: AppleTVKeyboardClient | None = None
entity: AppleTVKeyboardMediaPlayer | None = None
setup_flow: SetupFlow | None = None


def _install_config(config: AppleTVConfig) -> None:
    """Replace the active client/entity after setup succeeds."""
    global client, entity

    old_client = client
    client = AppleTVKeyboardClient(config, _LOOP)
    entity = AppleTVKeyboardMediaPlayer(client)

    api.available_entities.clear()
    api.available_entities.add(entity)

    if old_client is not None:
        _LOOP.create_task(old_client.disconnect())


@api.listens_to(ucapi.Events.CONNECT)
async def on_connect() -> None:
    await api.set_device_state(ucapi.DeviceStates.CONNECTING)
    if client is None:
        await api.set_device_state(ucapi.DeviceStates.DISCONNECTED)
        return
    connected = await client.connect()
    await api.set_device_state(
        ucapi.DeviceStates.CONNECTED if connected else ucapi.DeviceStates.ERROR
    )


@api.listens_to(ucapi.Events.DISCONNECT)
async def on_disconnect() -> None:
    if client is not None:
        await client.disconnect()
    await api.set_device_state(ucapi.DeviceStates.DISCONNECTED)


@api.listens_to(ucapi.Events.ENTER_STANDBY)
async def on_standby() -> None:
    if client is not None:
        await client.disconnect()


@api.listens_to(ucapi.Events.EXIT_STANDBY)
async def on_wake() -> None:
    if client is not None:
        await client.connect()


@api.listens_to(ucapi.Events.SUBSCRIBE_ENTITIES)
async def on_subscribe(entity_ids: list[str]) -> None:
    if client is not None and "appletv_keyboard" in entity_ids:
        await client.connect()


async def main() -> None:
    global setup_flow

    logging.basicConfig(
        level=os.getenv("UC_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    )

    configured = store.load()
    if configured is not None:
        _install_config(configured)

    setup_flow = SetupFlow(store, _LOOP, _install_config)
    await api.init("driver.json", setup_flow)
    # ucapi 0.7.0 still requires this runtime insertion for dynamic setup metadata.
    api._driver_info["setup_data_schema"] = setup_flow.setup_data_schema()  # noqa: SLF001
    await api.set_device_state(ucapi.DeviceStates.DISCONNECTED)


if __name__ == "__main__":
    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
