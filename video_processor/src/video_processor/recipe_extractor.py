import json
from itertools import islice
from pathlib import Path

from .llm_provider import OpenAICompatibleLLMProvider

EXTRACTION_SYSTEM_PROMPT = """You extract recipes from the content of cooking videos.

You are given the video title, description and, when available, a transcription. Extract the
recipe that is actually cooked in the video and reply with ONLY markdown — no commentary — in
the SAME LANGUAGE as the video content, using exactly this structure:

# <Recipe name>

## Ingredients
- <quantity> <name>

## Steps
1. <one action>

Rules:
- Base the recipe strictly on the provided content. When no transcription is available, work
  from the title and description only — never invent ingredients, quantities or steps that the
  content does not support.
- When the video description contains quantities (the typed recipe is often posted there),
  prefer those measurements over spoken ones from the transcription, which are often
  approximate or could be misheard.
- Recipe name: use the real, conventional name of the dish cooked in the video. Usually it
  is mentioned in the video. Never invent a name and never copy the video title
  (titles are often clickbait). If the video features a specific variant, briefly append
  its key differentiator after the name.
- Ingredients: one per line, formatted as `<quantity> <name>`. The quantity includes its
  unit (g, ml, tsp, cloves, ...); use `to taste` when the video gives no amount. Keep the
  unit system used in the video. Merge duplicates and list ingredients in order of first
  mention.
- Ingredient names and steps must be comprehensive (nothing needed for the dish is missing)
  and concise (no filler words, no brands or serving tips unless essential). Keep only
  essential information.
- Steps: each step is exactly one simple action in imperative form. Keep the total number
  of steps minimal — trivially related sub-actions (e.g. peel and chop one vegetable, or cut
  multiple vegetables) may share a step, but two distinct actions never share one.
- If the content does not describe an actual recipe, reply with exactly: NO_RECIPE"""


def extract_prompt_from_video(video_folder_path: Path, force_extract: bool = False):
    id = video_folder_path.name
    output_path = video_folder_path.joinpath(f"combined_prompt.txt")

    if output_path.exists() and force_extract is False:
        return output_path.read_text(encoding="utf-8")

    raw_metadata_path = video_folder_path.joinpath(f"raw_metadata.json")

    if not raw_metadata_path.exists():
        raise RuntimeError(f"The video {id} was not processed.")

    with open(raw_metadata_path, "r", encoding="utf-8") as file:
        metadata = json.load(file)
        id = metadata["id"]
        title = metadata["title"]
        description = metadata["description"]

    transcript = "No transcript available for this video."
    subtitles_path = video_folder_path.joinpath(f"subtitles.srt")
    if subtitles_path.exists():
        with open(subtitles_path, "r", encoding="utf-8") as file:
            # TODO: add a propper subtitles processing
            each_third_line = map(str.strip, islice(file, 2, None, 4))
            transcript = " ".join(each_third_line)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(f"# Video title\n{title}\n\n")
        file.write(f"# Video description\n{description}\n\n")
        file.write(f"# Transcription\n{transcript}\n")

    return output_path.read_text(encoding="utf-8")


def process_with_llm(prompt_text: str) -> str:
    api = OpenAICompatibleLLMProvider()
    message = api.make_request([
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": prompt_text},
    ])

    recipe = message.get('content').strip()
    return recipe


def save_extracted_recipe(recipe: str, video_folder_path: Path):
    id = video_folder_path.name
    recipe_path = video_folder_path.joinpath(f"recipe.md")

    if not recipe:
        raise RuntimeError(f"The recipe is empty for the video {id}.")

    with open(recipe_path, "w", encoding="utf-8") as file:
        file.write(f"{recipe}\n")
