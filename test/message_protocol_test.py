"""跨驱动消息语义协议测试。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from launch.adapter.local import LocalEventHandler, dispatch
from launch.adapter.local.manager import manager as local_manager
from launch.adapter import manager as public_manager
from launch.adapter.qq.render import render_qq_message
from message import Action, M, RenderedMessage
from message.renderers.markdown import render_markdown
from message.renderers.plain_text import render_plain_text


def main() -> None:
    message = _sample_message()
    _assert_markdown_shape(message)
    _assert_qq_translation(message)
    _assert_strict_structure()
    asyncio.run(_assert_local_translation(message))
    asyncio.run(_assert_public_manager_rejects_native_payload())
    print("cross-adapter message protocol test passed")


def _sample_message():
    return (
        M.document()
        .header("天易 斗法胜手 Lv49")
        .inline_section("天机", "灵签已开", icon="system")
        .inline_section("提醒", "灵签中奖", icon="notice")
        .section("技能书", icon="skill")
        .row(("数量", 2), ("状态", "可用"))
        .item(1, "乾坤书")
        .note("请谨慎操作")
        .actions(
            (
                Action("view", "查看", "查看 乾坤书", behavior="send"),
                Action("fill", "回填", "查看 ", behavior="fill", style="secondary"),
                Action("callback", "回调", "测试 回调", behavior="callback"),
            )
        )
        .build()
    )


def _assert_markdown_shape(message) -> None:
    content = render_markdown(message.document)
    assert content == "\n".join(
        [
            "**天易 斗法胜手 Lv49**",
            "> ✨ 天机: 灵签已开",
            "> 📌 提醒: 灵签中奖",
            "> ",
            "> 📘 技能书",
            "> > 数量: _2_&nbsp;|&nbsp;状态: _可用_",
            "> > \\[1\\] 乾坤书",
            "> ",
            "> 请谨慎操作",
        ]
    )
    plain = render_plain_text(message.document)
    assert "数量: 2 | 状态: 可用" in plain
    assert ">" not in plain


def _assert_qq_translation(message) -> None:
    rendered = render_qq_message(message)
    assert rendered["kind"] == "markdown"
    keyboard = rendered["keyboard"]
    buttons = [button for row in keyboard["content"]["rows"] for button in row["buttons"]]
    assert [button["id"] for button in buttons] == ["view", "fill", "callback"]
    assert buttons[0]["action"] == {
        "type": 2,
        "data": "查看 乾坤书",
        "permission": {"type": 2},
        "unsupport_tips": "当前客户端不支持该操作.",
        "enter": True,
        "reply": False,
    }
    assert buttons[1]["action"]["enter"] is False
    assert buttons[2]["action"]["type"] == 1


def _assert_strict_structure() -> None:
    for invalid in ("> 手写引用", "---"):
        try:
            M.document().section("测试", icon="test").line(invalid)
            raise AssertionError("手写 Markdown 结构必须被拒绝")
        except ValueError:
            pass
    try:
        M.document().line("无栏目正文")
        raise AssertionError("正文必须归属于栏目")
    except ValueError:
        pass
    try:
        render_markdown(M.document().section("测试", icon="不存在").line("正文").build().document)
        raise AssertionError("未知 icon key 必须被拒绝")
    except ValueError as exc:
        assert "未知消息图标分类" in str(exc)


async def _assert_local_translation(message) -> None:
    old_exact = LocalEventHandler.exact_rules
    LocalEventHandler.exact_rules = {}
    try:
        @LocalEventHandler.handler(cmd="公共消息", priority=100, block=True)
        async def handler(client_id: str) -> None:
            await local_manager.send(message, client_id)

        await LocalEventHandler.run()
        result = await dispatch(client_id="local-user", raw_message="公共消息")
        assert len(result.replies) == 1
        rendered = result.replies[0].message
        assert isinstance(rendered, RenderedMessage)
        assert rendered.kind == "markdown"
        assert len(rendered.actions) == 3
    finally:
        LocalEventHandler.exact_rules = old_exact


async def _assert_public_manager_rejects_native_payload() -> None:
    try:
        await public_manager.send({"kind": "markdown", "content": "绕过模板"}, "local-user")
        raise AssertionError("公共 manager 必须拒绝平台原生 payload")
    except TypeError as exc:
        assert "只接受 message.Message" in str(exc)


if __name__ == "__main__":
    main()
