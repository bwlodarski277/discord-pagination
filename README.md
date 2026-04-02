# discord-pagination

A generic, reusable pagination view for [discord.py](https://github.com/Rapptz/discord.py) bots.

## Installation

```bash
pip install "git+https://github.com/bwlodarski277/discord-pagination.git@v0.1.1"
```

For local development of this package:

```bash
pip install -e .
```

## Class hierarchy

```
BasePaginationView[T]          — abstract base (pagination state, buttons, lifecycle)
├── EmbedPaginationView[T]     — override create_embed()
│   └── FieldPaginationView    — ready-made embed-fields view
└── TextPaginationView[T]      — override format_text()
```

`PaginationView` is a **deprecated alias** for `EmbedPaginationView` and emits
a `DeprecationWarning` when subclassed or instantiated.

## Modes at a glance

| Mode | Constructor | Pages fetched |
|---|---|---|
| [Eager](#eager-mode) | `data=[...]` | All upfront |
| [Lazy snapshot](#lazy-snapshot-mode) | `total_items=N` | Once per page, then cached |
| [Lazy live](#lazy-live-mode) | `total_items=N, cache_pages=False` | On every navigation |
| [Lazy live (dynamic count)](#lazy-live-mode-dynamic-count) | `cache_pages=False` | On every navigation; count also re-fetched |

---

## Eager mode

Pass all items upfront. Use `FieldPaginationView` for the common case of embed
fields, or subclass `EmbedPaginationView[T]` for full rendering control.

### With `FieldPaginationView`

```python
from discord_pagination import Field, FieldPaginationView

fields = [Field(name=f"Item {i}", value=f"Description {i}") for i in range(30)]
view = FieldPaginationView("My list", fields, colour=discord.Colour.blurple())
await view.send(interaction)
```

### With a custom `create_embed`

```python
from discord_pagination import EmbedPaginationView

class GalleryView(EmbedPaginationView[str]):
    def create_embed(self, page_items: list[str]) -> discord.Embed:
        embed = discord.Embed(title="Gallery")
        embed.set_image(url=page_items[0])
        embed.set_footer(text=f"Page {self.current_page} of {self.total_pages}")
        return embed

urls = ["https://example.com/1.png", "https://example.com/2.png"]
view = GalleryView(urls, page_size=1)
await view.send(interaction)
```

### With plain text

```python
from discord_pagination import TextPaginationView

class LogView(TextPaginationView[str]):
    def format_text(self, page_items: list[str]) -> str:
        header = f"**Log** — Page {self.current_page}/{self.total_pages}\n"
        return header + "\n".join(page_items)

lines = open("app.log").readlines()
view = LogView(lines, page_size=20)
await view.send(interaction)
```

---

## Lazy snapshot mode

Provide `total_items` so the page count is known upfront, then implement
`load_page` to fetch items for each page on demand. Each page is fetched once
and cached for the lifetime of the view, which is suitable for most bots with a
standard interaction timeout.

```python
from discord_pagination import EmbedPaginationView

class LeaderboardView(EmbedPaginationView[Row]):
    def __init__(self, total: int) -> None:
        super().__init__(total_items=total, page_size=10)

    async def load_page(self, page: int, page_size: int) -> list[Row]:
        offset = (page - 1) * page_size
        return await db.fetch("SELECT ... LIMIT $1 OFFSET $2", page_size, offset)

    def create_embed(self, page_items: list[Row]) -> discord.Embed:
        embed = discord.Embed(title="Leaderboard")
        embed.description = "\n".join(str(row) for row in page_items)
        embed.set_footer(text=f"Page {self.current_page} of {self.total_pages}")
        return embed

total = await db.fetchval("SELECT COUNT(*) FROM ...")
view = LeaderboardView(total)
await view.send(interaction)
```

---

## Lazy live mode

Set `cache_pages=False` to re-fetch data on every navigation. Also provide a
`count_items` implementation to keep the page count accurate when the
underlying dataset may change. Suitable for long-lived views (e.g. `timeout=None`).

```python
from discord_pagination import EmbedPaginationView

class LiveLeaderboardView(EmbedPaginationView[Row]):
    def __init__(self, total: int) -> None:
        super().__init__(total_items=total, page_size=10, cache_pages=False, timeout=None)

    async def count_items(self) -> int:
        return await db.fetchval("SELECT COUNT(*) FROM ...")

    async def load_page(self, page: int, page_size: int) -> list[Row]:
        offset = (page - 1) * page_size
        return await db.fetch("SELECT ... LIMIT $1 OFFSET $2", page_size, offset)

    def create_embed(self, page_items: list[Row]) -> discord.Embed:
        embed = discord.Embed(title="Leaderboard")
        embed.description = "\n".join(str(row) for row in page_items)
        embed.set_footer(text=f"Page {self.current_page} of {self.total_pages}")
        return embed

total = await db.fetchval("SELECT COUNT(*) FROM ...")
view = LiveLeaderboardView(total)
await view.send(channel)  # sent to a channel, not an interaction
```

---

## Lazy live mode (dynamic count)

When you don't want to run a separate count query before constructing the view,
omit `total_items` entirely. You **must** override `count_items` as this is
called before every page build to keep `total_pages` accurate.

```python
from discord_pagination import EmbedPaginationView

class LiveLeaderboardView(EmbedPaginationView[Row]):
    def __init__(self) -> None:
        super().__init__(cache_pages=False, timeout=None)

    async def count_items(self) -> int:
        return await db.fetchval("SELECT COUNT(*) FROM ...")

    async def load_page(self, page: int, page_size: int) -> list[Row]:
        offset = (page - 1) * page_size
        return await db.fetch("SELECT ... LIMIT $1 OFFSET $2", page_size, offset)

    def create_embed(self, page_items: list[Row]) -> discord.Embed:
        embed = discord.Embed(title="Leaderboard")
        embed.description = "\n".join(str(row) for row in page_items)
        embed.set_footer(text=f"Page {self.current_page} of {self.total_pages}")
        return embed

view = LiveLeaderboardView()
await view.send(interaction)
```

---

## Sending

`send()` accepts either a `discord.Interaction` or any `discord.abc.Messageable`
(e.g. a `TextChannel`). Interaction responses are ephemeral by default.

```python
# Reply to a slash command (ephemeral by default)
await view.send(interaction)

# Reply publicly
await view.send(interaction, content="Here's the list:")
view = MyView(data, ephemeral=False)
await view.send(interaction)

# Send to a channel
await view.send(ctx.channel)
```
