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
    verify_ffmpeg_zip,
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

PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))
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
    except Exception:
        download_path = DEFAULT_DOWNLOAD_PATH
        sorting_order = "Resolution"
        pref_video_format = "mp4"
        pref_audio_format = "mp3"

    return download_path, sorting_order, pref_video_format, pref_audio_format


@plugin.on_method
def query(query: str) -> ResultResponse:
    d_path, sort, pvf, paf = fetch_settings()

    verified, verify_reason = verify_ffmpeg()
    if not verified:
        return send_results([download_ffmpeg_result(PLUGIN_ROOT, verify_reason)])

    extracted, extract_reason = extract_ffmpeg()
    if not extracted:
        return send_results([download_ffmpeg_result(PLUGIN_ROOT, extract_reason)])

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

    if not verify_ffmpeg_binaries():
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
    try:
        subprocess.run(
            ["curl", "-L", BIN_URL, "-o", FFMPEG_ZIP],
            check=True,
        )
    except Exception:
        # Fallback to shell invocation
        try:
            subprocess.run(f'curl -L "{BIN_URL}" -o "{FFMPEG_ZIP}"', shell=True, check=True)
        except Exception:
            pass

    if not os.path.exists(FFMPEG_ZIP):
        return

    zip_ok, zip_reason = verify_ffmpeg_zip(return_reason=True)
    if not zip_ok and zip_reason:
        print(f"FFmpeg download validation failed: {zip_reason}")


@plugin.on_method
def download(
    url: str,
    format_id: str,
    download_path: str,
    pref_video_path: str,
    pref_audio_path: str,
    is_audio: bool,
) -> None:
    try:
        last_modified_time = datetime.fromtimestamp(os.path.getmtime(EXE_PATH))
    except Exception:
        last_modified_time = None

    exe_path = os.path.join(os.path.dirname(__file__), "yt-dlp.exe")
    ffmpeg_path = get_binaries_paths() or ""

    if is_audio:
        format_value = "bestaudio/best"
    else:
        # If the user selected a specific format_id (e.g. "137"), try:
        # 1) <format_id>+bestaudio (video+audio merged)
        # 2) <format_id> (video only) — yt-dlp can later combine with audio if available
        # 3) bestvideo+bestaudio (best muxed)
        # 4) best (fallback)
        requested = str(format_id) if format_id else ""
        fallback_choices = []
        if requested:
            fallback_choices.append(f"{requested}+bestaudio")
            fallback_choices.append(f"{requested}")
        fallback_choices.append("bestvideo+bestaudio")
        fallback_choices.append("best")
        format_value = "/".join(fallback_choices)

    command = [exe_path, url, "-f", format_value]

    if is_audio:
        command += ["-x", "--audio-format", pref_audio_path or "mp3", "--audio-quality", "0"]
    else:
        if pref_video_path:
            command += ["--remux-video", pref_video_path]
        else:
            command += ["--remux-video", "mp4"]

    command += [
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
    ]

    if ffmpeg_path:
        command += ["--ffmpeg-location", ffmpeg_path]

    update_flag = ""
    if last_modified_time is not None:
        if datetime.now() - last_modified_time >= timedelta(days=CHECK_INTERVAL_DAYS):
            update_flag = "-U"
    else:
        # If we couldn't determine last modified time (exe missing), try updating
        update_flag = "-U"

    if update_flag:
        command.append(update_flag)

    command = [arg for arg in command if arg is not None and arg != ""]

    try:
        subprocess.run(command)
    except Exception:
        pass

if __name__ == "__main__":
    plugin.run()
