def join_api_path(base_url: str, suffix: str) -> str:
    """Append ``suffix`` to an API base URL, tolerating a trailing slash."""
    return f"{base_url.rstrip('/')}/{suffix}"
