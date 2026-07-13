"""核心、正式修仙产品与测试业务的物理归属和单向依赖测试。"""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import game  # noqa: E402
from game import core  # noqa: E402
from game import cmd  # noqa: E402


def main() -> None:
    _assert_physical_layout()
    _assert_public_root()
    _assert_import_boundaries()
    print("core architecture tests passed")


def _assert_physical_layout() -> None:
    game = ROOT / "game"
    core = game / "core"
    assert (game / "__init__.py").is_file()
    assert core.is_dir()
    for name in ("gameplay", "account", "persistence"):
        assert (core / name / "__init__.py").is_file()
        assert not (ROOT / name).exists(), f"禁止保留旧顶层兼容包：{name}"
    assert (core / "gameplay" / "grants" / "__init__.py").is_file()
    assert not (ROOT / "xiuxian_core").exists(), "禁止保留旧核心目录"

    commands = game / "cmd"
    assert (commands / "__init__.py").is_file()
    assert (commands / "后台接口" / "__init__.py").is_file()
    assert not (game / "修仙4").exists(), "禁止保留提前建立的旧产品目录"

    assert (ROOT / "组件测试" / "QQ协议测试" / "__init__.py").is_file()
    for legacy in ("src", "components", "xiuxian_game"):
        assert not (ROOT / legacy).exists(), f"禁止保留旧目录：{legacy}"


def _assert_public_root() -> None:
    assert game.PUBLIC_FOUNDATION_VERSION == "public-foundation.v1.1"
    assert set(game.__all__) == {"PUBLIC_FOUNDATION_VERSION"}
    assert cmd.router is not None
    assert core.GAME_CORE_VERSION == "game-core.v1"
    assert core.CORE_LAYERS == (
        "game.core.gameplay",
        "game.core.account",
        "game.core.persistence",
    )
    assert set(core.__all__) == {"CORE_LAYERS", "GAME_CORE_VERSION"}


def _assert_import_boundaries() -> None:
    forbidden_by_layer = {
        "gameplay": {
            "launch", "message", "组件测试", "account", "persistence"
        },
        "account": {
            "launch",
            "message",
            "组件测试",
            "gameplay",
            "persistence",
        },
        "persistence": {"launch", "message", "组件测试"},
    }
    failures: list[str] = []
    for layer, forbidden in forbidden_by_layer.items():
        folder = ROOT / "game" / "core" / layer
        for path in folder.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for imported in _imports(tree, path):
                root_name = imported.split(".", 1)[0]
                core_layer = (
                    imported.split(".", 3)[2]
                    if imported.startswith("game.core.")
                    else root_name
                )
                if core_layer in forbidden or _is_game_integration(imported):
                    failures.append(
                        f"{path.relative_to(ROOT)} 导入了禁止层 {imported}"
                    )
    for folder_name in ("launch", "message"):
        for path in (ROOT / folder_name).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if any(
                imported == "game"
                or imported.startswith("game.")
                or (
                    folder_name == "message"
                    and (imported == "launch" or imported.startswith("launch."))
                )
                for imported in _imports(tree, path)
            ):
                failures.append(
                    f"{path.relative_to(ROOT)} 违反公共框架与游戏代码依赖边界"
                )
    for path in (ROOT / "组件测试").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imports(tree, path):
            if imported == "game" or imported.startswith("game."):
                failures.append(
                    f"{path.relative_to(ROOT)} 协议测试不得依赖游戏代码 {imported}"
                )
    assert not failures, "\n".join(failures)


def _is_game_core(imported: str) -> bool:
    return imported == "game.core" or imported.startswith("game.core.")


def _is_game_integration(imported: str) -> bool:
    return imported == "game.cmd" or imported.startswith("game.cmd.")


def _imports(tree: ast.AST, path: Path) -> tuple[str, ...]:
    result: list[str] = []
    relative = path.relative_to(ROOT).with_suffix("")
    package_parts = relative.parts[:-1]
    if path.name == "__init__.py":
        package_parts = relative.parts[:-1]
    package = ".".join(package_parts)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                result.append(node.module)
            elif node.level > 0:
                relative_name = "." * node.level + (node.module or "")
                result.append(resolve_name(relative_name, package))
    return tuple(result)


if __name__ == "__main__":
    main()
