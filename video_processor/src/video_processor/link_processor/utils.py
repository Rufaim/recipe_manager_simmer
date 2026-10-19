import mimetypes
import os
import warnings

import requests


def download_file(url: str, save_path: str, filename: str, extension: str | None = None):
    response = requests.get(url)
    if response.status_code == 200:
        if extension is None:
            # 1. Fetch the Content-Type header (e.g., 'image/png; charset=utf-8')
            content_type = response.headers.get("Content-Type")
            if content_type is None:
                warnings.warn(f"The provided URL does not contain Content-Type field. Stopped downloading.\nURL: {url}")
                return
            # 2. Strip out extras like charset parameters
            clean_mime_type = content_type.split(";")[0].strip()
            # 3. Guess the standard extension (e.g., returns '.png')
            extension = mimetypes.guess_extension(clean_mime_type)
            if extension is None:
                warnings.warn(f"Could not determine the file extension from Content-Type: {clean_mime_type}. Stopped downloading.")
                return
        filename = os.path.join(save_path,f"{filename}{extension}")
        with open(filename, "wb") as file:
            file.write(response.content)
    else:
        warnings.warn(f"Failed to fetch from url {url} .\n Status code: {response.status_code}")
