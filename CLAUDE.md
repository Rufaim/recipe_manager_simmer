# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

The only code lives in `you_tube_video_descriptor/` — a Python CLI that turns YouTube cooking videos into markdown recipes. `docs/` at the root holds design notes (`ideas.md`, and `verification_url.md` — the plan for moving URL validation behind the platform decision). This directory is **not** a git repository.

All commands below must be run from `you_tube_video_descriptor/`.

## Commands

Note: Do NOT run any commands unless explicitly asked by user.

```bash
uv sync                                        # install deps (creates .venv, Python 3.14 required)

# Two-stage pipeline (see Architecture):
uv run python -m src download -v <youtube-url> [-o <existing-dir>]   # stage 1
uv run python -m src recipe -p <dir>/<video_id>                      # stage 2
uv run python -m src doctor                                          # env checks, exit 1 on failure
```

- `download` options: `-o/--save_path` defaults to `temp` (system temp dir + `video_processed`); `--language_preference` is `;`-separated 2-letter codes, default `ru;en;fr`.
- `recipe` option: `--force_extract` regenerates the cached prompt file instead of reusing it.
- There is no test suite, no linter and no CI configured. `test.py` at the package root is a
  hand-run scratch demo of a cyclopts custom-type `converter` (a `Point` dataclass), not a test.

## Required environment

Config comes from `.env` (loaded via python-dotenv at CLI startup; gitignored, so it exists only on this machine):

- `YT_DLP_PATH` — path to a yt-dlp **binary** (a copy is vendored at `you_tube_video_descriptor/yt-dlp`); README recommends downloading it from releases.
- `LLM_API_KEY`, `LLM_API_BASE_URL`, `LLM_MODEL_NAME` — OpenAI-compatible chat endpoint.

External runtime dependencies beyond Python: the yt-dlp binary and `curl` (subtitles/thumbnails are fetched with `curl -L`, not `requests`).

## Architecture

Two-stage pipeline coordinated entirely through files on disk — the two commands never share state, they communicate via a per-video artifact folder.

```
download (src/__main__.py)
  └─ link_processor.downloader.download_metadata_subtitles_thumbnail
       ├─ receives an already-parsed/validated LinkURL (host → LinkSourceType happens
       │  during cyclopts arg binding, before this function is entered)
       ├─ runs `<yt-dlp> --skip-download --dump-single-json <url>` via subprocess
       ├─ video_url.get_metadata_extractor_type() picks the extractor from
       │  metadata_extractor/ (YouTubeMetadataExtractor today, TikTok later)
       ├─ picks one SRT subtitle track: video's own language first, then
       │  language_preference order; manual subtitles preferred over automatic_captions
       └─ curl-downloads the chosen subtitles + thumbnail

recipe (src/__main__.py)
  └─ recipe_extractor
       ├─ extract_prompt_from_video — builds the combined prompt from artifacts
       ├─ process_with_llm — llm_provider.OpenAICompatibleLLMProvider, system prompt
       │  (EXTRACTION_SYSTEM_PROMPT) + user prompt → chat/completions with
       │  reasoning: {"enabled": true}
       └─ save_extracted_recipe
```

### The artifact-folder convention (critical to understand)

`download` creates `<save_path>/<video_id>/` containing:

| File | Written by | Read by |
|---|---|---|
| `raw_metadata_<video_id>.json` | link_processor | recipe stage |
| `subtitles_<video_id>.srt` | link_processor | recipe stage |
| `thumbnail.<ext>` (ext from URL) | link_processor | — |
| `combined_prompt_<video_id>.txt` | recipe stage (cached) | recipe stage |
| `recipe_<video_id>.md` | recipe stage | — |

Everything is keyed on **the folder name being the video ID**: `extract_prompt_from_video` derives the ID from `video_folder_path.name` and expects the exact `<prefix>_<id>.<ext>` filenames above. Re-running `download` overwrites the folder's files; re-running `recipe` reuses the cached `combined_prompt_*.txt` unless `force_extract` is passed (it still re-calls the LLM). Missing metadata/subtitles files → `RuntimeError("The video <id> was not processed.")`.

