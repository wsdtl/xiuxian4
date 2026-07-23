"""套装图纸业务回执白名单。"""

from .models import EquipmentBlueprintReceipt


def equipment_blueprint_codec_registrations() -> tuple[tuple[str, type[object]], ...]:
    return (("game.equipment_blueprint.receipt.v1", EquipmentBlueprintReceipt),)


__all__ = ["equipment_blueprint_codec_registrations"]
