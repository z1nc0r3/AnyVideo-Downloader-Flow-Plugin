# Author: Lasith Manujitha
# Github: @z1nc0r3
# Description: A plugin to download videos from multiple websites
# Date: 2024-07-28

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass

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
    check_ytdlp_version,
    update_ytdlp_library,
    launch_plugin_setup,
)
from results import (
    init_results,
    invalid_result,
    error_result,
    empty_result,
    query_result,
    best_video_result,
    best_audio_result,
    ffmpeg_setup_result,
    ffmpeg_not_found_result,
    plugin_setup_in_progress_result,
    ytdlp_update_in_progress_result,
)
try:
    from ytdlp import CustomYoutubeDL
    YTDLP_AVAILABLE = True
except ImportError:
    CustomYoutubeDL = None
    YTDLP_AVAILABLE = False

PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))
CHECK_INTERVAL_DAYS = 7
DEFAULT_DOWNLOAD_PATH = str(Path.home() / "Downloads")

plugin = Plugin()


@dataclass
class PluginSettings:
    """Dataclass to manage plugin configuration settings."""
    download_path: str
    sorting_order: str
    pref_video_format: str
    pref_audio_format: str
    auto_open_folder: bool
    title_format: str
    subtitle_format: str
    best_video_title_format: str
    best_audio_title_format: str
    pin_best_results: bool


def fetch_settings() -> PluginSettings:
    """Fetches user settings with fallback logic."""
    try:
        download_path = settings().get("download_path") or DEFAULT_DOWNLOAD_PATH
        if not os.path.exists(download_path):
            download_path = DEFAULT_DOWNLOAD_PATH

        sorting_order = settings().get("sorting_order") or "Resolution"
        pref_video_format = settings().get("preferred_video_format") or "mp4"
        pref_audio_format = settings().get("preferred_audio_format") or "mp3"
        auto_open_folder = settings().get("auto_open_folder", True)

        title_format = settings().get("title_format") or "{title}"
        subtitle_format = settings().get("subtitle_format") or "Res: {resolution} ┃ {tbr} kbps ┃ Size: {size}MB ┃ FPS: {fps}"
        
        best_video_title_format = settings().get("best_video_title_format") or title_format
        best_audio_title_format = settings().get("best_audio_title_format") or title_format
        
        pin_best_results = settings().get("pin_best_results", True)
    except Exception:
        return PluginSettings(
            download_path=DEFAULT_DOWNLOAD_PATH,
            sorting_order="Resolution",
            pref_video_format="mp4",
            pref_audio_format="mp3",
            auto_open_folder=False,
            title_format="{title}",
            subtitle_format="Res: {resolution} ┃ {tbr} kbps ┃ Size: {size}MB ┃ FPS: {fps}",
            best_video_title_format="BEST VIDEO: {resolution}",
            best_audio_title_format="BEST AUDIO: {tbr} kbps",
            pin_best_results=True,
        )

    return PluginSettings(
        download_path,
        sorting_order,
        pref_video_format,
        pref_audio_format,
        auto_open_folder,
        title_format,
        subtitle_format,
        best_video_title_format,
        best_audio_title_format,
        pin_best_results,
    )


def format_result_text(template: str, full_title: str, fmt: dict) -> str:
    """Formats title/subtitle based on allowed formats."""
    short_title = full_title[:50] + "..." if len(full_title) > 50 else full_title
    res = fmt.get("resolution", "Unknown")
    tbr = f"{round(fmt['tbr'], 2)}" if fmt.get("tbr") else "0"
    size = f"{round(fmt['filesize'] / 1024 / 1024, 2)}" if fmt.get("filesize") else "0"
    fps = f"{int(fmt['fps'])}" if fmt.get("fps") else "0"

    try:
        return template.format(
            title=short_title,
            full_title=full_title,
            resolution=res,
            tbr=tbr,
            size=size,
            fps=fps
        )
    except Exception:
        return template