### Other non-obvious behavior

- URL platform knowledge is split three ways: `__main__.py:convert_tokens2LiknUrl` maps host →
  `LinkSourceType` (never raises — an unknown host becomes `LinkSourceType.UNKNOWN`),
  `url_validators/` holds the per-platform rules (`validate_you_tube_link` checks the 11-char
  id; it has no host check because dispatch already proved the host), and
  `link_url_type.py:LinkURL` carries `url/host/path/query/type` plus the two `match` dispatches
  (`validate_url`, `get_metadata_extractor_type`). `RawMetadata` gained a `url` field
  (yt-dlp `webpage_url`) in place of the old `source_type`, so `RawMetadata.load()` (no callers)
  rejects any artifact written before that swap. Stage 2 is unaffected either way —
  `recipe_extractor` re-reads the JSON itself, using only `id`/`title`/`description`.
- Validation is CLI-boundary only: `download_metadata_subtitles_thumbnail` never calls
  `LinkURL.validate_url()`, so a `LinkURL` built in code reaches yt-dlp unchecked. It also calls
  `get_metadata_extractor_type()` *after* the subprocess, so dispatch itself costs a network
  round-trip on an unwired platform.
- Subtitle parsing assumes strict 4-line SRT blocks and extracts only the text line (`islice(file, 2, None, 4)`) — timing/index lines are dropped and all text is joined into one line.
- The LLM base URL gets `v1/chat/completions` appended automatically (`llm_provider._url`); it must not already include a trailing path.
- `EXTRACTION_SYSTEM_PROMPT` in `recipe_extractor.py` defines the output contract: markdown-only recipe **in the same language as the video**, and the literal sentinel `NO_RECIPE` when the video isn't a recipe (currently saved to `recipe_*.md` as-is, not handled specially).
- Adding a platform is five edits: a `LinkSourceType` member; its host(s) in
  `__main__.py:convert_tokens2LiknUrl`; a validator in `url_validators/`; a `case` arm in **both**
  `LinkURL.validate_url` and `LinkURL.get_metadata_extractor_type`; and the extractor class in
  `metadata_extractor/`. TikTok is deliberately half-wired today — `LinkSourceType.TIKTOK` and the
  two `RuntimeError("TikTok support is under development")` arms exist, but the converter never
  assigns TIKTOK, so a TikTok URL is reported as UNKNOWN. `test_tiktok.json` / `test_you_tube.json`
  at the package root are real `--dump-single-json` dumps to build against: TikTok has **no**
  subtitles (`subtitles: []`) and `language: null`, while the whole recipe sits in `description` —
  so `save_subtitles()` only warns and stage 2 then fails with `The video <id> was not processed.`
- CLI framework is [cyclopts](https://github.com/jump-loop-labs/cyclopts). `--video_url` is
  `Annotated[LinkURL, Parameter(n_tokens=1, converter=convert_tokens2LiknUrl, validator=validate_video_url, accepts_keys=False)]`:
  `n_tokens=1` + `accepts_keys=False` are what stop a dataclass hint from being decomposed into one
  CLI token per field. A converter's signature is `(type_, tokens)` (Token objects) while a
  validator's is `(type_, value)`, and only `ValueError`/`AssertionError`/`TypeError` from a
  validator become a clean usage error — a `RuntimeError` escapes as a traceback, which is why
  `__main__.py:validate_video_url` raises `ValueError` for the UNKNOWN case instead of letting
  `LinkURL.validate_url()`'s `RuntimeError` surface. `language_preference` keeps a plain
  `(type_, value)` validator.
- `pyproject.toml` registers a console script `link_processor = "src.__main__:app"`; `[tool.uv] package = false`, so `uv run python -m src` is the way to invoke the app during development.
