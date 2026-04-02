import warnings

import pytest
import discord

from discord_pagination.view import (
    BasePaginationView,
    EmbedPaginationView,
    MessageContent,
    PaginationView,
    TextPaginationView,
)


class DummyEmbedView(EmbedPaginationView[int]):
    def create_embed(self, page_items: list[int]) -> discord.Embed:
        return discord.Embed(title=", ".join(str(item) for item in page_items))


class DummyTextView(TextPaginationView[int]):
    def format_text(self, page_items: list[int]) -> str:
        return ", ".join(str(item) for item in page_items)


# ── EmbedPaginationView tests ──────────────────────────────────


def test_total_pages_for_empty_data_is_one() -> None:
    view = DummyEmbedView([], page_size=9)
    assert view.total_pages == 1


def test_total_pages_rounds_up() -> None:
    view = DummyEmbedView(list(range(10)), page_size=9)
    assert view.total_pages == 2


@pytest.mark.asyncio
async def test_get_page_items_uses_current_page_window() -> None:
    view = DummyEmbedView(list(range(1, 21)), page_size=5)
    view.current_page = 3
    assert await view._get_page_items() == [11, 12, 13, 14, 15]


@pytest.mark.asyncio
async def test_load_page_called_once_per_page() -> None:
    call_log: list[tuple[int, int]] = []

    class LazyView(EmbedPaginationView[int]):
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

    await view._get_page_items()  # page 1 again - should use cache
    assert call_log == [(1, 5)]  # load_page not called a second time

    view.current_page = 2
    result = await view._get_page_items()
    assert result == [6, 7, 8, 9, 10]
    assert len(call_log) == 2


@pytest.mark.asyncio
async def test_cache_pages_false_always_calls_load_page() -> None:
    call_count = 0

    class LazyView(EmbedPaginationView[int]):
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

    class LazyView(EmbedPaginationView[int]):
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

    class LazyView(EmbedPaginationView[int]):
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
        DummyEmbedView()


def test_data_and_total_items_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        DummyEmbedView([1, 2, 3], total_items=3)


@pytest.mark.asyncio
async def test_cache_pages_false_does_not_require_total_items() -> None:
    """Live mode should not require total_items upfront."""
    class LazyView(EmbedPaginationView[int]):
        def create_embed(self, page_items: list[int]) -> discord.Embed:
            return discord.Embed()

        async def load_page(self, page: int, page_size: int) -> list[int]:
            return [1, 2, 3]

        async def count_items(self) -> int:
            return 3

    view = LazyView(cache_pages=False)  # no total_items
    await view._build_page()
    assert view.total_pages == 1


# ── TextPaginationView tests ───────────────────────────────────


def test_text_view_total_pages() -> None:
    view = DummyTextView(list(range(10)), page_size=3)
    assert view.total_pages == 4


@pytest.mark.asyncio
async def test_text_view_format_page_returns_message_content() -> None:
    view = DummyTextView(list(range(1, 4)), page_size=3)
    mc = await view._build_page()
    assert isinstance(mc, MessageContent)
    assert mc.content == "1, 2, 3"
    assert mc.embed is None


@pytest.mark.asyncio
async def test_text_view_pagination_window() -> None:
    view = DummyTextView(list(range(1, 11)), page_size=3)
    view.current_page = 2
    mc = view.format_page(await view._get_page_items())
    assert mc.content == "4, 5, 6"


@pytest.mark.asyncio
async def test_text_view_lazy_loading() -> None:
    class LazyTextView(TextPaginationView[int]):
        def format_text(self, page_items: list[int]) -> str:
            return ", ".join(str(i) for i in page_items)

        async def load_page(self, page: int, page_size: int) -> list[int]:
            start = (page - 1) * page_size
            return list(range(start + 1, start + page_size + 1))

    view = LazyTextView(total_items=15, page_size=5)
    mc = await view._build_page()
    assert mc.content == "1, 2, 3, 4, 5"

    view.current_page = 3
    mc = await view._build_page()
    assert mc.content == "11, 12, 13, 14, 15"


