import pytest
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


@pytest.mark.asyncio
async def test_get_page_items_uses_current_page_window() -> None:
    view = DummyPaginationView(list(range(1, 21)), page_size=5)
    view.current_page = 3
    assert await view._get_page_items() == [11, 12, 13, 14, 15]


@pytest.mark.asyncio
async def test_load_page_called_once_per_page() -> None:
    call_log: list[tuple[int, int]] = []

    class LazyView(PaginationView[int]):
        def create_embed(self, page_items: list[int]) -> discord.Embed:
            return discord.Embed()

        async def load_page(self, page: int, page_size: int) -> list[int]:
            call_log.append((page, page_size))
            start = (page - 1) * page_size
            return list(range(start + 1, start + page_size + 1))

    view = LazyView(total_items=20, page_size=5)
    assert view.total_pages == 4

    result = await view._get_page_items()  # page 1, first fetch
    assert result == [1, 2, 3, 4, 5]
    assert call_log == [(1, 5)]

    await view._get_page_items()  # page 1 again — should use cache
    assert call_log == [(1, 5)]  # load_page not called a second time

    view.current_page = 2
    result = await view._get_page_items()
    assert result == [6, 7, 8, 9, 10]
    assert len(call_log) == 2


@pytest.mark.asyncio
async def test_cache_pages_false_always_calls_load_page() -> None:
    call_count = 0

    class LazyView(PaginationView[int]):
        def create_embed(self, page_items: list[int]) -> discord.Embed:
            return discord.Embed()

        async def load_page(self, page: int, page_size: int) -> list[int]:
            nonlocal call_count
            call_count += 1
            return [1, 2, 3]

    view = LazyView(total_items=3, page_size=5, cache_pages=False)

    await view._get_page_items()
    await view._get_page_items()
    assert call_count == 2  # called both times, no caching


@pytest.mark.asyncio
async def test_count_items_refreshes_total_when_not_caching() -> None:
    current_count = 10

    class LazyView(PaginationView[int]):
        def create_embed(self, page_items: list[int]) -> discord.Embed:
            return discord.Embed()

        async def load_page(self, page: int, page_size: int) -> list[int]:
            return []

        async def count_items(self) -> int:
            return current_count

    view = LazyView(total_items=10, page_size=5, cache_pages=False)
    assert view.total_pages == 2

    current_count = 20
    await view._build_page()
    assert view.total_pages == 4


@pytest.mark.asyncio
async def test_count_items_not_called_when_caching() -> None:
    """count_items should not be called when cache_pages=True."""
    called = False

    class LazyView(PaginationView[int]):
        def create_embed(self, page_items: list[int]) -> discord.Embed:
            return discord.Embed()

        async def load_page(self, page: int, page_size: int) -> list[int]:
            return [1, 2]

        async def count_items(self) -> int:
            nonlocal called
            called = True
            return 999

    view = LazyView(total_items=10, page_size=5)
    await view._build_page()
    assert not called
    assert view.total_pages == 2  # unchanged


def test_missing_data_and_total_items_raises() -> None:
    with pytest.raises(ValueError, match="'total_items' is required"):
        DummyPaginationView()


def test_data_and_total_items_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        DummyPaginationView([1, 2, 3], total_items=3)


@pytest.mark.asyncio
async def test_cache_pages_false_does_not_require_total_items() -> None:
    """Live mode should not require total_items upfront."""
    class LazyView(PaginationView[int]):
        def create_embed(self, page_items: list[int]) -> discord.Embed:
            return discord.Embed()

        async def load_page(self, page: int, page_size: int) -> list[int]:
            return [1, 2, 3]

        async def count_items(self) -> int:
            return 3

    view = LazyView(cache_pages=False)  # no total_items
    await view._build_page()
    assert view.total_pages == 1


@pytest.mark.asyncio
async def test_count_items_not_overridden_without_total_items_raises() -> None:
    """Forgetting to override count_items without total_items should error."""
    class LazyView(PaginationView[int]):
        def create_embed(self, page_items: list[int]) -> discord.Embed:
            return discord.Embed()

        async def load_page(self, page: int, page_size: int) -> list[int]:
            return [1, 2, 3]

    view = LazyView(cache_pages=False)  # no total_items, no count_items override
    with pytest.raises(NotImplementedError, match="count_items"):
        await view._build_page()


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
