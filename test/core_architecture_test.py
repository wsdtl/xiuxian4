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
from game.core import account, gameplay, persistence  # noqa: E402


def main() -> None:
    _assert_physical_layout()
    _assert_public_root()
    _assert_layer_public_exports()
    _assert_import_boundaries()
    _assert_core_neutrality()
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
    assert game.PUBLIC_FOUNDATION_VERSION == "public-foundation.v5"
    assert set(game.__all__) == {"PUBLIC_FOUNDATION_VERSION"}
    assert cmd.router is not None
    assert core.GAME_CORE_VERSION == "game-core.v5"
    assert core.CORE_LAYERS == (
        "game.core.gameplay",
        "game.core.account",
        "game.core.persistence",
    )
    assert set(core.__all__) == {"CORE_LAYERS", "GAME_CORE_VERSION"}


def _assert_layer_public_exports() -> None:
    for module in (account, gameplay, persistence):
        exports = tuple(module.__all__)
        assert len(exports) == len(set(exports)), f"{module.__name__} 存在重复公开符号"
        missing = tuple(name for name in exports if not hasattr(module, name))
        assert not missing, f"{module.__name__} 缺少公开符号：{', '.join(missing)}"


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


def _assert_core_neutrality() -> None:
    """真正核心不能倒灌产品词、模块随机源或机器当前时间。"""

    product_terms = ("宗门", "仙城", "纳戒", "探险", "首领", "洞天", "修仙")
    failures: list[str] = []
    core = ROOT / "game" / "core"
    for path in core.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        for term in product_terms:
            if term in source:
                failures.append(f"{relative} 出现具体产品词 {term}")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "random" and path.name != "context.py":
                        failures.append(f"{relative} 直接导入模块随机源")
            elif isinstance(node, ast.ImportFrom) and node.module == "random":
                failures.append(f"{relative} 直接导入模块随机源")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                owner = node.func.value
                if (
                    isinstance(owner, ast.Name)
                    and owner.id == "datetime"
                    and node.func.attr in {"now", "utcnow"}
                ):
                    failures.append(f"{relative} 直接读取机器当前时间")
                if (
                    isinstance(owner, ast.Name)
                    and owner.id == "time"
                    and node.func.attr == "time"
                ):
                    failures.append(f"{relative} 直接读取机器当前时间")
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
