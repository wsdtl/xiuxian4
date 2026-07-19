"""休息正式玩法入口。"""

from .codec import rest_codec_registrations
from .service import RestFeature, RestStorageKinds


__all__ = ["RestFeature", "RestStorageKinds", "rest_codec_registrations"]
