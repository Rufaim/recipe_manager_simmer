import json
import os
import subprocess
from pathlib import Path

from .link_url_type import LinkURL


def download_metadata_subtitles_thumbnail(video_url: LinkURL, save_path: Path, language_preference: str) -> Path:
    yt_dlp_path = os.getenv("YT_DLP_PATH")
    language_preferences = language_preference.split(";")
    # Download video metadata
    command = [
        yt_dlp_path,
        "--skip-download",
        "--dump-single-json",
        video_url.url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    video_data = json.loads(result.stdout)

    metadata_extractor = video_url.get_metadata_extractor_type()(video_data)

    video_id = metadata_extractor.video_id
    if video_id is None:
        raise RuntimeError("Unable to identify video id")

    work_path = save_path / video_id
    os.makedirs(work_path, exist_ok=True)

    raw_metadata = metadata_extractor.build_metadata(language_preferences)

    # Write raw metadata for debug purposes.
    raw_metadata.save(work_path)
    # Download subtitles into the working directory
    raw_metadata.save_subtitles(work_path)
    # Download thumbnail into the working directory
    raw_metadata.save_thumbnail(work_path)
    return work_path
