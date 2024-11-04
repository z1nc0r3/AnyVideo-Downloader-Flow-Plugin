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


def fetch_settings():
    download_path = settings().get("download_path") or DEFAULT_DOWNLOAD_PATH
    if not os.path.exists(download_path):
        download_path = DEFAULT_DOWNLOAD_PATH

    sorting_order = settings().get("sorting_order") or "Resolution"

    pref_video_format = settings().get("preferred_video_format") or "mp4"
    pref_audio_format = settings().get("preferred_audio_format") or "mp3"

    return download_path, sorting_order, pref_video_format, pref_audio_format


def sort_by_resolution(formats):
    def resolution_to_tuple(resolution):
        if resolution == "audio only":
            return (0, 0)
        return tuple(map(int, resolution.split("x")))

    return sorted(
        formats, key=lambda x: resolution_to_tuple(x["resolution"]), reverse=True
    )


def sort_by_tbr(formats):
    return sorted(formats, key=lambda x: x["tbr"], reverse=True)


def sort_by_fps(formats):
    return sorted(
        formats,
        key=lambda x: (
            x["fps"] is None,
            -x["fps"] if x["fps"] is not None else float("-inf"),
        ),
    )


def sort_by_size(formats):
    return sorted(
        formats,
        key=lambda x: (
            x["size"] is None,
            -x["size"] if x["size"] is not None else float("-inf"),
        ),
    )


@plugin.on_method
def query(query: str) -> ResultResponse:
    d_path, sort, pvf, paf = fetch_settings()

    if not query.strip():
        return send_results([init_results(d_path)])

    if not is_valid_url(query):
        return send_results([invalid_result()])

    query = query.replace("https://", "http://")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
    }
    ydl = CustomYoutubeDL(params=ydl_opts)
    info = ydl.extract_info(query)

    if ydl.error_message:
        return send_results([error_result()])

    formats = [
        {
            "format_id": format["format_id"],
            "resolution": format.get("resolution"),
            "tbr": format.get("tbr"),
            "fps": format.get("fps"),
        }
        for format in info["formats"]
        if format.get("resolution") and format.get("tbr")
    ]

    if not formats:
        return send_results([empty_result()])

    results = [
        query_result(
            query,
            str(info.get("thumbnail")),
            str(info.get("title")),
            format,
            d_path,
            pvf,
            paf,
        )
        for format in reversed(formats)
    ]
    return send_results(results)


@plugin.on_method
def download(
    url: str,
    format_id: str,
    download_path: str,
    pref_video_path: str,
    pref_audio_path: str,
    is_audio: bool,
) -> None:
    last_modified_time = datetime.fromtimestamp(os.path.getmtime(EXE_PATH))

    base_command = f'yt-dlp "{url}" -f {format_id}+ba -P {download_path} --windows-filenames --restrict-filenames --trim-filenames 50 --quiet --progress --no-mtime --force-overwrites --no-part'

    command = (
        f"{base_command} -U"
        if datetime.now() - last_modified_time >= timedelta(days=CHECK_INTERVAL_DAYS)
        else base_command
    )

    command = (
        f"{command} -x --audio-quality 0 --audio-format {pref_audio_path}"
        if is_audio
        else f"{command} --remux-video {pref_video_path}"
    )

    os.system(command)


if __name__ == "__main__":
    plugin.run()
