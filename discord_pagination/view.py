from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

import discord

T = TypeVar("T")
ViewButton: TypeAlias = discord.ui.Button[discord.ui.View]


@dataclass(slots=True)
class Field:
    """A single embed field."""

    name: str
    value: str
    inline: bool = True


class PaginationView(discord.ui.View, Generic[T]):
    """Generic paginated embed view for discord.py.

    Subclass this and implement :meth:`create_embed` to control how each page
    is rendered.  For the common case of embed fields, use the ready-made
    :class:`FieldPaginationView` instead.

    Parameters
    ----------
    data:
        The full list of items to paginate.  Cannot be combined with
        *total_items*.  When neither *data* nor *total_items* is given,
        *cache_pages* must be ``False`` and :meth:`count_items` must be
        overridden.
    total_items:
        Total number of items across all pages.  Use this together with
        :meth:`load_page` to fetch data lazily.  Required when *data* is
        not provided and *cache_pages* is ``True``.  When *cache_pages*
        is ``False``, this can be omitted and :meth:`count_items` will
        provide the count on every page build.
    cache_pages:
        When ``True`` (the default), each page returned by
        :meth:`load_page` is cached for the lifetime of the view
        (snapshot model).  When ``False``, :meth:`load_page` is called
        on every navigation and :meth:`count_items` is called before
        each page build so that :attr:`total_pages` stays accurate
        (live model).  Only meaningful in lazy-loading mode.
    page_size:
        Maximum items shown per page.
    ephemeral:
        Whether Interaction responses are sent as ephemeral messages.
    timeout:
        View timeout in seconds (``None`` to disable).
    """

    def __init__(
        self,
        data: list[T] | None = None,
        *,
        total_items: int | None = None,
        cache_pages: bool = True,
        page_size: int = 9,
        ephemeral: bool = True,
        timeout: float | None = 180,
    ) -> None:
        _lazy = data is None
        if _lazy and total_items is None and cache_pages:
            raise ValueError(
                "'total_items' is required in lazy mode when 'cache_pages=True'. "
                "Either provide 'total_items' or set 'cache_pages=False'."
            )
        if data is not None and total_items is not None:
            raise ValueError("'data' and 'total_items' are mutually exclusive.")
        super().__init__(timeout=timeout)
        self.data: list[T] = data if data is not None else []
        self._lazy = _lazy
        self._total_items = total_items if total_items is not None else 0
        self._total_items_provided = total_items is not None
        self.cache_pages = cache_pages
        self._page_cache: dict[int, list[T]] = {}
        self.page_size = page_size
        self.ephemeral = ephemeral
        self.current_page = 1
        self._message: discord.Message | None = None

    # ── Properties ──────────────────────────────────────────────

    @property
    def total_pages(self) -> int:
        if self._lazy:
            return max(1, -(-self._total_items // self.page_size))
        return max(1, -(-len(self.data) // self.page_size))

    @property
    def _should_paginate(self) -> bool:
        return self.total_pages > 1

    # ── Public API ──────────────────────────────────────────────

    async def send(
        self,
        target: discord.Interaction | discord.abc.Messageable,
        content: str | None = None,
    ) -> None:
        """Send the paginated view to *target*.

        Parameters
        ----------
        target:
            A :class:`discord.Interaction` (replied to ephemerally by
            default) or any :class:`~discord.abc.Messageable` such as
            a text channel.
        content:
            Optional text to send alongside the embed.
        """
        embed = await self._build_page()

        if not self._should_paginate:
            self.stop()
            if isinstance(target, discord.Interaction):
                await target.response.send_message(
                    content=content, embed=embed, ephemeral=self.ephemeral,
                )
            else:
                await target.send(content=content, embed=embed)
            return

        if isinstance(target, discord.Interaction):
            await target.response.send_message(
                content=content, embed=embed, view=self, ephemeral=self.ephemeral,
            )
            self._message = await target.original_response()
        else:
            self._message = await target.send(content=content, embed=embed, view=self)

    # ── Hooks (override in subclasses) ──────────────────────────

    def create_embed(self, page_items: list[T]) -> discord.Embed:
        """Build the embed for the current page.

        Override this method to fully customise embed appearance.

        Parameters
        ----------
        page_items:
            Items for the current page.

        Returns
        -------
        discord.Embed
            The rendered embed.
        """
        raise NotImplementedError(
            "Subclasses must implement create_embed. "
            "Use FieldPaginationView for simple embed-field pagination."
        )

    async def load_page(self, page: int, page_size: int) -> list[T]:
        """Fetch items for a single page on demand.

        Override this method when using lazy loading (i.e. when *data*
        is not provided to the constructor).  Results are cached per
        page when *cache_pages* is ``True``; otherwise this is called
        on every navigation.

        Parameters
        ----------
        page:
            The 1-indexed page number.
        page_size:
            Maximum items per page.

        Returns
        -------
        list[T]
            Items for this page, which is then passed to :meth:`create_embed`.
        """
        raise NotImplementedError(
            "Subclasses must implement load_page when using lazy loading."
        )

    async def count_items(self) -> int:
        """Return the current total number of items.

        Override this method to provide a dynamic count (e.g., a
        database query).  Only called when *cache_pages* is ``False``.
        By default, returns the *total_items* value passed to the
        constructor.  If *total_items* was not provided, this method
        must be overridden.

        Returns
        -------
        int
            Total number of items across all pages.
        """
        if not self._total_items_provided:
            raise NotImplementedError(
                "Subclasses must implement count_items when using lazy loading "
                "without providing 'total_items'."
            )
        return self._total_items

    # ── Internals ───────────────────────────────────────────────

    def _clamp_page(self) -> None:
        """Clamp :attr:`current_page` to valid range [1, total_pages]."""
        self.current_page = max(1, min(self.current_page, self.total_pages))

    async def _get_page_items(self) -> list[T]:
        """Fetch items for the current page, using cache or load_page."""
        if self._lazy:
            if self.cache_pages and self.current_page in self._page_cache:
                return self._page_cache[self.current_page]
            items = await self.load_page(self.current_page, self.page_size)
            if self.cache_pages:
                self._page_cache[self.current_page] = items
            return items
        start = (self.current_page - 1) * self.page_size
        return self.data[start : start + self.page_size]

    async def _build_page(self) -> discord.Embed:
        """Build and return the embed for the current page.

        Updates item count if using live mode, clamps page, syncs buttons.
        """
        if self._lazy and not self.cache_pages:
            self._total_items = await self.count_items()
        self._clamp_page()
        self._sync_buttons()
        return self.create_embed(await self._get_page_items())

    def _sync_buttons(self) -> None:
        """Update button enabled/disabled state based on current page."""
        pairs: list[tuple[ViewButton, bool]] = [
            (self._btn_first, self.current_page <= 1),
            (self._btn_prev, self.current_page <= 1),
            (self._btn_next, self.current_page >= self.total_pages),
            (self._btn_last, self.current_page >= self.total_pages),
        ]
        for button, disabled in pairs:
            button.disabled = disabled
            button.style = (
                discord.ButtonStyle.gray if disabled else discord.ButtonStyle.primary
            )

    async def _edit_page(self, interaction: discord.Interaction) -> None:
        """Update the message to show the current page."""
        embed = await self._build_page()
        await interaction.edit_original_response(embed=embed, view=self)

    async def on_timeout(self) -> None:
        """Disable all buttons when view times out."""
        buttons: tuple[ViewButton, ...] = (
            self._btn_first,
            self._btn_prev,
            self._btn_next,
            self._btn_last
        )
        
        for btn in buttons:
            btn.disabled = True
            btn.style = discord.ButtonStyle.gray
        if self._message:
            await self._message.edit(view=self)
        await super().on_timeout()

    # ── Buttons ─────────────────────────────────────────────────

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.grey, disabled=True)
    async def _btn_first(
        self, interaction: discord.Interaction, _: ViewButton,
    ) -> None:
        await interaction.response.defer()
        self.current_page = 1
        await self._edit_page(interaction)

    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.grey, disabled=True)
    async def _btn_prev(
        self, interaction: discord.Interaction, _: ViewButton,
    ) -> None:
        await interaction.response.defer()
        self.current_page -= 1
        await self._edit_page(interaction)

    @discord.ui.button(emoji="⏩", style=discord.ButtonStyle.grey, disabled=True)
    async def _btn_next(
        self, interaction: discord.Interaction, _: ViewButton,
    ) -> None:
        await interaction.response.defer()
        self.current_page += 1
        await self._edit_page(interaction)

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.grey, disabled=True)
    async def _btn_last(
        self, interaction: discord.Interaction, _: ViewButton,
    ) -> None:
        await interaction.response.defer()
        self.current_page = self.total_pages
        await self._edit_page(interaction)


class FieldPaginationView(PaginationView[Field]):
    """Paginated view that renders :class:`Field` items as embed fields.

    This covers the most common Discord pagination pattern.  For fully custom
    rendering, subclass :class:`PaginationView` directly.

    Parameters
    ----------
    title:
        The embed title shown on every page.
    data:
        List of :class:`Field` items to paginate.
    colour:
        Sidebar colour of the embed (``None`` for the default).
    page_size:
        Maximum fields shown per page (capped at 25 by Discord).
    ephemeral:
        Whether Interaction responses are sent as ephemeral messages.
    timeout:
        View timeout in seconds (``None`` to disable).
    """

    def __init__(
        self,
        title: str,
        data: list[Field],
        *,
        colour: discord.Colour | None = None,
        page_size: int = 9,
        ephemeral: bool = True,
        timeout: float | None = 180,
    ) -> None:
        super().__init__(data, page_size=page_size, ephemeral=ephemeral, timeout=timeout)
        self.title = title
        self.colour = colour

    def create_embed(self, page_items: list[Field]) -> discord.Embed:
        embed = discord.Embed(title=self.title, colour=self.colour)
        for field in page_items:
            embed.add_field(name=field.name, value=field.value, inline=field.inline)
        embed.set_footer(text=f"Page {self.current_page} of {self.total_pages}")
        return embed
