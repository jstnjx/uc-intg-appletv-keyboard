# Apple TV Keyboard for Unfolded Circle Remote Two / Remote 3

A purpose-built workaround for the lack of a generic keyboard entity/component in the UC Remote UI.

The integration exposes one **media-player** entity with **Browse Media** and **Search Media** support. The Remote's existing media-browser search field becomes the text-entry UI. Every non-empty search request is forwarded to the selected Apple TV's currently focused tvOS text field through pyatv's Companion keyboard API.

## Behaviour

1. Install / run the integration.
2. During setup, discover or enter the IP address of an Apple TV.
3. Select the Apple TV and enter the Companion PIN shown on the TV.
4. Add **Apple TV Keyboard - <device name>** to the Remote.
5. On Apple TV, navigate to any screen that has a text/search field and give that field focus.
6. On the UC Remote, open the integration media player -> **Browse** -> **Search**.
7. Type text. After the Remote's normal search debounce (or when Enter is pressed), the full string replaces the focused Apple TV text field.

The integration deliberately uses `text_set`, not `text_append`: the UC media browser sends the complete search query each time, so replacing the tvOS text avoids duplicated text after repeated/debounced requests.

## Focus protection

Text is only sent when pyatv reports `KeyboardFocusState.Focused`. If tvOS does not currently have a text field focused, the search result says **Text not sent** instead of blindly injecting input.

The client reads the live focus property for every send in addition to registering the pyatv focus listener. This gives the integration a second source of truth if a focus callback is missed.

## Local development

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
UC_CONFIG_HOME=./config python intg-appletv-keyboard/driver.py
```

The driver listens on the normal ucapi integration port (9090 unless overridden with `UC_INTEGRATION_HTTP_PORT`).

## Build for Remote Two / Remote 3

```bash
./build.sh
```

This uses Unfolded Circle's current Python 3.11 aarch64 PyInstaller image, matching the approach used by the official Apple TV integration.

For a custom-integration release package, place the compiled `dist/intg-appletv-keyboard/` payload together with `driver.json` in the archive layout required by the Remote custom integration installer.

## Dependencies

- `ucapi==0.7.0` - includes Browse/Search Media support.
- `pyatv==0.18.0` - same version currently pinned by the official UC Apple TV integration.
- Companion pairing only. AirPlay pairing is intentionally not required because keyboard input is a Companion feature.

## Current limitation inherited from the UC media-browser UI

The Remote does not issue a `search_media` request for an empty query. Therefore clearing the UC search field does **not** clear the Apple TV field. Any subsequent non-empty search replaces the full Apple TV text, so normal editing/replacement still works.
