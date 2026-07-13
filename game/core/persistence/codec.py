"""只允许白名单类型的结构化 JSON 编解码。"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
import json
import math
from typing import Mapping, TypeVar

from .errors import CorruptPersistenceData


ValueT = TypeVar("ValueT")


class StructuredJsonCodec:
    """不执行动态导入、不运行任意构造器之外代码的类型注册编解码器。"""

    FORMAT = "structured-json.v1"

    def __init__(self) -> None:
        self._types_by_id: dict[str, type[object]] = {}
        self._ids_by_type: dict[type[object], str] = {}
        self._frozen = False

    def register(self, type_id: str, value_type: type[object]) -> None:
        if self._frozen:
            raise RuntimeError("结构化 JSON 类型目录已经冻结")
        if not type_id.strip() or type_id in self._types_by_id:
            raise ValueError(f"重复或无效的持久化类型 id：{type_id!r}")
        if value_type in self._ids_by_type:
            raise ValueError(f"持久化类型重复登记：{value_type.__name__}")
        if not is_dataclass(value_type) and not issubclass(value_type, Enum):
            raise TypeError("持久化白名单只接受 dataclass 或 Enum")
        self._types_by_id[type_id] = value_type
        self._ids_by_type[value_type] = type_id

    def freeze(self) -> None:
        if not self._types_by_id:
            raise ValueError("结构化 JSON 类型目录不能为空")
        self._frozen = True

    def dumps(self, value: object) -> str:
        if not self._frozen:
            self.freeze()
        envelope = {"format": self.FORMAT, "value": self._encode(value)}
        return json.dumps(
            envelope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def loads(self, payload: str, expected_type: type[ValueT]) -> ValueT:
        if not self._frozen:
            self.freeze()
        try:
            envelope = json.loads(payload)
            if envelope.get("format") != self.FORMAT:
                raise CorruptPersistenceData("未知结构化 JSON 格式")
            value = self._decode(envelope["value"])
        except CorruptPersistenceData:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CorruptPersistenceData("持久化 JSON 无法按当前模型还原") from exc
        if not isinstance(value, expected_type):
            raise CorruptPersistenceData(
                f"持久化根类型错误：需要 {expected_type.__name__}，实际 {type(value).__name__}"
            )
        return value

    def _encode(self, value: object) -> object:
        if value is None:
            return value
        value_type = type(value)
        registered_id = self._ids_by_type.get(value_type)
        if registered_id is not None:
            if isinstance(value, Enum):
                return {"$type": registered_id, "$enum": value.value}
            return {
                "$type": registered_id,
                "$fields": {
                    item.name: self._encode(getattr(value, item.name))
                    for item in fields(value)
                },
            }
        if isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("持久化数值不能是 NaN 或 Infinity")
            return value
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("持久化 datetime 必须包含时区")
            return {"$type": "datetime", "value": value.isoformat()}
        if isinstance(value, Mapping):
            return {
                "$type": "mapping",
                "items": [
                    [self._encode(key), self._encode(item)]
                    for key, item in sorted(value.items(), key=lambda pair: repr(pair[0]))
                ],
            }
        if isinstance(value, tuple):
            return {"$type": "tuple", "items": [self._encode(item) for item in value]}
        if isinstance(value, frozenset):
            encoded = [self._encode(item) for item in value]
            encoded.sort(key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=True))
            return {"$type": "frozenset", "items": encoded}
        if isinstance(value, list):
            return {"$type": "list", "items": [self._encode(item) for item in value]}
        raise TypeError(f"未登记的持久化类型：{value_type.__name__}")

    def _decode(self, value: object) -> object:
        if value is None or isinstance(value, (str, bool, int, float)):
            return value
        if not isinstance(value, dict) or "$type" not in value:
            raise CorruptPersistenceData("持久化节点缺少类型标记")
        type_id = value["$type"]
        if type_id == "datetime":
            result = datetime.fromisoformat(value["value"])
            if result.tzinfo is None or result.utcoffset() is None:
                raise CorruptPersistenceData("持久化 datetime 缺少时区")
            return result
        if type_id == "mapping":
            return {
                self._decode(key): self._decode(item)
                for key, item in value["items"]
            }
        if type_id == "tuple":
            return tuple(self._decode(item) for item in value["items"])
        if type_id == "frozenset":
            return frozenset(self._decode(item) for item in value["items"])
        if type_id == "list":
            return [self._decode(item) for item in value["items"]]
        try:
            value_type = self._types_by_id[type_id]
        except KeyError as exc:
            raise CorruptPersistenceData(f"持久化类型未在白名单登记：{type_id}") from exc
        if issubclass(value_type, Enum):
            return value_type(value["$enum"])
        field_values = {
            key: self._decode(item)
            for key, item in value["$fields"].items()
        }
        return value_type(**field_values)


__all__ = ["StructuredJsonCodec"]
