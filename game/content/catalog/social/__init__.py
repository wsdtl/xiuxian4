"""社会互动内容名录。"""

from game.core.gameplay import SocialRequestDefinition


SPARRING_REQUEST_ID = "social_request.sparring"
SPARRING_REQUEST_LIFETIME_SECONDS = 600
SPARRING_REQUEST = SocialRequestDefinition(
    SPARRING_REQUEST_ID,
    SPARRING_REQUEST_LIFETIME_SECONDS,
)


__all__ = [
    "SPARRING_REQUEST",
    "SPARRING_REQUEST_ID",
    "SPARRING_REQUEST_LIFETIME_SECONDS",
]
