import re
import tempfile
from pathlib import Path
from typing import Annotated, Literal, Sequence
from urllib.parse import urlsplit

from cyclopts import App, Parameter, Token, validators
from dotenv import load_dotenv
from rich.console import Console
from rich.text import Text

from .doctor import run_doctor
from .link_processor import (
    LinkSourceType,
    LinkURL,
    download_metadata_subtitles_thumbnail,
)
from .recipe_extractor import (
    extract_prompt_from_video,
    process_with_llm,
    save_extracted_recipe,
)


def convert_tokens2list_of_LinkUrl(type_, tokens: Sequence[Token]) -> list[LinkURL]:
    return [convert_tokenvalue2LinkUrl(t.value)
        for t in tokens
    ]

def convert_tokenvalue2LinkUrl(url: str) -> LinkURL:
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


def validate_video_urls(type_, values: list[LinkURL]) -> None:
    """Raise ValueError unless ``value`` is a supported YouTube or TikTok URL."""
    errors = []
    for v in values:
        try:
            v.validate_url()
        except (RuntimeError, ValueError) as e:
            errors.append(str(e))

    if len(errors) > 0:
        errors = "\n".join(errors)
        err_msg = Text(f"\n\n{errors}", no_wrap=True)
        raise ValueError(err_msg)


def validate_language_preference(type_, value: str) -> None:
    """Raise ValueError unless ``value`` is ';'-separated 2-letter codes, e.g. 'en;fr'."""
    if not all(re.fullmatch(r"[a-z]{2}", token) for token in value.split(";")):
        raise ValueError(
            f"language_preference must be ';'-separated 2-letter codes, e.g. 'en;fr', got {value!r}"
        )


def validate_paths_exist(type_, values: list[Path]) -> None:
    """Raise ValueError unless ``value`` is an existing path."""
    errors = [f"Path \"{v}\" does not exist"
        for v in values
        if not v.exists()
    ]

    if len(errors) > 0:
        errors = "\n".join(errors)
        err_msg = Text(f"\n\n{errors}", no_wrap=True)
        raise ValueError(err_msg)

load_dotenv()
app = App(name="you_tube_video_descriptor")

@app.default
def main(video_urls: Annotated[list[LinkURL], Parameter(n_tokens=1, converter=convert_tokens2list_of_LinkUrl,
                                    validator=validate_video_urls, name=["--video_url", "-v"], accepts_keys=False)],
        save_path: Annotated[Literal["temp"] | Annotated[Path, Parameter(validator=validators.Path(exists=True))], Parameter(name=["--save_path", "-o"])] = "temp",
        language_preference: Annotated[str, Parameter(validator=validate_language_preference)] = "ru;en;fr",
        verbose: bool = False
        ):
    """Download one or more videos and extract a recipe from each.

    Runs the ``download`` and ``extract_recipe`` stages back-to-back for every
    given URL: fetch metadata, subtitles and thumbnail, then build the LLM
    prompt and write the extracted markdown recipe into the same per-video
    ``<video_id>/`` folder.

    Parameters
    ----------
    video_urls
        One or more YouTube or TikTok URLs to process.
    save_path
        Where the per-video ``<video_id>/`` output folder is created. Pass
        ``temp`` (the default) for ``<system temp dir>/video_processed``, or a
        path to an existing directory.
    language_preference
        Semicolon-separated lowercase 2-letter subtitle language codes, tried
        in order (default ``ru;en;fr``).
    """
    video_paths = _download(video_urls, save_path, language_preference, verbose)
    _extract_recipe(video_paths, verbose=verbose)


def _download(video_urls: list[LinkURL],
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

    video_paths = []
    for vurl in video_urls:
        video_path = download_metadata_subtitles_thumbnail(vurl, save_path_, language_preference)
        if verbose:
            print(f"Metadata saved to \"{video_path}\"")
        video_paths.append(video_path)
    return video_paths


@app.command
def download(video_urls: Annotated[list[LinkURL], Parameter(n_tokens=1, converter=convert_tokens2list_of_LinkUrl,
                                    validator=validate_video_urls, name=["--video_url", "-v"], consume_multiple=True, accepts_keys=False)],
        save_path: Annotated[Literal["temp"] | Annotated[Path, Parameter(validator=validators.Path(exists=True))], Parameter(name=["--save_path", "-o"])] = "temp",
        language_preference: Annotated[str, Parameter(validator=validate_language_preference)] = "ru;en;fr",
        verbose: bool = False
        ):
    """Download each video's metadata, subtitles and thumbnail.

    Fetches the videos' metadata with yt-dlp and writes each into
    ``<save_path>/<video_id>/``: ``raw_metadata_<video_id>.json``, the
    thumbnail (extension taken from its URL) and, for videos that expose
    caption tracks, ``subtitles_<video_id>.srt``.
    The subtitle track is chosen by trying ``language_preference`` codes in
    order, preferring the video's own language and manual subtitles over
    automatic captions (ASR). Videos without captions (common on TikTok) are
    saved without an SRT file; the recipe stage then works from title and
    description.

    Requires ``YT_DLP_PATH`` in the environment pointing at a yt-dlp binary,
    plus ``curl`` and network access.

    Parameters
    ----------
    video_urls
        One or more URLs of the video to process — a YouTube
        ``watch?v=``/``youtu.be/<id>`` link, a TikTok
        ``tiktok.com/@<user>/video/<id>`` link, or a TikTok ``vm.tiktok.com``
        share short link.
    save_path
        Where the per-video ``<video_id>/`` output folders are created (re-run
        overwrites their files). Pass ``temp`` (the default) to write to
        ``<system temp dir>/video_processed``, or a path to an existing
        directory.
    language_preference
        Semicolon-separated lowercase 2-letter subtitle language codes, tried
        in order (default ``ru;en;fr``).
    """
    _download(video_urls, save_path, language_preference, verbose)


def _extract_recipe(video_folder_paths: list[Path],
    force_extract: bool = False,
    verbose: bool = False
    ):
    for vp in video_folder_paths:
        if verbose:
            print(f"Constructing a prompt from the metadata: {vp}")
        prompt = extract_prompt_from_video(vp, force_extract)
        if verbose:
            print("Processing with LLM")
        recipe = process_with_llm(prompt)
        if verbose:
            print("Saving the extracted recipe")
        save_extracted_recipe(recipe, vp)


@app.command(alias='recipe')
def extract_recipe(video_folder_paths: Annotated[list[Path], Parameter(validator=validate_paths_exist, consume_multiple=True, name=["--path", "-p"])],
    force_extract: bool = False,
    verbose: bool = False
    ):
    """Build an LLM prompt for each previously downloaded video.

    Reads metadata (and, when present, subtitles) from each given per-video
    folder and returns the prompt. The prompt is logged into
    ``combined_prompt_<video_id>.txt`` in the same folder. If ``force_extract``
    flag is provided, the prompt is regenerated. Videos without captions
    (most TikTok videos) are processed from their title and description, with
    the transcript marked as unavailable.

    Raises ``RuntimeError`` if a folder does not contain the metadata file,
    i.e. the video wasn't processed by ``download``.

    Parameters
    ----------
    video_folder_paths
        Paths to the per-video ``<video_id>/`` folders created by ``download``.
    force_extract
        Forces prompt re-extraction, if the prompt file exists.
    """
    _extract_recipe(video_folder_paths, force_extract, verbose)


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
