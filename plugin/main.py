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
    check_ytdlp_update_needed,
    skip_ytdlp_update,
    update_ytdlp_library,
)
from results import (
    init_results,
    invalid_result,
    error_result,
    empty_result,
    query_result,
    best_video_result,
    best_audio_result,
    download_ffmpeg_result,
    ffmpeg_setup_result,
    ffmpeg_not_found_result,
    update_ytdlp_result,
    ytdlp_update_in_progress_result,
)
from ytdlp import CustomYoutubeDL

PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.abspath(os.path.join(PLUGIN_ROOT, "..", "lib"))
EXE_PATH = os.path.join(PLUGIN_ROOT, "yt-dlp.exe")
CHECK_INTERVAL_DAYS = 5
DEFAULT_DOWNLOAD_PATH = str(Path.home() / "Downloads")

plugin = Plugin()


def fetch_settings() -> Tuple[str, str, str, str, bool]:
    """
    Fetches the user settings for the plugin.

    Returns:
        Tuple[str, str, str, str, bool]: A tuple containing:
            - download_path (str): The path where videos will be downloaded.
            - sorting_order (str): The order in which videos will be sorted (default is "Resolution").
            - pref_video_format (str): The preferred video format (default is "mp4").
            - pref_audio_format (str): The preferred audio format (default is "mp3").
            - auto_open_folder (bool): Whether to automatically open the download folder after download.
    """
    try:
        download_path = settings().get("download_path") or DEFAULT_DOWNLOAD_PATH
        if not os.path.exists(download_path):
            download_path = DEFAULT_DOWNLOAD_PATH

        sorting_order = settings().get("sorting_order") or "Resolution"
        pref_video_format = settings().get("preferred_video_format") or "mp4"
        pref_audio_format = settings().get("preferred_audio_format") or "mp3"
        auto_open_folder = settings().get("auto_open_folder", True)
    except Exception:
        download_path = DEFAULT_DOWNLOAD_PATH
        sorting_order = "Resolution"
        pref_video_format = "mp4"
        pref_audio_format = "mp3"
        auto_open_folder = False

    return (
        download_path,
        sorting_order,
        pref_video_format,
        pref_audio_format,
        auto_open_folder,
    )


