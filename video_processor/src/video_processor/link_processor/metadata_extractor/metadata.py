import json
import os
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

from ..utils import download_file


@dataclass(frozen=True)
class RawMetadata:
    url: str
    id: str
    title: str
    description: str
    thumbnail: str
    subtitles: str | None
    channel: str
    view_count: str
    duration: int
    language: str | None

    def save(self, path: Path):
        raw_metadata_path = os.path.join(path, f"raw_metadata_{self.id}.json")

        with open(raw_metadata_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    def save_subtitles(self, path: Path):
        if self.subtitles:
            download_file(self.subtitles, path.as_posix(), "subtitles", ".srt")
        else:
            warnings.warn("No URL for subtitles", RuntimeWarning, stacklevel=2)

    def save_thumbnail(self, path: Path):
        if self.thumbnail:
            download_file(self.thumbnail, path.as_posix(), "thumbnail")
        else:
            warnings.warn("No URL for thumbnail", RuntimeWarning, stacklevel=2)

    @classmethod
    def load(cls, path: Path) -> RawMetadata:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return RawMetadata(**data)
