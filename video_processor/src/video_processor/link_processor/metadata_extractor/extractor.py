from abc import ABC, abstractmethod
from typing import Any

from .metadata import RawMetadata


class VideoMetadataExtractor(ABC):
    def __init__(self, video_data: dict[str, Any]):
        super().__init__()

        self._video_data = video_data

    @property
    @abstractmethod
    def video_id(self) -> str | None:
        raise NotADirectoryError

    @abstractmethod
    def build_metadata(self, language_preferences: list[str]) -> RawMetadata:
        raise NotImplementedError
