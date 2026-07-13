"""由稳定领域身份推导聚合内键，不读取数据库。"""

from .world import CURRENCY_ID


def inventory_container_id(character_id: str) -> str:
    return f"container:{character_id}:inventory"


def equipped_container_id(character_id: str) -> str:
    return f"container:{character_id}:equipped"


def issuer_id() -> str:
    return f"ledger:issuer:{CURRENCY_ID}"


def wallet_id(account_id: str) -> str:
    return f"ledger:wallet:{account_id}:{CURRENCY_ID}"


__all__ = [
    "equipped_container_id",
    "inventory_container_id",
    "issuer_id",
    "wallet_id",
]
