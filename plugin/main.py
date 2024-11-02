# Author: Lasith Manujitha
# Github: @z1nc0r3
# Description: A plugin to download videos from multiple websites
# Date: 2024-07-28

import os
import re
import shutil
from datetime import datetime, timedelta

from pyflowlauncher import Plugin, Result, ResultResponse, send_results
from pyflowlauncher.settings import settings
from results import (
    init_results,
    invalid_result,
    error_result,
    empty_result,
    query_result,
)
from yt_dlp import YoutubeDL

parent_folder_path = os.path.abspath(os.path.dirname(__file__))
EXE_PATH = os.path.join(parent_folder_path, "yt-dlp.exe")
CHECK_INTERVAL_DAYS = 10

plugin = Plugin()


# Custom YoutubeDL class to exception handling
class CustomYoutubeDL(YoutubeDL):
    def __init__(self, params=None, auto_init=True):
        super().__init__(params, auto_init)
        self.error_message = None

    def report_error(self, message, *args, **kwargs):
        self.error_message = message

    def extract_info(
        self,
        url,
        download=False,
        ie_key=None,
        extra_info=None,
        process=True,
        force_generic_extractor=False,
    ):
        try:
            result = super().extract_info(
                url, download, ie_key, extra_info, process, force_generic_extractor
            )
            return result
        except Exception as e:
            self.error_message = f"Unexpected error: {str(e)}"
            return None


def is_valid_url(url: str) -> bool:
    regex = (
        "((http|https)://)(www.)?"
        + "[a-zA-Z0-9@:%._\\+~#?&//=]"
        + "{1,256}\\.[a-z]"
        + "{2,6}\\b([-a-zA-Z0-9@:%"
        + "._\\+~#?&//=]*)"
    )

    p = re.compile(regex)

    return re.match(p, url)


@plugin.on_method
def query(query: str) -> ResultResponse:
    if not query.strip():
        return send_results([init_results()])

    if not is_valid_url(query):
        return send_results([invalid_result()])

    if query.startswith("https://"):
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

    results = [query_result(info, format, download) for format in reversed(formats)]

    return send_results(results)


@plugin.on_method
def download(url: str, format_id: str) -> None:
    last_modified_time = datetime.fromtimestamp(os.path.getmtime(EXE_PATH))
    base_command = f'yt-dlp "{url}" -f {format_id}+ba -P ~/Downloads/AnyDownloader --windows-filenames --restrict-filenames --trim-filenames 50 --quiet --progress --no-mtime --force-overwrites --no-part'
    command = (
        f"{base_command} -U"
        if datetime.now() - last_modified_time >= timedelta(days=CHECK_INTERVAL_DAYS)
        else base_command
    )
    os.system(command)


if __name__ == "__main__":
    plugin.run()
