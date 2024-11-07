# Author: Lasith Manujitha
# Github: @z1nc0r3
# Description: A plugin to download videos from multiple websites
# Date: 2024-07-28

import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

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
URL_REGEX = (
    "((http|https)://)(www.)?"
    + "[a-zA-Z0-9@:%._\\+~#?&//=]"
    + "{1,256}\\.[a-z]"
    + "{2,6}\\b([-a-zA-Z0-9@:%"
    + "._\\+~#?&//=]*)"
)

plugin = Plugin()


def is_valid_url(url: str) -> bool:
    """
    Check if the given URL is valid based on a predefined regex pattern.

    Args:
        url (str): The URL string to validate.

    Returns:
        bool: True if the URL matches the regex pattern, False otherwise.
    """

    return bool(re.match(URL_REGEX, url))


def fetch_settings() -> Tuple[str, str, str, str]:
    """
    Fetches the user settings for the plugin.

    Returns:
        Tuple[str, str, str, str]: A tuple containing:
            - download_path (str): The path where videos will be downloaded.
            - sorting_order (str): The order in which videos will be sorted (default is "Resolution").
            - pref_video_format (str): The preferred video format (default is "mp4").
            - pref_audio_format (str): The preferred audio format (default is "mp3").
    """
    try:
        download_path = settings().get("download_path") or DEFAULT_DOWNLOAD_PATH
        if not os.path.exists(download_path):
            download_path = DEFAULT_DOWNLOAD_PATH

        sorting_order = settings().get("sorting_order") or "Resolution"
        pref_video_format = settings().get("preferred_video_format") or "mp4"
        pref_audio_format = settings().get("preferred_audio_format") or "mp3"
    except Exception as _:
        download_path = DEFAULT_DOWNLOAD_PATH
        sorting_order = "Resolution"
        pref_video_format = "mp4"
        pref_audio_format = "mp3"

    return download_path, sorting_order, pref_video_format, pref_audio_format


def sort_by_resolution(formats):
    """
    Sorts a list of video formats by their resolution in descending order.

    Returns:
        list of dict: The list of video formats sorted by resolution in descending order.
                      Audio-only formats are considered to have the lowest resolution.
    """

    def resolution_to_tuple(resolution):
        if resolution == "audio only":
            return (0, 0)
        return tuple(map(int, resolution.split("x")))

    return sorted(
        formats, key=lambda x: resolution_to_tuple(x["resolution"]), reverse=True
    )


def sort_by_tbr(formats):
    """
    Sort a list of video formats by their 'tbr' (total bitrate) in descending order.

    Returns:
        list: The input list sorted by the 'tbr' value in descending order.
    """
    return sorted(formats, key=lambda x: x["tbr"], reverse=True)


def sort_by_fps(formats):
    """
    Sort a list of video formats by frames per second (fps) in descending order.

    Returns:
        list of dict: The list of video formats sorted by fps in descending order.
                      Formats with None fps values are placed at the end.
    """
    return sorted(
        formats,
        key=lambda x: (
            x["fps"] is None,
            -x["fps"] if x["fps"] is not None else float("-inf"),
        ),
    )


def sort_by_size(formats):
    """
    Sort a list of video formats by their file size in descending order.

    Returns:
        list of dict: The list of video formats sorted by file size in
                      descending order. Formats with no file size information
                      (None) are placed at the end of the list.
    """
    return sorted(
        formats,
        key=lambda x: (
            x["filesize"] is None,
            -x["filesize"] if x["filesize"] is not None else float("-inf"),
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
            "filesize": format.get("filesize"),
            "tbr": format.get("tbr"),
            "fps": format.get("fps"),
        }
        for format in info["formats"]
        if format.get("resolution") and format.get("tbr")
    ]

    if not formats:
        return send_results([empty_result()])

    if sort == "Resolution":
        formats = sort_by_resolution(formats)
    elif sort == "File Size":
        formats = sort_by_size(formats)
    elif sort == "Total Bitrate":
        formats = sort_by_tbr(formats)
    elif sort == "FPS":
        formats = sort_by_fps(formats)

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
        for format in formats
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

    format = (
        f"-f ba -x --audio-format {pref_audio_path}"
        if is_audio
        else f"-f {format_id}+ba --remux-video {pref_video_path}"
    )

    update = (
        f"-U"
        if datetime.now() - last_modified_time >= timedelta(days=CHECK_INTERVAL_DAYS)
        else ""
    )

    command = f'yt-dlp "{url}" {format} -P {download_path} --windows-filenames --restrict-filenames --trim-filenames 50 --quiet --progress --no-mtime --force-overwrites --no-part {update}'

    exe_path = os.path.join(os.path.dirname(__file__), "yt-dlp.exe")
    command = [
        exe_path,
        url,
        *format.split(),
        "-P",
        download_path,
        "--windows-filenames",
        "--restrict-filenames",
        "--trim-filenames",
        "50",
        "--quiet",
        "--progress",
        "--no-mtime",
        "--force-overwrites",
        "--no-part",
        update,
    ]

    command = [arg for arg in command if arg]
    subprocess.run(command)


if __name__ == "__main__":
    plugin.run()
