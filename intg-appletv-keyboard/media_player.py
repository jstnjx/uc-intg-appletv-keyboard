"""UC media-player entity used as a text-entry bridge."""

from __future__ import annotations

from typing_extensions import override
from ucapi import StatusCodes
from ucapi.api_definitions import Pagination
from ucapi import media_player as mp
from pyatv.const import KeyboardFocusState

from apple_tv import AppleTVKeyboardClient


class AppleTVKeyboardMediaPlayer(mp.MediaPlayer):
    """Media player whose media-search query is forwarded to tvOS keyboard input."""

    def __init__(self, client: AppleTVKeyboardClient):
        self.client = client
        super().__init__(
            identifier="appletv_keyboard",
            name=f"Apple TV Keyboard - {client.config.name}",
            features=[mp.Features.BROWSE_MEDIA, mp.Features.SEARCH_MEDIA],
            attributes={mp.Attributes.STATE: mp.States.UNKNOWN},
            device_class=mp.DeviceClasses.STREAMING_BOX,
            icon="uc:integration",
            description="Open Browse, tap Search and type to send text to the focused Apple TV field.",
        )

    def _pagination(self, page: int, limit: int, count: int) -> Pagination:
        return Pagination(page=page, limit=limit, count=count)

    @override
    async def browse(self, options: mp.BrowseOptions) -> mp.BrowseResults | StatusCodes:
        focus = await self.client.current_focus()
        if not self.client.connected:
            title = "Apple TV unavailable"
            subtitle = "Check that the Apple TV is online and reachable."
            state = mp.States.UNAVAILABLE
        elif focus == KeyboardFocusState.Focused:
            title = "Keyboard ready"
            subtitle = "Tap Search above and type. The full text is sent to Apple TV."
            state = mp.States.ON
        elif focus == KeyboardFocusState.Unfocused:
            title = "Open a text field on Apple TV"
            subtitle = "Search input is only forwarded while tvOS keyboard focus is active."
            state = mp.States.ON
        else:
            title = "Waiting for keyboard focus"
            subtitle = "Open a search or text field on Apple TV, then type here."
            state = mp.States.UNKNOWN

        self.update_attributes({mp.Attributes.STATE: state})
        status = mp.BrowseMediaItem(
            media_id="keyboard-status",
            title=title,
            subtitle=subtitle,
            media_class=mp.MediaClass.DIRECTORY,
            media_type="keyboard_status",
            can_browse=False,
            can_play=False,
            can_search=False,
        )
        root = mp.BrowseMediaItem(
            media_id="keyboard-root",
            title="Apple TV Keyboard",
            media_class=mp.MediaClass.DIRECTORY,
            media_type="keyboard",
            can_browse=False,
            can_play=False,
            can_search=True,
            items=[status],
        )
        return mp.BrowseResults(
            media=root,
            pagination=self._pagination(options.paging.page, options.paging.limit, 1),
        )

    @override
    async def search(self, options: mp.SearchOptions) -> mp.SearchResults | StatusCodes:
        query = options.query.strip()
        if not query:
            return mp.SearchResults(
                media=[],
                pagination=self._pagination(options.paging.page, options.paging.limit, 0),
            )

        ok, message = await self.client.set_text(query)
        if ok:
            self.update_attributes({mp.Attributes.STATE: mp.States.ON})
            item = mp.SearchMediaItem(
                media_id="keyboard-sent",
                title=f"Sent: {query[:220]}",
                subtitle=message,
                media_class=mp.MediaClass.DIRECTORY,
                media_type="keyboard_status",
                can_browse=False,
                can_play=False,
                can_search=False,
            )
        else:
            self.update_attributes(
                {
                    mp.Attributes.STATE: (
                        mp.States.ON if self.client.connected else mp.States.UNAVAILABLE
                    )
                }
            )
            item = mp.SearchMediaItem(
                media_id="keyboard-not-sent",
                title="Text not sent",
                subtitle=message,
                media_class=mp.MediaClass.DIRECTORY,
                media_type="keyboard_status",
                can_browse=False,
                can_play=False,
                can_search=False,
            )

        return mp.SearchResults(
            media=[item],
            pagination=self._pagination(options.paging.page, options.paging.limit, 1),
        )