@plugin.on_method
def query(query: str) -> ResultResponse:
    d_path, sort, pvf, paf, auto_open = fetch_settings()

    verified, verify_reason = verify_ffmpeg()
    if not verified:
        if verify_reason and "setup in progress" in verify_reason.lower():
            return send_results([ffmpeg_setup_result(verify_reason)])
        return send_results([download_ffmpeg_result(PLUGIN_ROOT, verify_reason)])

    extracted, extract_reason = extract_ffmpeg()
    if not extracted:
        return send_results([download_ffmpeg_result(PLUGIN_ROOT, extract_reason)])

    if not query.strip():
        return send_results([init_results(d_path)])

    if not is_valid_url(query):
        return send_results([invalid_result()])

    query = query.replace("https://", "http://")

    # Check if yt-dlp library needs update before processing
    update_lock = os.path.join(LIB_PATH, ".ytdlp_updating")

    # Check if update is in progress, but ignore stale locks
    if os.path.exists(update_lock):
        try:
            lock_age = datetime.now() - datetime.fromtimestamp(
                os.path.getmtime(update_lock)
            )
            if lock_age < timedelta(minutes=5):
                return send_results([ytdlp_update_in_progress_result()])
            else:
                try:
                    os.remove(update_lock)
                except Exception:
                    # Best-effort cleanup of stale update lock; ignore failures as they are non-fatal.
                    pass
        except Exception:
            # If we can't check lock age, assume update is in progress to be safe
            return send_results([ytdlp_update_in_progress_result()])

    if check_ytdlp_update_needed(CHECK_INTERVAL_DAYS):
        try:
            import yt_dlp

            current_version = yt_dlp.version.__version__
        except:
            current_version = None
        return send_results(update_ytdlp_result(current_version))

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
    }
    ydl = CustomYoutubeDL(params=ydl_opts)
    info = ydl.extract_info(query)

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
        if ydl.error_message:
            return send_results([error_result()])
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

    # Extract common info with trimmed title
    thumbnail = str(info.get("thumbnail") or "")
    full_title = str(info.get("title") or "Unknown Title")
    title = full_title[:50] + "..." if len(full_title) > 50 else full_title

    # Find best video (highest resolution, then highest bitrate)
    video_formats = [f for f in formats if f.get("resolution") and f["resolution"] != "audio only"]
    if video_formats:
        try:
            best_video = max(
                video_formats,
                key=lambda x: (
                    tuple(map(int, x["resolution"].split("x"))) if x.get("resolution") and "x" in x["resolution"] else (0, 0),
                    x.get("tbr") or 0,
                ),
            )
            results.append(
                best_video_result(
                    query,
                    thumbnail,
                    best_video,
                    d_path,
                    pvf,
                    paf,
                    auto_open,
                )
            )
        except (ValueError, TypeError):
            pass  # Skip if we can't determine best video

    # Find best audio (highest bitrate)
    audio_formats = [f for f in formats if f.get("resolution") == "audio only"]
    if audio_formats:
        try:
            best_audio = max(audio_formats, key=lambda x: x.get("tbr") or 0)
            results.append(
                best_audio_result(
                    query,
                    thumbnail,
                    best_audio,
                    d_path,
                    pvf,
                    paf,
                    auto_open,
                )
            )
        except (ValueError, TypeError):
            pass  # Skip if we can't determine best audio

    results.extend(
        [
            query_result(
                query,
                thumbnail,
                title,
                format,
                d_path,
                pvf,
                paf,
                auto_open,
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
    lock_path = os.path.join(PLUGIN_ROOT, "ffmpeg_setup.lock")

    # Create a lock to indicate setup is in progress so queries can avoid re-triggering.
    try:
        with open(lock_path, "w", encoding="utf-8") as lock_file:
            lock_file.write("in-progress")
    except Exception:
        pass

    try:
        try:
            subprocess.run(
                ["curl", "-L", BIN_URL, "-o", FFMPEG_ZIP],
                check=True,
            )
        except Exception:
            try:
                subprocess.run(
                    f'curl -L "{BIN_URL}" -o "{FFMPEG_ZIP}"', shell=True, check=True
                )
            except Exception:
                pass

        if not os.path.exists(FFMPEG_ZIP):
            return

        zip_ok, _ = verify_ffmpeg_zip(return_reason=True)
        if not zip_ok:
            try:
                os.remove(FFMPEG_ZIP)
            except Exception:
                pass
            return

        extract_ffmpeg()
    finally:
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception:
            pass


@plugin.on_method
def update_ytdlp_library_action() -> None:
    """Update the yt-dlp library when user clicks the update prompt.

    Launches the update script in a separate terminal window.
    The script handles its own lock file management.
    """
    update_ytdlp_library()


@plugin.on_method
def skip_ytdlp_update_action() -> None:
    """Skip the yt-dlp update and use the current bundled version."""
    skip_ytdlp_update()


@plugin.on_method
def download(
    url: str,
    format_id: str,
    download_path: str,
    pref_video_path: str,
    pref_audio_path: str,
    is_audio: bool,
    auto_open_folder: bool = False,
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
        command += [
            "-x",
            "--audio-format",
            pref_audio_path or "mp3",
            "--audio-quality",
            "0",
        ]
    else:
        if pref_video_path:
            command += ["--remux-video", pref_video_path]
        else:
            command += ["--remux-video", "mp4"]

    command += [
        "-P",
        download_path,
        "--output",
        "%(title).100s.%(ext)s",
        "--windows-filenames",
        "--restrict-filenames",
        "--trim-filenames",
        "100",
        "--quiet",
        "--progress",
        "--no-mtime",
        "--force-overwrites",
        "--no-part",
        "--retries",
        "3",
        "--retry-sleep",
        "2",
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
        result = subprocess.run(command)
        if result.returncode == 0 and auto_open_folder and os.path.isdir(download_path):
            os.startfile(download_path)
    except Exception:
        pass


if __name__ == "__main__":
    plugin.run()
