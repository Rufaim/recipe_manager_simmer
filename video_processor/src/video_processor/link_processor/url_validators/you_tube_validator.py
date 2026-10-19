import re
from urllib.parse import parse_qs

_VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")

def validate_you_tube_link(url: str,host: str, path: str, query: str):
    """Raise ValueError unless ``url`` is a supported YouTube link.

    Host dispatch is done upstream by ``convert_tokens2LinkUrl``, so this only
    decides *form*: youtube.com ``watch`` pages must carry an 11-character
    video ID in the ``v`` query parameter, and ``youtu.be`` share links in the
    ``/<id>`` path. Anything else gets a concise ``ValueError``.
    """
    if host == "youtu.be":
        video_id = path.lstrip("/")
    else:
        video_id = (parse_qs(query).get("v") or [""])[0]
    if not _VIDEO_ID_RE.fullmatch(video_id):
        raise ValueError(f"No YouTube video ID in URL: {url}")
