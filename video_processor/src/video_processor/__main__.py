import re
import tempfile
from pathlib import Path
from typing import Annotated, Literal, Sequence
from urllib.parse import urlsplit

from cyclopts import App, Parameter, validators, Token
from dotenv import load_dotenv
from rich.console import Console
from rich.text import Text

from .doctor import run_doctor
from .link_processor import download_metadata_subtitles_thumbnail, LinkURL, LinkSourceType
from .recipe_extractor import (
    extract_prompt_from_video,
    process_with_llm,
    save_extracted_recipe,
)


def convert_tokens2LinkUrl(type_, tokens: Sequence[Token]) -> LinkURL:
    url = tokens[0].value
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com",
                    "music.youtube.com", "youtu.be"}:
        return LinkURL(
            url=url,
            host=host,
            path=parsed.path,
            query=parsed.query,
            type=LinkSourceType.YOU_TUBE
        )
    if host in {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com"}:
        return LinkURL(
            url=url,
            host=host,
            path=parsed.path,
            query=parsed.query,
            type=LinkSourceType.TIKTOK
        )
    return LinkURL(
        url=url,
        host=host,
        path=parsed.path,
        query=parsed.query,
        type=LinkSourceType.UNKNOWN
    )


def validate_video_url(type_, value: LinkURL) -> None:
    """Raise ValueError unless ``value`` is a supported YouTube or TikTok URL."""
    if value.type is LinkSourceType.UNKNOWN:
        raise ValueError(f"Unregistered source of URL: {value.url!r}")
    value.validate_url()


def validate_language_preference(type_, value: str) -> None:
    """Raise ValueError unless ``value`` is ';'-separated 2-letter codes, e.g. 'en;fr'."""
    if not all(re.fullmatch(r"[a-z]{2}", token) for token in value.split(";")):
        raise ValueError(
            f"language_preference must be ';'-separated 2-letter codes, e.g. 'en;fr', got {value!r}"
        )

load_dotenv()
app = App(name="you_tube_video_descriptor")

@app.default
def main(video_url: Annotated[LinkURL, Parameter(n_tokens=1, converter=convert_tokens2LinkUrl,
                                    validator=validate_video_url, name=["--video_url", "-v"], accepts_keys=False)],
        save_path: Annotated[Literal["temp"] | Annotated[Path, Parameter(validator=validators.Path(exists=True))], Parameter(name=["--save_path", "-o"])] = "temp",
        language_preference: Annotated[str, Parameter(validator=validate_language_preference)] = "ru;en;fr",
        verbose: bool = False
        ):
   video_path = _download(video_url, save_path, language_preference, verbose)
   _extract_recipe(video_path, verbose=verbose)


def _download(video_url: LinkURL,
        save_path: Literal["temp"] | Path = "temp",
        language_preference: str = "ru;en;fr",
        verbose: bool = False
    ):
    if save_path == "temp":
        save_path_ = Path(tempfile.gettempdir()).joinpath("video_processed")
    else:
        save_path_ = save_path

    if verbose:
        print(f"Downloading to \"{save_path_}\"")
    video_path = download_metadata_subtitles_thumbnail(video_url, save_path_, language_preference)
    if verbose:
        print(f"Metadata saved to \"{video_path}\"")
    return video_path


@app.command
def download(video_url: Annotated[LinkURL, Parameter(n_tokens=1, converter=convert_tokens2LinkUrl,
                                    validator=validate_video_url, name=["--video_url", "-v"], accepts_keys=False)],
        save_path: Annotated[Literal["temp"] | Annotated[Path, Parameter(validator=validators.Path(exists=True))], Parameter(name=["--save_path", "-o"])] = "temp",
        language_preference: Annotated[str, Parameter(validator=validate_language_preference)] = "ru;en;fr",
        verbose: bool = False
        ):
    """Download a video's metadata, subtitles and thumbnail.

    Fetches the video's metadata with yt-dlp and writes it into ``<save_path>/<video_id>/``:
    ``raw_metadata_<video_id>.json``, the thumbnail (extension taken from its
    URL) and, for videos that expose caption tracks, ``subtitles_<video_id>.srt``.
    The subtitle track is chosen by trying ``language_preference`` codes in
    order, preferring the video's own language and manual subtitles over
    automatic captions (ASR). Videos without captions (common on TikTok) are
    saved without an SRT file; the recipe stage then works from title and
    description.

    Requires ``YT_DLP_PATH`` in the environment (by default loaded from environment) pointing
    at a yt-dlp binary, plus ``curl`` and network access.

    Parameters
    ----------
    video_url
        URL of the video to process — a YouTube ``watch?v=``/``youtu.be/<id>``
        link, a TikTok ``tiktok.com/@<user>/video/<id>`` link, or a TikTok
        ``vm.tiktok.com`` share short link.
    save_path
        Where the per-video ``<video_id>/`` output folder is created (re-run
        overwrites its files). Pass ``temp`` (the default) to write to
        ``<system temp dir>/video_processed``, or a path to an existing
        directory.
    language_preference
        Semicolon-separated lowercase 2-letter subtitle language codes, tried
        in order (default ``ru;en;fr``).
    """
    _download(video_url, save_path, language_preference, verbose)


def _extract_recipe(video_folder_path: Path,
    force_extract: bool = False,
    verbose: bool = False
    ):
    if verbose:
        print(f"Constructing a prompt from the metadata: {video_folder_path}")
    prompt = extract_prompt_from_video(video_folder_path, force_extract)
    if verbose:
        print("Processing with LLM")
    recipe = process_with_llm(prompt)
    if verbose:
        print("Saving the extracted recipe")
    save_extracted_recipe(recipe, video_folder_path)


@app.command(alias='recipe')
def extract_recipe(video_folder_path: Annotated[Path, Parameter(validator=validators.Path(exists=True), name=["--path", "-p"])],
    force_extract: bool = False,
    verbose: bool = False
    ):
    """Build LLM prompt for a previously downloaded video.

    Reads metadata (and, when present, subtitles) from the given per-video
    folder and returns the prompt. The prompt is logged into
    ``combined_prompt_<video_id>.txt`` in the same folder. If ``force_extract``
    flag is provided, the prompt is regenerated. Videos without captions
    (most TikTok videos) are processed from their title and description, with
    the transcript marked as unavailable.

    Raises ``RuntimeError`` if the folder does not contain the metadata file,
    i.e. the video wasn't processed by ``download``.

    Parameters
    ----------
    video_folder_path
        Path to the per-video ``<video_id>/`` folder created by ``download``.
    force_extract
        Forces prompt re-extraction, if the prompt file exists.
    """
    _extract_recipe(video_folder_path, force_extract, verbose)


@app.command
def doctor():
    """Validate the environment the pipeline needs, in one shot.

    Checks the ``.env`` file, ``curl`` on ``PATH``, ``YT_DLP_PATH`` (points at
    an executable that actually runs yt-dlp) and the ``LLM_API_KEY``,
    ``LLM_API_BASE_URL`` and ``LLM_MODEL_NAME`` variables. When all three LLM
    variables pass, the endpoint is additionally probed with a free
    models-list request — no completion is sent and the API key is never
    printed; otherwise the probe is skipped.

    Prints one ``[ OK ]``/``[WARN]``/``[FAIL]``/``[SKIP]`` line per check, fix
    hints included in the details, and exits with status 1 if any check
    failed. Warnings alone do not fail.
    """
    checks = run_doctor()
    console = Console()
    status_colour = {"ok": "green", "warn": "yellow", "fail": "red bold", "skip": "dim"}
    for check in checks:
        label = Text(f"[{check.status.upper():^4}]", style=status_colour.get(check.status, "white"))
        # Text() everywhere: check details may contain markup-looking "[...]" substrings.
        console.print(label, Text(f"{check.name}: {check.details}"))
    if any(check.error() for check in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    app()
