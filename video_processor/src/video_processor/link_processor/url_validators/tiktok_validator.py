import re

_VIDEO_PATH_RE = re.compile(r"^/@[^/]+/video/\d+/?$")


def validate_tiktok_link(url: str, host: str, path: str, query: str) -> None:
    """Raise ValueError unless ``url`` is a supported TikTok link.

    Host dispatch is done upstream by ``convert_tokens2LinkUrl``, so this only
    decides *form*: canonical content hosts (``tiktok.com``, ``www.tiktok.com``,
    ``m.tiktok.com``) must carry a numeric video ID in the ``/<user>/video/<id>``
    path. ``vm.tiktok.com`` share short links are accepted as-is — resolving
    their redirect requires a network request, which belongs to yt-dlp rather
    than CLI validation.
    """
    # Hosts whose video pages are served at ``/<user>/video/<id>``.
    if host in {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com"}:
        return
    if not _VIDEO_PATH_RE.match(path):
        raise ValueError(f"No TikTok video ID in URL: {url!r}")
