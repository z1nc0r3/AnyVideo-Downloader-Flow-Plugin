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

# Cache for settings to avoid repeated file reads
_settings_cache = None
_cache_time = None
CACHE_DURATION_SECONDS = 30  # Cache settings for 30 seconds


def fetch_settings() -> Tuple[str, str, str, str]:
    """
    Fetches the user settings for the plugin with caching to improve performance.

    Returns:
        Tuple[str, str, str, str]: A tuple containing:
            - download_path (str): The path where videos will be downloaded.
            - sorting_order (str): The order in which videos will be sorted (default is "Resolution").
            - pref_video_format (str): The preferred video format (default is "mp4").
            - pref_audio_format (str): The preferred audio format (default is "mp3").
    """
    global _settings_cache, _cache_time
    
    # Check if cache is valid
    current_time = datetime.now()
    if _settings_cache is not None and _cache_time is not None:
        if (current_time - _cache_time).total_seconds() < CACHE_DURATION_SECONDS:
            return _settings_cache
    
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

    # Update cache
    _settings_cache = (download_path, sorting_order, pref_video_format, pref_audio_format)
    _cache_time = current_time
    
    return _settings_cache


@plugin.on_method
def query(query: str) -> ResultResponse:
    d_path, sort, pvf, paf = fetch_settings()

    if not verify_ffmpeg():
        return send_results([download_ffmpeg_result(PLUGIN_ROOT)])

    # Extract ffmpeg only if the zip file exists (not on every query)
    if verify_ffmpeg_zip():
        extract_ffmpeg()

    if not query.strip():
        return send_results([init_results(d_path)])

    if not is_valid_url(query):
        return send_results([invalid_result()])

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
    }
    ydl = CustomYoutubeDL(params=ydl_opts)
    info = ydl.extract_info(query)

    if ydl.error_message:
        return send_results([error_result()])

    formats = []
    for format in info.get("formats", []):
        resolution = format.get("resolution")
        tbr = format.get("tbr")
        # Skip formats without resolution or tbr
        if not resolution or not tbr:
            continue
        formats.append({
            "format_id": format.get("format_id"),
            "resolution": resolution,
            "filesize": format.get("filesize"),
            "tbr": tbr,
            "fps": format.get("fps"),
        })

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

    # Only check binaries if we haven't verified ffmpeg already
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

    command = [EXE_PATH, url, "-f", format_value]

    if is_audio:
        command.extend(["-x", "--audio-format", pref_audio_path or "mp3", "--audio-quality", "0"])
    else:
        command.extend(["--remux-video", pref_video_path or "mp4"])

    command.extend([
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
    ])

    if ffmpeg_path:
        command.extend(["--ffmpeg-location", ffmpeg_path])

    # Check if update is needed:
    # - When exe is missing (last_modified_time is None)
    # - When CHECK_INTERVAL_DAYS have passed since last modification
    if last_modified_time is None or datetime.now() - last_modified_time >= timedelta(days=CHECK_INTERVAL_DAYS):
        command.append("-U")

    try:
        subprocess.run(command)
    except Exception:
        pass

if __name__ == "__main__":
    plugin.run()
