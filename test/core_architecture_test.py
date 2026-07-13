"""核心、正式修仙产品与测试业务的物理归属和单向依赖测试。"""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import xiuxian_core  # noqa: E402


def main() -> None:
    _assert_physical_layout()
    _assert_public_root()
    _assert_import_boundaries()
    print("core architecture tests passed")


def _assert_physical_layout() -> None:
    core = ROOT / "xiuxian_core"
    assert core.is_dir()
    for name in ("gameplay", "account", "persistence"):
        assert (core / name / "__init__.py").is_file()
        assert not (ROOT / name).exists(), f"禁止保留旧顶层兼容包：{name}"
    product = ROOT / "src" / "修仙4"
    assert (product / "__init__.py").is_file()
    assert (product / "业务" / "__init__.py").is_file()
    assert (product / "组件" / "__init__.py").is_file()
    assert not (ROOT / "xiuxian_game").exists()
    assert (ROOT / "components" / "QQ协议测试" / "__init__.py").is_file()
    for legacy in ("first_world", "adventure", "qq_protocol_test", "修仙4", "测试业务"):
        assert not (ROOT / "components" / legacy).exists(), f"禁止保留旧组件目录：{legacy}"
    for child in (product / "组件").iterdir():
        if not child.is_dir() or not (child / "__init__.py").is_file():
            continue
        tree = ast.parse((child / "__init__.py").read_text(encoding="utf-8"))
        assert any(
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(target, ast.Name) and target.id == "router"
                for target in (
                    node.targets if isinstance(node, ast.Assign) else (node.target,)
                )
            )
            for node in tree.body
        ), f"ROUTER_CHILD_FOLDERS 子组件必须暴露 router：{child.name}"


def _assert_public_root() -> None:
    assert xiuxian_core.XIUXIAN_CORE_VERSION == "xiuxian-core.v1"
    assert xiuxian_core.CORE_LAYERS == (
        "xiuxian_core.gameplay",
        "xiuxian_core.account",
        "xiuxian_core.persistence",
    )
    assert set(xiuxian_core.__all__) == {"CORE_LAYERS", "XIUXIAN_CORE_VERSION"}


def _assert_import_boundaries() -> None:
    forbidden_by_layer = {
        "gameplay": {
            "launch", "message", "components", "account", "persistence"
        },
        "account": {
            "launch",
            "message",
            "components",
            "gameplay",
            "persistence",
        },
        "persistence": {"launch", "message", "components"},
    }
    failures: list[str] = []
    for layer, forbidden in forbidden_by_layer.items():
        folder = ROOT / "xiuxian_core" / layer
        for path in folder.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for imported in _imports(tree, path):
                root_name = imported.split(".", 1)[0]
                core_layer = (
                    imported.split(".", 2)[1]
                    if imported.startswith("xiuxian_core.")
                    else root_name
                )
                if core_layer in forbidden or _is_formal_product(imported):
                    failures.append(
                        f"{path.relative_to(ROOT)} 导入了禁止层 {imported}"
                    )
    for folder_name in ("launch", "message"):
        for path in (ROOT / folder_name).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if any(
                imported == "xiuxian_core"
                or imported.startswith("xiuxian_core.")
                or _is_formal_product(imported)
                for imported in _imports(tree, path)
            ):
                failures.append(
                    f"{path.relative_to(ROOT)} 不得反向依赖游戏核心或正式修仙产品"
                )
    business_root = ROOT / "src" / "修仙4" / "业务"
    for path in business_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imports(tree, path):
            if (
                imported.split(".", 1)[0] in {"launch", "message", "components"}
                or imported == "src.修仙4.组件"
                or imported.startswith("src.修仙4.组件.")
            ):
                failures.append(
                    f"{path.relative_to(ROOT)} 不得依赖命令或通信层 {imported}"
                )
    for path in (ROOT / "src" / "修仙4" / "组件").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imports(tree, path):
            if imported == "components" or imported.startswith("components."):
                failures.append(
                    f"{path.relative_to(ROOT)} 不得依赖测试业务 {imported}"
                )
    for path in (ROOT / "components").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imports(tree, path):
            if _is_formal_product(imported):
                failures.append(
                    f"{path.relative_to(ROOT)} 测试业务不得反向依赖正式修仙产品 {imported}"
                )
    assert not failures, "\n".join(failures)


def _is_formal_product(imported: str) -> bool:
    return imported == "src.修仙4" or imported.startswith("src.修仙4.")


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