# ── MessageContent merging tests ───────────────────────────────


def test_message_kwargs_embed_only() -> None:
    embed = discord.Embed(title="test")
    view = DummyEmbedView([1, 2, 3], page_size=9)
    mc = MessageContent(embed=embed)
    kwargs = view._message_kwargs(mc)
    assert kwargs == {"embed": embed}


def test_message_kwargs_text_only() -> None:
    view = DummyTextView([1, 2, 3], page_size=9)
    mc = MessageContent(content="hello")
    kwargs = view._message_kwargs(mc)
    assert kwargs == {"content": "hello"}


def test_message_kwargs_merges_user_content_and_page_content() -> None:
    view = DummyTextView([1, 2, 3], page_size=9)
    view._user_content = "header"
    mc = MessageContent(content="page text")
    kwargs = view._message_kwargs(mc)
    assert kwargs == {"content": "header\n\npage text"}


def test_message_kwargs_user_content_with_embed() -> None:
    embed = discord.Embed(title="test")
    view = DummyEmbedView([1, 2, 3], page_size=9)
    view._user_content = "Note:"
    mc = MessageContent(embed=embed)
    kwargs = view._message_kwargs(mc)
    assert kwargs == {"content": "Note:", "embed": embed}


def test_message_kwargs_empty_string_content_is_included() -> None:
    """Empty string is a valid value and must not be silently dropped."""
    view = DummyTextView([1, 2, 3], page_size=9)
    mc = MessageContent(content="")
    kwargs = view._message_kwargs(mc)
    assert kwargs == {"content": ""}


def test_message_content_requires_at_least_one_field() -> None:
    with pytest.raises(ValueError, match="at least one"):
        MessageContent()


# ── Deprecated PaginationView alias ────────────────────────────


def test_pagination_view_subclass_emits_deprecation_warning() -> None:
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        class OldStyleView(PaginationView[int]):
            def create_embed(self, page_items: list[int]) -> discord.Embed:
                return discord.Embed()

    assert len(w) == 1
    assert issubclass(w[0].category, DeprecationWarning)
    assert "deprecated" in str(w[0].message).lower()


def test_pagination_view_instantiation_emits_deprecation_warning() -> None:
    # Suppress the subclass warning first
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")

        class OldStyleView(PaginationView[int]):
            def create_embed(self, page_items: list[int]) -> discord.Embed:
                return discord.Embed()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        OldStyleView([1, 2, 3], page_size=3)

    assert any(issubclass(warning.category, DeprecationWarning) for warning in w)


# ── Abstract instantiation tests ───────────────────────────────


def test_base_pagination_view_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        BasePaginationView([1, 2, 3])  # type: ignore[abstract]


def test_embed_pagination_view_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        EmbedPaginationView([1, 2, 3])  # type: ignore[abstract]


def test_text_pagination_view_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        TextPaginationView([1, 2, 3])  # type: ignore[abstract]


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
    view = DummyEmbedView(list(range(20)), page_size=5)
    view.current_page = 1

    view._sync_buttons()

    assert view._btn_first.disabled is True
    assert view._btn_prev.disabled is True
    assert view._btn_next.disabled is False
    assert view._btn_last.disabled is False
    assert view._btn_first.style == discord.ButtonStyle.gray
    assert view._btn_next.style == discord.ButtonStyle.primary


def test_sync_buttons_disabled_on_last_page() -> None:
    view = DummyEmbedView(list(range(20)), page_size=5)
    view.current_page = view.total_pages

    view._sync_buttons()

    assert view._btn_first.disabled is False
    assert view._btn_prev.disabled is False
    assert view._btn_next.disabled is True
    assert view._btn_last.disabled is True
    assert view._btn_last.style == discord.ButtonStyle.gray
    assert view._btn_prev.style == discord.ButtonStyle.primary
