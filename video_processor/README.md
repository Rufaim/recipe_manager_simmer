# video-processor

A Python command-line tool that takes YouTube and TikTok video URLs and turns them into structured cooking recipes.

It downloads each video's metadata, thumbnails and auto/manual subtitles with `yt-dlp`, composes a combined prompt from that material, and sends it to an LLM to extract a final cooking-recipe report for human readers. Multiple URLs can be processed in a single invocation.
All artifacts for a given video land together in one per-video folder at the user-specified location. 
Each per-video folder is named by the video ID.

## Installation

Install [yt-dlp](https://github.com/yt-dlp). Preferably to do so from the binary

```bash
wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp
```
Set the path to this binary into the follwoing variable:
```bash
YT_DLP_PATH=<path to yt-dlp>
LLM_API_KEY=<api key>
LLM_API_BASE_URL=<api endpoint url>
LLM_MODEL_NAME=<model name for the endpoint>
```

## Usage
Check the environment setup (yt-dlp, curl, `.env`, LLM endpoint) with the doctor command
```bash
uv run video_processor doctor
```

Make a recipe — download metadata, subtitles and thumbnail, then extract a
markdown recipe via LLM in one shot.

```bash
uv run video_processor -v <link to YouTube / TikTok video> [-o <dir to store artifacts>] [--language_preference <lang>]
```
If artifact directory `-o` is omitted, the data are written to the system temp directory.

Subtitle language preference is a semicolon-separated list of 2-letter codes (default `ru;en;fr`). The pipeline looks for each language in order and prefers manual subtitles over automatic captions.

### Stages
You can run download and extract stages separately

Download each video's metadata, subtitles and thumbnail with yt-dlp.

```bash
uv run video_processor download -v <link to YouTube / TikTok video> [-o <dir to store artifacts>] [--language_preference <lang>]
```
Re-running `download` overwrites artifacts

Build an LLM prompt from the downloaded metadata and subtitles, then save the extracted markdown recipe.

```bash
uv run video_processor recipe -p <path to artifact dir> [--force_extract]
```
Re-running `recipe` reuses the cached prompt unless `--force_extract` is passed.
