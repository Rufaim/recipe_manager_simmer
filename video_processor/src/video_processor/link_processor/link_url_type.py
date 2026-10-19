from dataclasses import dataclass
from enum import StrEnum

from .metadata_extractor import (
    TikTokMetadataExtractor,
    VideoMetadataExtractor,
    YouTubeMetadataExtractor,
)
from .url_validators import validate_tiktok_link, validate_you_tube_link


class LinkSourceType(StrEnum):
    UNKNOWN = "unknown"
    YOU_TUBE = "youtube"
    TIKTOK = "tiktok"

@dataclass(repr=False)
class LinkURL:
    url: str
    host: str
    path: str
    query: str
    type: LinkSourceType

    def __repr__(self):
        return self.url

    def get_metadata_extractor_type(self) -> type[VideoMetadataExtractor]:
        match self.type:
            case LinkSourceType.YOU_TUBE:
                return YouTubeMetadataExtractor
            case LinkSourceType.TIKTOK:
                return TikTokMetadataExtractor
            case _:
                raise RuntimeError(f"Unregistered source of URL: {self.url!r}")

    def validate_url(self):
        match self.type:
            case LinkSourceType.YOU_TUBE:
                validate_you_tube_link(self.url, self.host, self.path, self.query)
            case LinkSourceType.TIKTOK:
                validate_tiktok_link(self.url, self.host, self.path, self.query)
            case _:
                raise RuntimeError(f"Unregistered source of URL: {self.url!r}")
