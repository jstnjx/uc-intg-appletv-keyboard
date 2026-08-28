# Apple TV Keyboard for Unfolded Circle Remote Two / Remote 3

Apple TV Keyboard turns the existing **Media Browser → Search** text field on an Unfolded Circle Remote into a keyboard for tvOS.

The integration is built on [`ucapi-framework`](https://github.com/JackJPowell/ucapi-framework). The framework owns setup routing, typed configuration persistence, device lifecycle, reconnection, entity registration and Remote subscription handling. `pyatv` is used only for Apple TV Companion discovery, pairing, keyboard-focus detection and text entry.

## How it works

1. Install the custom integration.
2. Run setup and continue past the framework restore prompt.
3. Discover an Apple TV or choose manual entry and enter its IP address.
4. Select the Apple TV.
5. Enter the Companion PIN shown by tvOS.
6. Add the **Apple TV Keyboard - <name>** media-player entity to the Remote.
7. Focus any text/search field on Apple TV.
8. Open the keyboard entity's **Browse → Search** screen on the Remote and type.

Every non-empty `search_media` query is forwarded with:

```python
await apple_tv.keyboard.text_set(query)
```

`text_set()` is intentional: the UC media browser sends the complete search query after its debounce, so replacing the tvOS field avoids duplicated characters.

## Focus protection

Text is only sent while `pyatv` reports:

```python
KeyboardFocusState.Focused
```

If no tvOS text field has focus, the integration returns **Text not sent** rather than injecting text blindly.

Keyboard focus changes are pushed into the framework device coordinator and reflected in the media-player state.

## Architecture

- `BaseIntegrationDriver` — Remote lifecycle, subscriptions and entity registration.
- `BaseConfigManager` — typed `AppleTVConfig` persistence plus framework backup/restore.
- `BaseSetupFlow` — discovery/manual setup and reconfiguration.
- Additional framework setup screen — Companion PIN entry.
- `ExternalClientDevice` — wraps the persistent `pyatv` Companion connection and watchdog/reconnect behavior.
- `MediaPlayerEntity` — exposes `BROWSE_MEDIA` and `SEARCH_MEDIA`.
- `BaseDiscovery` — adapts `pyatv.scan()` to framework `DiscoveredDevice` objects.

The setup schema is deliberately present **statically in `driver.json`**. Core must see it when the integration metadata is loaded; adding it after `IntegrationAPI.init()` is too late for custom-integration setup.

## Dependencies

- `ucapi-framework==1.9.6`
- `ucapi==0.7.0`
- `pyatv==0.18.0`
- Python 3.11+

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
UC_CONFIG_HOME=./config python intg-appletv-keyboard/driver.py
```

## Build

```bash
./build.sh
```

The release workflow builds a self-contained aarch64 bundle for Remote Two / Remote 3 and packages it using the standard custom-integration layout.

## Known UC media-browser limitation

The Remote does not send `search_media` for an empty query, so clearing the Remote search box alone does not clear the current Apple TV field. The next non-empty query replaces the entire tvOS field.
