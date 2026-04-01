import discord
from typing import cast

from discord_pagination.view import PaginationView


class DummyPaginationView(PaginationView[int]):
    def create_embed(self, page_items: list[int]) -> discord.Embed:
        return discord.Embed(title=", ".join(str(item) for item in page_items))


def test_total_pages_for_empty_data_is_one() -> None:
    view = DummyPaginationView([], page_size=9)
    assert view.total_pages == 1


def test_total_pages_rounds_up() -> None:
    view = DummyPaginationView(list(range(10)), page_size=9)
    assert view.total_pages == 2


def test_get_page_items_uses_current_page_window() -> None:
    view = DummyPaginationView(list(range(1, 21)), page_size=5)
    view.current_page = 3
    assert view._get_page_items() == [11, 12, 13, 14, 15]


def test_sync_buttons_disabled_on_first_page() -> None:
    view = DummyPaginationView(list(range(20)), page_size=5)
    view.current_page = 1

    view._sync_buttons()

    btn_first = cast(discord.ui.Button[discord.ui.View], view._btn_first)
    btn_prev = cast(discord.ui.Button[discord.ui.View], view._btn_prev)
    btn_next = cast(discord.ui.Button[discord.ui.View], view._btn_next)
    btn_last = cast(discord.ui.Button[discord.ui.View], view._btn_last)

    assert btn_first.disabled is True
    assert btn_prev.disabled is True
    assert btn_next.disabled is False
    assert btn_last.disabled is False
    assert btn_first.style == discord.ButtonStyle.gray
    assert btn_next.style == discord.ButtonStyle.primary


def test_sync_buttons_disabled_on_last_page() -> None:
    view = DummyPaginationView(list(range(20)), page_size=5)
    view.current_page = view.total_pages

    view._sync_buttons()

    btn_first = cast(discord.ui.Button[discord.ui.View], view._btn_first)
    btn_prev = cast(discord.ui.Button[discord.ui.View], view._btn_prev)
    btn_next = cast(discord.ui.Button[discord.ui.View], view._btn_next)
    btn_last = cast(discord.ui.Button[discord.ui.View], view._btn_last)

    assert btn_first.disabled is False
    assert btn_prev.disabled is False
    assert btn_next.disabled is True
    assert btn_last.disabled is True
    assert btn_last.style == discord.ButtonStyle.gray
    assert btn_prev.style == discord.ButtonStyle.primary
