"""Maps a yt-dlp TikTok JSON dump onto the shared metadata model."""

from collections.abc import Mapping, Sequence
from typing import Any

from .extractor import VideoMetadataExtractor
from .metadata import RawMetadata


class TikTokMetadataExtractor(VideoMetadataExtractor):
    """Extracts :class:`RawMetadata` from a yt-dlp TikTok JSON dump.

    TikTok frequently ships no caption tracks at all — ``language`` is null or
    missing and ``subtitles``/``automatic_captions`` are empty lists (or absent)
    — with the recipe content living in ``description``. Caption selection
    therefore treats any non-mapping value as "no captions" and yields
    ``RawMetadata.subtitles = None`` instead of failing.
    """

    @property
    def video_id(self) -> str | None:
        return self._video_data.get("id")

    def build_metadata(self, language_preferences: list[str]) -> RawMetadata:
        video_lang = self._video_data.get("language")
        subtitles = None    # TikTok does not return subtitles

        return RawMetadata(
            id=self.video_id,
            title=self._video_data.get("title"),
            description=self._video_data.get("description"),
            thumbnail=self._video_data.get("thumbnail"),
            subtitles=subtitles,
            language=video_lang,
            url=self._video_data.get("webpage_url"),
            view_count=self._video_data.get("view_count"),
            duration=self._video_data.get("duration"),
            channel=self._video_data.get("channel"),
        )
