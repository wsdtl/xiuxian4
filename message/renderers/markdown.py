"""公共 Document 到 Markdown 的结构渲染。"""

from __future__ import annotations

from collections.abc import Callable

from ..icons import icon_for
from ..schema import (
    CommandLink,
    Document,
    Emphasis,
    FieldSeparator,
    HeaderBlock,
    InlineBlock,
    Link,
    NoteBlock,
    RichText,
    SectionBlock,
    Strong,
    Text,
)


CommandRenderer = Callable[[CommandLink], str]


def render_markdown(document: Document, *, command_renderer: CommandRenderer | None = None) -> str:
    """按统一标题、正文和附加区边界渲染 Markdown。"""

    lines: list[str] = []
    previous_block = None
    for block in document.blocks:
        if isinstance(block, HeaderBlock):
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(f"**{_render_rich(block.content, command_renderer)}**")
            previous_block = block
            continue

        should_separate = isinstance(previous_block, (InlineBlock, SectionBlock, NoteBlock)) and not (
            isinstance(previous_block, InlineBlock) and isinstance(block, InlineBlock)
        )
        if should_separate and lines and lines[-1] != "> ":
            lines.append("> ")

        if isinstance(block, InlineBlock):
            title = _title(block.title, block.icon, command_renderer)
            content = _render_rich(block.content, command_renderer)
            lines.append(f"> {title}: {content}".rstrip())
        elif isinstance(block, SectionBlock):
            lines.append(f"> {_title(block.title, block.icon, command_renderer)}".rstrip())
            for line in block.lines:
                value = _render_rich(line, command_renderer)
                lines.append("> >" if not value else f"> > {value}")
        elif isinstance(block, NoteBlock):
            for line in block.lines:
                value = _render_rich(line, command_renderer)
                lines.append(">" if not value else f"> {value}")
        previous_block = block

    return "\n".join(lines).strip()


def render_rich_markdown(value: RichText, *, command_renderer: CommandRenderer | None = None) -> str:
    """渲染一段 RichText，供协议驱动构造内联能力。"""

    return _render_rich(value, command_renderer)


def _title(value: RichText, icon: str, command_renderer: CommandRenderer | None) -> str:
    title = _render_rich(value, command_renderer)
    display_icon = icon_for(icon)
    return f"{display_icon} {title}".strip()


def _render_rich(value: RichText, command_renderer: CommandRenderer | None) -> str:
    parts: list[str] = []
    for span in value:
        if isinstance(span, Text):
            parts.append(_escape(span.value))
        elif isinstance(span, Emphasis):
            parts.append(f"_{_render_rich(span.value, command_renderer)}_")
        elif isinstance(span, Strong):
            parts.append(f"**{_render_rich(span.value, command_renderer)}**")
        elif isinstance(span, Link):
            parts.append(f"[{_render_rich(span.label, command_renderer)}]({_escape_url(span.url)})")
        elif isinstance(span, CommandLink):
            parts.append(command_renderer(span) if command_renderer else _render_rich(span.label, None))
        elif isinstance(span, FieldSeparator):
            parts.append("&nbsp;|&nbsp;")
    return "".join(parts)


def _escape(value: object) -> str:
    text = str(value or "")
    for token in ("\\", "`", "*", "_", "[", "]"):
        text = text.replace(token, f"\\{token}")
    return text.replace("\r", " ").replace("\n", " ")


def _escape_url(value: object) -> str:
    return str(value or "").strip().replace(" ", "%20").replace(")", "%29")
