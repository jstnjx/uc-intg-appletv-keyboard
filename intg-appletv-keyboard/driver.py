#!/usr/bin/env python3
"""Unfolded Circle Apple TV Keyboard integration using ucapi-framework."""

from __future__ import annotations

import asyncio
import logging
import os

from ucapi_framework import BaseConfigManager, BaseIntegrationDriver, get_config_path

from apple_tv import AppleTVKeyboardDevice
from config import AppleTVConfig
from discovery import AppleTVDiscovery
from media_player import AppleTVKeyboardMediaPlayer
from setup_flow import AppleTVSetupFlow

_LOG = logging.getLogger("driver")


async def main() -> None:
    """Start the integration driver."""
    logging.basicConfig(
        level=os.getenv("UC_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    )

    driver = BaseIntegrationDriver(
        device_class=AppleTVKeyboardDevice,
        entity_classes=[AppleTVKeyboardMediaPlayer],
        driver_id="appletv_keyboard",
    )
    driver.config_manager = BaseConfigManager(
        get_config_path(driver.api.config_dir_path),
        driver.on_device_added,
        driver.on_device_removed,
        config_class=AppleTVConfig,
    )

    await driver.register_all_device_instances()

    discovery = AppleTVDiscovery(timeout=5)
    setup_handler = AppleTVSetupFlow.create_handler(
        driver,
        discovery=discovery,
    )
    await driver.api.init("driver.json", setup_handler)

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
