# CLAUDE.md

Guidance for working in this repository.

## Repository layout

- `video_processor/` is the Python CLI package that downloads YouTube/TikTok video metadata and extracts recipes with an OpenAI-compatible LLM endpoint.
- `docs/` contains design notes and implementation plans.
- This repository is a git repository.

Do **not** run commands unless explicitly asked by the user. When asked to run project commands, run them from `video_processor/`.

## Commands

The package requires Python 3.14 or newer. Install dependencies with `uv sync` from `video_processor/`.

```bash
uv run video_processor doctor
uv run video_processor -v <video-url> [-v <another-video-url> ...] [-o <existing-dir>] [--language_preference ru;en;fr]
uv run video_processor download -v <video-url> [-v <another-video-url> ...] [-o <existing-dir>] [--language_preference ru;en;fr]
uv run video_processor recipe -p <video-folder> [-p <another-video-folder> ...] [--force_extract]
```

- The default command runs download and recipe extraction sequentially for each video.
- `download` accepts multiple URLs; `recipe` accepts multiple artifact-folder paths.
- `-o/--save_path` must be an existing directory. If omitted, outputs go to `<system temp dir>/video_processed`.
- `--language_preference` is a semicolon-separated list of lowercase two-letter codes, default `ru;en;fr`. Codes are tried in order; manual subtitles are preferred over automatic captions.
- `--force_extract` regenerates the cached combined prompt. Without it, `recipe` reuses the existing prompt but still calls the LLM.
- `--verbose` enables progress messages.
- There is no committed test suite, linter, or CI configuration.

## Environment

The CLI loads `.env` at startup. Required values:

- `YT_DLP_PATH` — path to an executable yt-dlp binary.
- `LLM_API_KEY` — API key for the OpenAI-compatible endpoint.
- `LLM_API_BASE_URL` — endpoint base URL; the client appends `v1/chat/completions` (or `v1/models` for `doctor`). Do not include the endpoint path in this value.
- `LLM_MODEL_NAME` — model name sent with chat-completion requests.

Metadata, subtitle, and thumbnail downloads require network access; subtitle and thumbnail HTTP downloads use `requests`. The yt-dlp binary is required for downloading video metadata.

## Pipeline and artifacts

The default command and the two explicit stages communicate through one folder per video, named by video ID:

```text
<save_path>/<video_id>/
  raw_metadata.json
  subtitles.srt             # when a suitable SRT track exists
  thumbnail.<extension>     # when a thumbnail is available
  combined_prompt.txt       # cached by recipe extraction
  recipe.md                 # extracted recipe
```

- `download` runs yt-dlp to obtain metadata, then selects and downloads an SRT subtitle track when available and downloads the thumbnail. TikTok videos may not expose subtitles; in that case, metadata/description can still be saved without an SRT.
- `recipe` builds a prompt from title, description, and optional subtitle text. It parses SRT using a four-lines-per-cue assumption; multiline cues may be parsed incorrectly.
- The LLM is asked to return Markdown in the video content's language and to prefer measurements in the video description over spoken measurements. If it returns content containing `NO_RECIPE`, `save_extracted_recipe` raises `RuntimeError` and does not write `recipe.md` for that video.
- Batch loops do not catch per-video exceptions; a failure (including `NO_RECIPE`) stops processing subsequent videos in that invocation.
- Re-running `download` overwrites files in the video folder. Re-running `recipe` reuses `combined_prompt.txt` unless `--force_extract` is supplied; it still makes a fresh LLM request.

## Code map

- `video_processor/src/video_processor/__main__.py` — cyclopts CLI, URL parsing/validation, and command orchestration.
- `video_processor/src/video_processor/link_processor/downloader.py` — yt-dlp invocation and per-video artifact setup.
- `video_processor/src/video_processor/link_processor/link_url_type.py` — `LinkURL`, platform enum, and dispatch to validators/metadata extractors.
- `video_processor/src/video_processor/link_processor/metadata_extractor/` — platform-specific mapping from yt-dlp JSON into `RawMetadata`.
- `video_processor/src/video_processor/link_processor/metadata_extractor/metadata.py` — metadata serialization and subtitle/thumbnail persistence.
- `video_processor/src/video_processor/link_processor/utils.py` — HTTP asset download and API URL joining.
- `video_processor/src/video_processor/recipe_extractor.py` — prompt creation, LLM response handling, and recipe output.
- `video_processor/src/video_processor/llm_provider.py` — OpenAI-compatible request construction and timeout/retry handling.
- `video_processor/src/video_processor/doctor.py` — environment and LLM endpoint checks.

## Important implementation details

- Platform parsing starts in `convert_tokenvalue2LinkUrl()`; validators are attached to CLI parameters, so code constructing `LinkURL` directly does not automatically validate it.
- The YouTube extractor prefers the video's own language when it is in `language_preference`, otherwise tries the configured languages in order. For each language, manual subtitles are searched before automatic captions. Only SRT tracks are selected.
- TikTok metadata currently has no subtitle-track selection; `subtitles` is set to `None`.
- `OpenAICompatibleLLMProvider` defaults to a `(10, 120)` Requests timeout, `max_retries=2` total attempts, and a 2-second fallback delay. HTTP 429/5xx responses can be retried; other HTTP failures raise immediately. A request exception is not retried because the provider may already have completed the request. Numeric `Retry-After` values are honored.
- `doctor` checks the `.env` location, yt-dlp executable, LLM configuration, and endpoint reachability. It does not send a completion request.