@plugin.on_method
def query(query: str) -> ResultResponse:
    cfg = fetch_settings()
    plugin_setup_lock = os.path.join(PLUGIN_ROOT, "plugin_setup.lock")
    if os.path.exists(plugin_setup_lock):
        try:
            lock_age = datetime.now() - datetime.fromtimestamp(
                os.path.getmtime(plugin_setup_lock)
            )
            if lock_age < timedelta(minutes=10):
                return send_results([plugin_setup_in_progress_result()])
            else:
                try:
                    os.remove(plugin_setup_lock)
                except Exception:
                    pass
        except Exception:
            return send_results([plugin_setup_in_progress_result()])

    verified, verify_reason = verify_ffmpeg()
    if not verified:
        if verify_reason and "setup in progress" in verify_reason.lower():
            return send_results([ffmpeg_setup_result(verify_reason)])
        launch_plugin_setup()
        return send_results([plugin_setup_in_progress_result()])

    extracted, extract_reason = extract_ffmpeg()
    if not extracted:
        launch_plugin_setup()
        return send_results([plugin_setup_in_progress_result()])

    # Check if yt-dlp is being updated (lock file created by update_ytdlp.py)
    ytdlp_update_lock = os.path.join(PLUGIN_ROOT, "..", "lib", ".ytdlp_updating")
    if os.path.exists(ytdlp_update_lock):
        try:
            lock_age = datetime.now() - datetime.fromtimestamp(
                os.path.getmtime(ytdlp_update_lock)
            )
            if lock_age < timedelta(minutes=10):
                return send_results([ytdlp_update_in_progress_result()])
            else:
                try:
                    os.remove(ytdlp_update_lock)
                except Exception:
                    pass
        except Exception:
            return send_results([ytdlp_update_in_progress_result()])

    if not YTDLP_AVAILABLE:
        launch_plugin_setup()
        return send_results([plugin_setup_in_progress_result()])

    if not query.strip():
        return send_results([init_results(cfg.download_path)])

    if not is_valid_url(query):
        return send_results([invalid_result()])

    query = query.replace("https://", "http://")

    ydl_opts = {"quiet": True, "no_warnings": True, "socket_timeout": 30}
    ydl = CustomYoutubeDL(params=ydl_opts)
    info = ydl.extract_info(query)

    if info is None:
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

    # Sort formats
    if cfg.sorting_order == "Resolution": formats = sort_by_resolution(formats)
    elif cfg.sorting_order == "File Size": formats = sort_by_size(formats)
    elif cfg.sorting_order == "Total Bitrate": formats = sort_by_tbr(formats)
    elif cfg.sorting_order == "FPS": formats = sort_by_fps(formats)

    best_results = []
    regular_results = []
    final_results = []
    added_format_ids = set() # To track added formats

    thumbnail = str(info.get("thumbnail") or "")
    full_title = str(info.get("title") or "Unknown Title")

    # --- Identify Best Results ---
    video_formats = [f for f in formats if f.get("resolution") and f["resolution"] != "audio only"]
    if video_formats:
        try:
            best_video = max(video_formats, key=lambda x: (
                tuple(map(int, x["resolution"].split("x"))) if x.get("resolution") and "x" in x["resolution"] else (0, 0),
                x.get("tbr") or 0,
            ))
            title = format_result_text(cfg.best_video_title_format, full_title, best_video)
            subtitle = format_result_text(cfg.subtitle_format, full_title, best_video)
            best_results.append(best_video_result(title, subtitle, query, thumbnail, best_video, cfg.download_path, cfg.pref_video_format, cfg.pref_audio_format, cfg.auto_open_folder))
            added_format_ids.add(best_video["format_id"])
        except (ValueError, TypeError): pass

    audio_formats = [f for f in formats if f.get("resolution") == "audio only"]
    if audio_formats:
        try:
            best_audio = max(audio_formats, key=lambda x: x.get("tbr") or 0)
            title = format_result_text(cfg.best_audio_title_format, full_title, best_audio)
            subtitle = format_result_text(cfg.subtitle_format, full_title, best_audio)
            best_results.append(best_audio_result(title, subtitle, query, thumbnail, best_audio, cfg.download_path, cfg.pref_video_format, cfg.pref_audio_format, cfg.auto_open_folder))
            added_format_ids.add(best_audio["format_id"])
        except (ValueError, TypeError): pass

    # --- Generate Regular Results (with deduplication) ---
    for format in formats:
        if format["format_id"] in added_format_ids:
            continue # Skip if already added as a best result
        
        title = format_result_text(cfg.title_format, full_title, format)
        subtitle = format_result_text(cfg.subtitle_format, full_title, format)
        regular_results.append(query_result(title, subtitle, query, thumbnail, format, cfg.download_path, cfg.pref_video_format, cfg.pref_audio_format, cfg.auto_open_folder))
        added_format_ids.add(format["format_id"])

    # --- Assemble Final List ---
    if cfg.pin_best_results:
        final_results.extend(best_results)
        final_results.extend(regular_results)
    else:
        final_results.extend(regular_results)
        final_results.extend(best_results)

    return send_results(final_results)

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
    """Executes the download command using yt-dlp."""
    if check_ytdlp_version(CHECK_INTERVAL_DAYS):
        update_ytdlp_library()

    exe_path = os.path.join(os.path.dirname(__file__), "yt-dlp.exe")
    ffmpeg_path = get_binaries_paths() or ""

    if is_audio:
        format_value = "bestaudio/best"
    else:
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

    command.append("-U")

    command = [arg for arg in command if arg is not None and arg != ""]

    try:
        result = subprocess.run(command)
        if result.returncode == 0 and auto_open_folder and os.path.isdir(download_path):
            os.startfile(download_path)
    except Exception:
        pass


if __name__ == "__main__":
    plugin.run()
