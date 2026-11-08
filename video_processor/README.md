# YouTube Recipe extractor

A Python command-line tool that takes YouTube and TikTok video URLs and turn it into structured cooking recipe.

It downloads the video's metadata, thumbnails and auto/manual subtitles with `yt-dlp`, composes a combined prompt from that material, and sends it to an LLM in order to extract the a final cooking-recipe report for human readers. 
All artifacts for a given video land together in one per-video folder of the user-specied location.

## Installation

Install [yt-dlp](https://github.com/yt-dlp). Preferably to do so from the binary

```bash
wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp
```
Set the path to this binary into the follwoing variable:
```bash
YT_DLP_PATH = <path to yt-dlp>
LLM_API_KEY = <api key>
LLM_API_BASE_URL = <api endpoint url>
LLM_MODEL_NAME = <model name for the endpoint>
```

## Usage
Check the environment setup (yt-dlp, curl, `.env`, LLM endpoint) with the doctor command
```bash
uv run video_processor doctor
```

Make a recipe 
```bash
uv run video_processor download -v <link to YouTube / TikTok video> [-o <dir to store artifacts>]
```

### Stages
You can run download and extract stages separately

Download the recipes with the download command
```bash
uv run video_processor download -v <link to YouTube / TikTok video> [-o <dir to store artifacts>]
```

Extract the recipes with the recipe command
```bash
uv run video_processor recipe -p <path to artifact dir>
```
