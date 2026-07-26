# Author: Lasith Manujitha
# Github: @z1nc0r3
# Description: A plugin to download videos from multiple websites
# Date: 2024-07-28

import os
import subprocess
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from pyflowlauncher import Plugin, ResultResponse, send_results
from pyflowlauncher.settings import settings
from utils import (
    as_bool,
    normalize_path,
    is_valid_url,
    has_extractable_url_target,
    sort_by_resolution,
    sort_by_tbr,
    sort_by_fps,
    sort_by_size,
    resolution_value,
    numeric_value,
    log_message,
    log_exception,
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
    cookie_file_error_result,
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
MAX_FORMAT_RESULTS = 40

plugin = Plugin()


@dataclass(frozen=True)
class PluginSettings:
    download_path: str
    sorting_order: str
    preferred_video_format: str
    preferred_audio_format: str
    auto_open_folder: bool
    overwrite_existing_files: bool
    cookie_file_path: str = ""
    cookie_file_error: str = ""


def _normalize_download_path(download_path: str) -> str:
    expanded = normalize_path(download_path)
    return expanded if os.path.exists(expanded) else DEFAULT_DOWNLOAD_PATH


def _resolve_cookie_file_settings(user_settings) -> Tuple[str, str]:
    if not as_bool(user_settings.get("use_cookie_file", False), False):
        return "", ""

    cookie_file_path = normalize_path(user_settings.get("cookie_file_path") or "")
    if not cookie_file_path:
        return "", "Cookie file support is enabled, but no cookies.txt path is configured."

    if not os.path.isfile(cookie_file_path):
        return "", f"Cookie file not found: {cookie_file_path}"

    return cookie_file_path, ""


def _node_js_runtime_available() -> bool:
    return shutil.which("node") is not None


def _build_ydl_opts(cookie_file_path: str = ""):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "noplaylist": True,
    }
    if cookie_file_path:
        ydl_opts["cookiefile"] = cookie_file_path
    if _node_js_runtime_available():
        ydl_opts["js_runtimes"] = {"node": {}}
    return ydl_opts


def _format_resolution(format_info):
    resolution = format_info.get("resolution")
    if resolution and resolution != "unknown":
        return resolution

    width = numeric_value(format_info.get("width"))
    height = numeric_value(format_info.get("height"))
    if width > 0 and height > 0:
        return f"{int(width)}x{int(height)}"

    if format_info.get("vcodec") == "none":
        return "audio only"

    return None


def _append_format(formats, seen, format_info, allow_unknown=False):
    format_id = format_info.get("format_id")
    resolution = _format_resolution(format_info)
    filesize = numeric_value(
        format_info.get("filesize") or format_info.get("filesize_approx"), None
    )
    tbr = numeric_value(format_info.get("tbr"), None)
    fps = numeric_value(format_info.get("fps"), None)
    width = numeric_value(format_info.get("width"), None)
    height = numeric_value(format_info.get("height"), None)

    if not format_id:
        return

    if not resolution and allow_unknown and format_info.get("url"):
        resolution = "unknown"

    if not resolution:
        return
    if not allow_unknown and not tbr and not filesize:
        return

    normalized = {
        "format_id": format_id,
        "resolution": resolution,
        "filesize": filesize,
        "tbr": tbr,
        "fps": fps,
        "width": width,
        "height": height,
        "vcodec": format_info.get("vcodec"),
        "acodec": format_info.get("acodec"),
        "ext": format_info.get("ext"),
    }
    dedupe_key = (
        normalized["format_id"],
        normalized["resolution"],
        normalized["tbr"],
        normalized["filesize"],
        normalized["fps"],
    )
    if dedupe_key in seen:
        return

    seen.add(dedupe_key)
    formats.append(normalized)


def _get_raw_formats(info):
    raw_formats = info.get("formats") or []
    if not isinstance(raw_formats, (list, tuple)):
        raw_formats = []

    if not raw_formats and info.get("format_id") and info.get("url"):
        raw_formats = [info]

    return raw_formats


def _build_formats(info):
    formats = []
    seen = set()
    raw_formats = _get_raw_formats(info)

    for format_info in raw_formats:
        if not isinstance(format_info, dict):
            continue
        _append_format(formats, seen, format_info)

    if not formats:
        for format_info in raw_formats:
            if not isinstance(format_info, dict):
                continue
            _append_format(formats, seen, format_info, allow_unknown=True)

    return formats


def fetch_settings() -> PluginSettings:
    """
    Fetches the user settings for the plugin.
    """
    try:
        user_settings = settings()
        download_path = _normalize_download_path(
            user_settings.get("download_path") or DEFAULT_DOWNLOAD_PATH
        )

        sorting_order = user_settings.get("sorting_order") or "Resolution"
        pref_video_format = user_settings.get("preferred_video_format") or "mp4"
        pref_audio_format = user_settings.get("preferred_audio_format") or "mp3"
        auto_open_folder = as_bool(user_settings.get("auto_open_folder", True), True)
        overwrite_existing_files = as_bool(
            user_settings.get("overwrite_existing_files", True), True
        )
        cookie_file_path, cookie_file_error = _resolve_cookie_file_settings(
            user_settings
        )
    except Exception:
        download_path = DEFAULT_DOWNLOAD_PATH
        sorting_order = "Resolution"
        pref_video_format = "mp4"
        pref_audio_format = "mp3"
        auto_open_folder = False
        overwrite_existing_files = True
        cookie_file_path = ""
        cookie_file_error = ""

    return PluginSettings(
        download_path=download_path,
        sorting_order=sorting_order,
        preferred_video_format=pref_video_format,
        preferred_audio_format=pref_audio_format,
        auto_open_folder=auto_open_folder,
        overwrite_existing_files=overwrite_existing_files,
        cookie_file_path=cookie_file_path,
        cookie_file_error=cookie_file_error,
    )


