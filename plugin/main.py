# Author: Lasith Manujitha
# Github: @z1nc0r3
# Description: A plugin to download videos from multiple websites
# Date: 2024-07-28

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

from pyflowlauncher import Plugin, ResultResponse, send_results
from pyflowlauncher.settings import settings
from utils import (
    is_valid_url,
    sort_by_resolution,
    sort_by_tbr,
    sort_by_fps,
    sort_by_size,
    verify_ffmpeg_binaries,
    verify_ffmpeg,
    extract_ffmpeg,
    get_binaries_paths,
)
from results import (
    init_results,
    invalid_result,
    error_result,
    empty_result,
    query_result,
    download_ffmpeg_result,
    ffmpeg_not_found_result,
)
from ytdlp import CustomYoutubeDL

PLUGIN_ROOT = os.path.dirname(__file__)
EXE_PATH = os.path.join(PLUGIN_ROOT, "yt-dlp.exe")
CHECK_INTERVAL_DAYS = 5
DEFAULT_DOWNLOAD_PATH = str(Path.home() / "Downloads")


plugin = Plugin()


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


@plugin.on_method
def query(query: str) -> ResultResponse:
    d_path, sort, pvf, paf = fetch_settings()

    if verify_ffmpeg():
        return send_results([download_ffmpeg_result(PLUGIN_ROOT)])

    extract_ffmpeg()

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
            "format_id": format.get("format_id"),
            "resolution": format.get("resolution"),
            "filesize": format.get("filesize"),
            "tbr": format.get("tbr"),
            "fps": format.get("fps"),
        }
        for format in info.get("formats", [])
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

    results = []

    if verify_ffmpeg_binaries():
        results.extend([ffmpeg_not_found_result()])

    results.extend(
        [
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
    )
    return send_results(results)


@plugin.on_method
def download_ffmpeg_binaries(PLUGIN_ROOT) -> None:
    BIN_URL = (
        "https://github.com/z1nc0r3/ffmpeg-binaries/blob/main/ffmpeg-bin.zip?raw=true"
    )
    FFMPEG_ZIP = os.path.join(PLUGIN_ROOT, "ffmpeg.zip")
    command = f'curl -L "{BIN_URL}" -o "{FFMPEG_ZIP}"'

    subprocess.run(command)


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
    exe_path = os.path.join(os.path.dirname(__file__), "yt-dlp.exe")
    ffmpeg_path = get_binaries_paths()

    format = (
        f"-f b -x --audio-format {pref_audio_path} --audio-quality 0"
        if is_audio
        else f"-f {format_id}+ba[ext=mp3]/{format_id}+ba[ext=aac]/{format_id}+ba[ext=m4a]/{format_id}+ba[ext=wav]/{format_id}+ba --remux-video {pref_video_path}"
    )

    update = (
        f"-U"
        if datetime.now() - last_modified_time >= timedelta(days=CHECK_INTERVAL_DAYS)
        else ""
    )

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
        "--ffmpeg-location",
        ffmpeg_path,
        update,
    ]

    command = [arg for arg in command if arg]

    subprocess.run(command)


if __name__ == "__main__":
    plugin.run()
