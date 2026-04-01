from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

import discord

T = TypeVar("T")


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
        The full list of items to paginate.
    page_size:
        Maximum items shown per page.
    ephemeral:
        Whether Interaction responses are sent as ephemeral messages.
    timeout:
        View timeout in seconds (``None`` to disable).
    """

    def __init__(
        self,
        data: list[T],
        *,
        page_size: int = 9,
        ephemeral: bool = True,
        timeout: float | None = 180,
    ) -> None:
        super().__init__(timeout=timeout)
        self.data = data
        self.page_size = page_size
        self.ephemeral = ephemeral
        self.current_page = 1
        self._message: discord.Message | None = None

    # ── Properties ──────────────────────────────────────────────

    @property
    def total_pages(self) -> int:
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

        *target* can be a :class:`discord.Interaction` (replied to
        ephemerally by default) or any :class:`~discord.abc.Messageable`
        such as a text channel.
        """
        embed = self._build_page()

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
            self._message = await target.send(content=content, embed=embed, view=self)  # type: ignore[call-overload]

    # ── Hook (override in subclasses) ───────────────────────────

    def create_embed(self, page_items: list[T]) -> discord.Embed:
        """Build the embed for the current page.

        Override this method to fully customise embed appearance.
        """
        raise NotImplementedError(
            "Subclasses must implement create_embed. "
            "Use FieldPaginationView for simple embed-field pagination."
        )

    # ── Internals ───────────────────────────────────────────────

    def _clamp_page(self) -> None:
        self.current_page = max(1, min(self.current_page, self.total_pages))

    def _get_page_items(self) -> list[T]:
        start = (self.current_page - 1) * self.page_size
        return self.data[start : start + self.page_size]

    def _build_page(self) -> discord.Embed:
        self._clamp_page()
        self._sync_buttons()
        return self.create_embed(self._get_page_items())

    def _sync_buttons(self) -> None:
        pairs = [
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
        embed = self._build_page()
        await interaction.edit_original_response(embed=embed, view=self)

    async def on_timeout(self) -> None:
        for btn in (self._btn_first, self._btn_prev, self._btn_next, self._btn_last):
            btn.disabled = True
            btn.style = discord.ButtonStyle.gray
        if self._message:
            await self._message.edit(view=self)
        await super().on_timeout()

    # ── Buttons ─────────────────────────────────────────────────

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.grey, disabled=True)
    async def _btn_first(
        self, interaction: discord.Interaction, _: discord.ui.Button,
    ) -> None:
        await interaction.response.defer()
        self.current_page = 1
        await self._edit_page(interaction)

    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.grey, disabled=True)
    async def _btn_prev(
        self, interaction: discord.Interaction, _: discord.ui.Button,
    ) -> None:
        await interaction.response.defer()
        self.current_page -= 1
        await self._edit_page(interaction)

    @discord.ui.button(emoji="⏩", style=discord.ButtonStyle.grey, disabled=True)
    async def _btn_next(
        self, interaction: discord.Interaction, _: discord.ui.Button,
    ) -> None:
        await interaction.response.defer()
        self.current_page += 1
        await self._edit_page(interaction)

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.grey, disabled=True)
    async def _btn_last(
        self, interaction: discord.Interaction, _: discord.ui.Button,
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