@plugin.on_method
def query(query: str) -> ResultResponse:
    plugin_settings = fetch_settings()

    # Check if combined plugin setup is in progress
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
        return send_results([init_results(plugin_settings.download_path)])

    if not is_valid_url(query):
        return send_results([invalid_result()])

    if not has_extractable_url_target(query):
        return send_results([invalid_result()])

    if plugin_settings.cookie_file_error:
        return send_results(
            [cookie_file_error_result(plugin_settings.cookie_file_error)]
        )

    ydl = CustomYoutubeDL(params=_build_ydl_opts(plugin_settings.cookie_file_path))
    info = ydl.extract_info(query)

    if info is None:
        if ydl.error_message:
            log_message(f"Failed to extract video information: {ydl.error_message}")
        return send_results([error_result()])

    formats = _build_formats(info)

    if not formats:
        if ydl.error_message:
            return send_results([error_result()])
        return send_results([empty_result()])

    try:
        if plugin_settings.sorting_order == "Resolution":
            formats = sort_by_resolution(formats)
        elif plugin_settings.sorting_order == "File Size":
            formats = sort_by_size(formats)
        elif plugin_settings.sorting_order == "Total Bitrate":
            formats = sort_by_tbr(formats)
        elif plugin_settings.sorting_order == "FPS":
            formats = sort_by_fps(formats)
    except Exception as e:
        log_exception("Failed to sort formats", e)
        formats = sort_by_resolution(formats)

    formats = formats[:MAX_FORMAT_RESULTS]

    results = []

    if not verify_ffmpeg_binaries():
        results.extend([ffmpeg_not_found_result()])

    # Extract common info with trimmed title
    thumbnail = str(info.get("thumbnail") or "")
    full_title = str(info.get("title") or "Unknown Title")
    title = full_title[:50] + "..." if len(full_title) > 50 else full_title

    # Find best video (highest resolution, then highest bitrate)
    video_formats = [
        f
        for f in formats
        if f.get("resolution") and f["resolution"] not in ("audio only", "unknown")
    ]
    if video_formats:
        try:
            best_video = max(
                video_formats,
                key=lambda x: (
                    resolution_value(x),
                    x.get("tbr") or 0,
                ),
            )
            results.append(
                best_video_result(
                    query,
                    thumbnail,
                    best_video,
                    plugin_settings.download_path,
                    plugin_settings.preferred_video_format,
                    plugin_settings.preferred_audio_format,
                    plugin_settings.auto_open_folder,
                    plugin_settings.overwrite_existing_files,
                    plugin_settings.cookie_file_path,
                )
            )
        except (ValueError, TypeError) as e:
            log_exception("Failed to determine best video format", e)

    # Find best audio (highest bitrate)
    audio_formats = [f for f in formats if f.get("resolution") == "audio only"]
    if audio_formats:
        try:
            best_audio = max(audio_formats, key=lambda x: numeric_value(x.get("tbr")))
            results.append(
                best_audio_result(
                    query,
                    thumbnail,
                    best_audio,
                    plugin_settings.download_path,
                    plugin_settings.preferred_video_format,
                    plugin_settings.preferred_audio_format,
                    plugin_settings.auto_open_folder,
                    plugin_settings.overwrite_existing_files,
                    plugin_settings.cookie_file_path,
                )
            )
        except (ValueError, TypeError) as e:
            log_exception("Failed to determine best audio format", e)

    results.extend(
        [
            query_result(
                query,
                thumbnail,
                title,
                format,
                plugin_settings.download_path,
                plugin_settings.preferred_video_format,
                plugin_settings.preferred_audio_format,
                plugin_settings.auto_open_folder,
                plugin_settings.overwrite_existing_files,
                plugin_settings.cookie_file_path,
            )
            for format in formats
        ]
    )
    return send_results(results)


@plugin.on_method
def download(
    url: str,
    format_id: str,
    download_path: str,
    pref_video_path: str,
    pref_audio_path: str,
    is_audio: bool,
    auto_open_folder: bool = False,
    overwrite_existing_files: bool = True,
    cookie_file_path: str = "",
) -> None:
    if check_ytdlp_version(CHECK_INTERVAL_DAYS):
        update_ytdlp_library()

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
        "--no-playlist",
        "--no-part",
        "--retries",
        "3",
        "--retry-sleep",
        "2",
    ]

    if overwrite_existing_files:
        command.append("--force-overwrites")

    cookie_file_path = normalize_path(cookie_file_path)
    if cookie_file_path:
        if os.path.isfile(cookie_file_path):
            command += ["--cookies", cookie_file_path]
        else:
            log_message(
                f"Configured cookie file not found during download: {cookie_file_path}"
            )

    if _node_js_runtime_available():
        command += ["--js-runtimes", "node"]

    if ffmpeg_path:
        command += ["--ffmpeg-location", ffmpeg_path]

    command.append("-U")

    command = [arg for arg in command if arg is not None and arg != ""]

    try:
        result = subprocess.run(command)
        if result.returncode == 0 and auto_open_folder and os.path.isdir(download_path):
            os.startfile(download_path)
    except Exception as e:
        log_exception("Download command failed", e)


if __name__ == "__main__":
    plugin.run()
