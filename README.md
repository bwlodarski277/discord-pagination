# discord-pagination

A generic, reusable pagination view for [discord.py](https://github.com/Rapptz/discord.py) bots.

## Installation

```bash
pip install -e path/to/discord-pagination
```

## Quick start

```python
from discord_pagination import Field, FieldPaginationView

fields = [Field(name=f"Item {i}", value=f"Description {i}") for i in range(30)]
view = FieldPaginationView("My list", fields, colour=discord.Colour.blurple())
await view.send(interaction)
```

## Custom rendering

Subclass `PaginationView[T]` and implement `create_embed` for full control
over how each page is rendered:

```python
from discord_pagination import PaginationView

class ImagePaginationView(PaginationView[str]):
    def create_embed(self, page_items: list[str]) -> discord.Embed:
        embed = discord.Embed(title="Gallery")
        embed.set_image(url=page_items[0])
        embed.set_footer(text=f"Page {self.current_page} of {self.total_pages}")
        return embed

urls = ["https://example.com/1.png", "https://example.com/2.png"]
view = ImagePaginationView(urls, page_size=1)
await view.send(interaction)
```
