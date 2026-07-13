"""只改展示名称、不改变战斗规则的铭刻底座。"""

INSCRIPTION_FOUNDATION_VERSION = "inscription.foundation.v1"

from .engine import InscriptionEngine, inscription_fingerprint
from .models import (
    INSCRIPTION_DATA_KEY,
    INSCRIPTION_MEDIUM_DATA_KEY,
    MAX_INSCRIPTION_NAME_LENGTH,
    AssetInscriptionTarget,
    InscriptionCommand,
    InscriptionData,
    InscriptionExecution,
    InscriptionMediumData,
    InscriptionPreference,
    InscriptionReceipt,
    InscriptionTarget,
    WeaponAbilityInscriptionTarget,
    clean_inscription_name,
    inscription_data,
)
from .projection import InscriptionProjector

__all__ = [
    "INSCRIPTION_DATA_KEY",
    "INSCRIPTION_FOUNDATION_VERSION",
    "INSCRIPTION_MEDIUM_DATA_KEY",
    "MAX_INSCRIPTION_NAME_LENGTH",
    "AssetInscriptionTarget",
    "InscriptionCommand",
    "InscriptionData",
    "InscriptionEngine",
    "InscriptionExecution",
    "InscriptionMediumData",
    "InscriptionPreference",
    "InscriptionProjector",
    "InscriptionReceipt",
    "InscriptionTarget",
    "WeaponAbilityInscriptionTarget",
    "clean_inscription_name",
    "inscription_data",
    "inscription_fingerprint",
]
