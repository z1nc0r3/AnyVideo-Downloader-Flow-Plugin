# Author: Lasith Manujitha
# Github: @z1nc0r3
# Description: A plugin to download videos from multiple websites
# Date: 2024-07-28

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from pyflowlauncher import Plugin, ResultResponse, send_results
from pyflowlauncher.settings import settings
from results import (
    init_results,
    invalid_result,
    error_result,
    empty_result,
    query_result,
)
from ytdlp import CustomYoutubeDL

EXE_PATH = os.path.join(os.path.dirname(__file__), "yt-dlp.exe")
CHECK_INTERVAL_DAYS = 10
DEFAULT_DOWNLOAD_PATH = str(Path.home() / "Downloads")

plugin = Plugin()


def is_valid_url(url: str) -> bool:
    regex = (
        "((http|https)://)(www.)?"
        + "[a-zA-Z0-9@:%._\\+~#?&//=]"
        + "{1,256}\\.[a-z]"
        + "{2,6}\\b([-a-zA-Z0-9@:%"
        + "._\\+~#?&//=]*)"
    )

    return bool(re.match(regex, url))


@plugin.on_method
def query(query: str) -> ResultResponse:
    download_path = settings().get("download_path") or DEFAULT_DOWNLOAD_PATH
    if not os.path.exists(download_path):
        download_path = DEFAULT_DOWNLOAD_PATH

    if not query.strip():
        return send_results([init_results(download_path)])

    if not is_valid_url(query):
        return send_results([invalid_result()])

    query = query.replace("https://", "http://")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format-sort": "res,tbr",
    }
    ydl = CustomYoutubeDL(params=ydl_opts)
    info = ydl.extract_info(query)

    if ydl.error_message:
        return send_results([error_result()])

    formats = [
        format
        for format in info["formats"]
        if format.get("resolution") and format.get("tbr")
    ]

    if not formats:
        return send_results([empty_result()])

    results = [
        query_result(query, info, format, download_path) for format in reversed(formats)
    ]
    return send_results(results)


@plugin.on_method
def download(url: str, format_id: str, download_path: str) -> None:
    last_modified_time = datetime.fromtimestamp(os.path.getmtime(EXE_PATH))

    base_command = f'yt-dlp "{url}" -f {format_id}+ba -P {download_path} --windows-filenames --restrict-filenames --trim-filenames 50 --quiet --progress --no-mtime --force-overwrites --no-part'

    command = (
        f"{base_command} -U"
        if datetime.now() - last_modified_time >= timedelta(days=CHECK_INTERVAL_DAYS)
        else base_command
    )

    os.system(command)


if __name__ == "__main__":
    plugin.run()
