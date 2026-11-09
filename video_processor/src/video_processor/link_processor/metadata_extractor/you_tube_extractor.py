from collections.abc import Sequence
from typing import Any

from .extractor import VideoMetadataExtractor
from .metadata import RawMetadata


class YouTubeMetadataExtractor(VideoMetadataExtractor):
    @property
    def video_id(self) -> str | None:
        return self._video_data.get("id")

    def build_metadata(self, language_preferences: list[str]) -> RawMetadata:
        # resolve subtitles in SRT format
        video_lang = self._video_data.get("language")
        subtitles = self._video_data.get("subtitles")
        automatic_captions = self._video_data.get("automatic_captions")

        selected_subtitles_url = None
        if video_lang in language_preferences:
            if video_lang in subtitles:
                selected_subtitles_url = get_subtitles_link_in_str(subtitles.get(video_lang))
            else:
                selected_subtitles_url = get_subtitles_link_in_str(automatic_captions.get(video_lang))
        else:
            selected_subtitles_url = get_subtitles_link_on_lang(language_preferences, subtitles)
            if selected_subtitles_url is None:
                selected_subtitles_url = get_subtitles_link_on_lang(language_preferences, automatic_captions)

        return RawMetadata(
            id=self.video_id,
            title=self._video_data.get("title"),
            description=self._video_data.get("description"),
            thumbnail=self._video_data.get("thumbnail"),
            subtitles=selected_subtitles_url,
            language=video_lang,
            url=self._video_data.get("webpage_url"),
            view_count=self._video_data.get("view_count"),
            duration=self._video_data.get("duration"),
            channel=self._video_data.get("channel")
        )

def get_subtitles_link_on_lang(language_preference: Sequence[str], subtitles_list: dict[str, Any]) -> str | None:
    for lang in language_preference:
        subtitles = get_subtitles_link_in_str(subtitles_list[lang])
        if subtitles is not None:
            return subtitles
    return None

def get_subtitles_link_in_str(subtitles: Sequence[dict[str, Any]]) -> str | None:
    for record in subtitles:
        if record.get("ext", "") == "srt":
            return record.get("url")
    return None
