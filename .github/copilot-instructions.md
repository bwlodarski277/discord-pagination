# discord-pagination — Copilot Instructions

## Project Overview

`discord-pagination` is a discord.py library providing reusable, generic paginated views.
The public API lives entirely in `discord_pagination/view.py`. Tests are in `tests/test_view.py`.

## Architecture

```
BasePaginationView[T]          — abstract base (ABC): state, buttons, send/edit lifecycle
├── EmbedPaginationView[T]     — abstract: implements format_page via create_embed()
│   └── FieldPaginationView    — concrete: renders Field items as embed fields
└── TextPaginationView[T]      — abstract: implements format_page via format_text()

PaginationView                 — deprecated alias for EmbedPaginationView
MessageContent                 — render-agnostic dataclass returned by format_page()
Field                          — dataclass for embed field data
```

See `README.md` for full loading-mode documentation (eager, lazy snapshot, lazy live, dynamic count).

## Build & Test

```bash
pip install -e .                          # install in editable mode
python -m pytest tests/ -v               # run tests
python -m pyright .                      # type-check (target: 0 errors, 0 warnings)
```

## Code Standards

### SOLID

- **SRP**: `BasePaginationView` owns only lifecycle/state; render intermediaries own only their format hook. Do not merge these concerns.
- **OCP**: Extend via subclass (`EmbedPaginationView`, `TextPaginationView`). Do not add render-specific logic to `BasePaginationView`.
- **LSP**: Subclasses must honour the contracts of their base — `format_page` must return a valid `MessageContent`; `load_page` must return `list[T]`.
- **ISP**: Optional hooks (`load_page`, `count_items`) intentionally raise `NotImplementedError` rather than being `@abstractmethod` — eager-mode users must not be forced to implement lazy-loading methods.
- **DIP**: `BasePaginationView` depends on `MessageContent` (an abstraction), never on `discord.Embed` or `str` directly.

### Python

- Use `@abstractmethod` on methods that every concrete subclass **must** implement.
- Use `raise NotImplementedError` for optional hooks (e.g. `load_page`, `count_items`).
- Use `dataclass(slots=True)` for data-only classes.
- `__post_init__` to enforce dataclass invariants (see `MessageContent`).
- Use `from __future__ import annotations` for forward references.
- Prefer `TypeVar`, `Generic[T]`, `TypeAlias` over `typing.Any` where possible.
- None-checks must be explicit: `if x is not None`, never `if x` when falsy values are valid.

### Typing

- All public **and** private methods must have full annotations: parameters, return types, and instance attributes.
- New TypeVars must be module-level, named clearly (e.g. `T = TypeVar("T")`).
- Use `discord.abc.Messageable` not concrete channel types when accepting send targets.
- Never use `dict` or `list` without type parameters.
- `dict[str, Any]` is acceptable only for Discord API kwargs construction.

### Docstrings

Every public method, class, and module-level symbol needs a NumPy-style docstring with:

```python
def method(self, param: int) -> str:
    """One-line summary.

    Optional extended description for non-obvious behaviour.

    Parameters
    ----------
    param:
        Description of the parameter.

    Returns
    -------
    str
        Description of the return value.

    Raises
    ------
    ValueError
        Describe when this is raised.
    """
```

Private methods (`_name`) should have a brief one-line docstring. Omit parameter sections if the signature is self-explanatory.

### Discord.py Conventions

- Button decorators use `discord.ButtonStyle.grey` (not `.gray`) for initial state.
- `discord.ButtonStyle.gray` (the US spelling) is used programmatically in `_sync_buttons` — this is intentional; both spellings are aliases.
- Always `await interaction.response.defer()` before calling `_edit_page` in button handlers.
- Expose `ephemeral` as a constructor parameter; default `True` for Interaction targets.
- `discord.ui.View` button methods must accept `interaction: discord.Interaction` and `_: <ButtonType>` as positional parameters.

## Patterns to Preserve

- `_message_kwargs(mc: MessageContent) -> dict[str, Any]` merges user-provided content with page content. Use `if p is not None` (not `if p`) when filtering string parts.
- `_build_page()` is the single choke-point before any message is sent or edited — all pre-render logic (count refresh, clamp, button sync) belongs here.
- The `total_pages` property uses ceiling division (`-(-n // d)`) — preserve this idiom.
- `_lazy` is computed once in `__init__` from `data is None` and never changed.

## What Not to Do

- Do not add render-specific logic (embeds, text formatting) to `BasePaginationView`.
- Do not change `load_page` or `count_items` to `@abstractmethod` — this would violate ISP.
- Do not use `if x:` truthiness checks where `None` and a falsy value have distinct meanings.
- Do not modify `PaginationView` beyond its role as a deprecated alias.
- Do not add Discord API calls outside of `send()`, `_edit_page()`, and `on_timeout()`.
