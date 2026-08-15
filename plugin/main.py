# Author: Lasith Manujitha
# Github: @z1nc0r3
# Description: A plugin to download videos from multiple websites
# Date: 2024-07-28

import os
import shutil
import subprocess
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from pyflowlauncher import Plugin, send_results
from pyflowlauncher.models.json_rpc import JsonRPCResponse as ResultResponse
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
    DownloadContext,
    init_results,
    invalid_result,
    error_result,
    empty_result,
    cookie_file_error_result,
    trim_disabled_result,
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
PLUGIN_CACHE_DIR = os.path.abspath(os.path.join(PLUGIN_ROOT, "..", ".cache"))
CHECK_INTERVAL_DAYS = 7
DEFAULT_DOWNLOAD_PATH = str(Path.home() / "Downloads")
MAX_FORMAT_RESULTS = 40
TRIM_MODE_OFF = "Off"
TRIM_MODE_NATIVE_SECTION = "Native section download"
TRIM_MODE_DOWNLOAD_THEN_TRIM = "Download then trim"
TRIM_MODES = (
    TRIM_MODE_OFF,
    TRIM_MODE_DOWNLOAD_THEN_TRIM,
    TRIM_MODE_NATIVE_SECTION,
)

plugin = Plugin()


@dataclass(frozen=True)
class PluginSettings:
    download_path: str
    sorting_order: str
    preferred_video_format: str
    preferred_audio_format: str
    auto_open_folder: bool
    overwrite_existing_files: bool
    trim_mode: str = TRIM_MODE_OFF
    delete_original_after_trim: bool = False
    cookie_file_path: str = ""
    cookie_file_error: str = ""


@dataclass(frozen=True)
class QueryRequest:
    url: str
    download_section: str = ""
    start_time: str = ""
    end_time: str = ""


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


def _normalize_trim_mode(mode: str) -> str:
    mode = str(mode or "").strip()
    return mode if mode in TRIM_MODES else TRIM_MODE_OFF


def _timestamp_seconds(token: str, allow_inf: bool = False):
    token = str(token or "").strip().lower()
    if token == "inf":
        return float("inf") if allow_inf else None

    if not token:
        return None

    parts = token.split(":")
    if len(parts) > 3:
        return None

    try:
        if len(parts) == 1:
            seconds = float(parts[0])
        else:
            if any(part == "" for part in parts):
                return None
            whole_parts = parts[:-1]
            if not all(part.isdigit() for part in whole_parts):
                return None
            seconds_part = float(parts[-1])
            if seconds_part >= 60:
                return None
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = minutes * 60 + seconds_part
            else:
                hours = int(parts[0])
                minutes = int(parts[1])
                if minutes >= 60:
                    return None
                seconds = hours * 3600 + minutes * 60 + seconds_part
    except ValueError:
        return None

    if seconds < 0:
        return None
    return seconds


def _build_download_section(start_time: str, end_time: str) -> str:
    start_time = str(start_time or "").strip().lower()
    end_time = str(end_time or "").strip().lower()

    start_seconds = _timestamp_seconds(start_time)
    end_seconds = _timestamp_seconds(end_time, allow_inf=True)
    if start_seconds is None or end_seconds is None:
        return ""
    if end_seconds != float("inf") and end_seconds <= start_seconds:
        return ""

    return f"*{start_time}-{end_time}"


def _parse_query_request(query: str) -> QueryRequest:
    parts = str(query or "").strip().split()
    if len(parts) < 3:
        return QueryRequest(str(query or "").strip())

    section = _build_download_section(parts[-2], parts[-1])
    if not section:
        return QueryRequest(str(query or "").strip())

    return QueryRequest(" ".join(parts[:-2]), section, parts[-2].lower(), parts[-1].lower())


def _create_trim_marker_path() -> str:
    os.makedirs(PLUGIN_CACHE_DIR, exist_ok=True)
    return os.path.join(PLUGIN_CACHE_DIR, f"trim-final-path-{uuid.uuid4().hex}.txt")


def _delete_file_if_exists(path: str) -> None:
    if not path:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as error:
        log_exception(f"Failed to delete file: {path}", error)


def _read_final_path_marker(marker_path: str) -> str:
    try:
        lines = Path(marker_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""

    for line in reversed(lines):
        final_path = line.strip().strip('"')
        if final_path:
            return final_path
    return ""


def _format_duration(seconds: float) -> str:
    if seconds == int(seconds):
        return str(int(seconds))
    return str(round(seconds, 3))


def _ffmpeg_exe_path(ffmpeg_path: str) -> str:
    return os.path.join(ffmpeg_path, "ffmpeg.exe") if ffmpeg_path else "ffmpeg"


def _trimmed_output_path(source_path: str, overwrite_existing_files: bool) -> str:
    source = Path(source_path)
    output = source.with_name(f"{source.stem} - trimmed{source.suffix}")
    if overwrite_existing_files or not output.exists():
        return str(output)

    index = 1
    while True:
        candidate = source.with_name(f"{source.stem} - trimmed ({index}){source.suffix}")
        if not candidate.exists():
            return str(candidate)
        index += 1


def _run_post_trim(
    final_path: str,
    start_time: str,
    end_time: str,
    ffmpeg_path: str,
    overwrite_existing_files: bool,
    delete_original_after_trim: bool,
) -> bool:
    final_path = normalize_path(final_path)
    if not os.path.isfile(final_path):
        log_message(f"Post-trim skipped. Downloaded file not found: {final_path}")
        return False

    start_seconds = _timestamp_seconds(start_time)
    end_seconds = _timestamp_seconds(end_time, allow_inf=True)
    if start_seconds is None or end_seconds is None:
        log_message(f"Post-trim skipped. Invalid time range: {start_time}-{end_time}")
        return False
    if end_seconds != float("inf") and end_seconds <= start_seconds:
        log_message(f"Post-trim skipped. Invalid time range: {start_time}-{end_time}")
        return False

    output_path = _trimmed_output_path(final_path, overwrite_existing_files)
    if os.path.abspath(final_path) == os.path.abspath(output_path):
        log_message(f"Post-trim skipped. Output path matches input path: {final_path}")
        return False

    command = [
        _ffmpeg_exe_path(ffmpeg_path),
        "-y" if overwrite_existing_files else "-n",
        "-ss",
        start_time,
        "-i",
        final_path,
    ]
    if end_seconds != float("inf"):
        command += ["-t", _format_duration(end_seconds - start_seconds)]
    command += ["-c", "copy", output_path]

    result = subprocess.run(command)
    if result.returncode != 0:
        log_message(f"Post-trim failed with exit code {result.returncode}.")
        return False

    if not os.path.isfile(output_path) or os.path.getsize(output_path) <= 0:
        log_message(f"Post-trim failed. Output missing or empty: {output_path}")
        return False

    if delete_original_after_trim:
        try:
            os.remove(final_path)
        except OSError as error:
            log_exception(
                f"Failed to delete original after post-trim: {final_path}",
                error,
            )

    return True


def _build_ydl_opts(cookie_file_path: str = ""):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "noplaylist": True,
        "ignore_no_formats_error": True,
    }
    if cookie_file_path:
        ydl_opts["cookiefile"] = cookie_file_path
    if _node_js_runtime_available():
        ydl_opts["js_runtimes"] = {"node": {}}
    return ydl_opts


def _build_format_choices(format_id: str, is_audio: bool):
    if is_audio:
        return ["bestaudio/best"]

    requested = str(format_id or "").strip()
    choices = []
    if requested:
        choices.append(requested)
        choices.append(f"{requested}+bestaudio")
    choices.append("bestvideo+bestaudio")
    choices.append("best")

    deduped = []
    seen = set()
    for choice in choices:
        if choice in seen:
            continue
        seen.add(choice)
        deduped.append(choice)
    return deduped


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


def _is_media_format(format_info) -> bool:
    ext = str(format_info.get("ext") or "").lower()
    protocol = str(format_info.get("protocol") or "").lower()
    format_note = str(format_info.get("format_note") or "").lower()

    if ext == "mhtml" or protocol == "mhtml" or "storyboard" in format_note:
        return False

    return not (
        format_info.get("vcodec") == "none"
        and format_info.get("acodec") == "none"
    )


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

    if not format_id or not _is_media_format(format_info):
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
        try:
            raw_formats = list(raw_formats)
        except TypeError:
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
        user_settings = plugin.settings
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
        trim_mode = _normalize_trim_mode(user_settings.get("trim_mode"))
        delete_original_after_trim = as_bool(
            user_settings.get("delete_original_after_trim", False), False
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
        trim_mode = TRIM_MODE_OFF
        delete_original_after_trim = False
        cookie_file_path = ""
        cookie_file_error = ""

    return PluginSettings(
        download_path=download_path,
        sorting_order=sorting_order,
        preferred_video_format=pref_video_format,
        preferred_audio_format=pref_audio_format,
        auto_open_folder=auto_open_folder,
        overwrite_existing_files=overwrite_existing_files,
        trim_mode=trim_mode,
        delete_original_after_trim=delete_original_after_trim,
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

    query_request = _parse_query_request(query)
    url = query_request.url
    download_section = query_request.download_section
    trim_mode = plugin_settings.trim_mode

    if not is_valid_url(url):
        return send_results([invalid_result()])

    if not has_extractable_url_target(url):
        return send_results([invalid_result()])

    if download_section and trim_mode == TRIM_MODE_OFF:
        return send_results([trim_disabled_result()])

    if plugin_settings.cookie_file_error:
        return send_results(
            [cookie_file_error_result(plugin_settings.cookie_file_error)]
        )

    active_cookie_file_path = plugin_settings.cookie_file_path
    ydl = CustomYoutubeDL(params=_build_ydl_opts(active_cookie_file_path))
    info = ydl.extract_info(url, download=False)

    if info is None:
        if active_cookie_file_path:
            active_cookie_file_path = ""
            ydl = CustomYoutubeDL(params=_build_ydl_opts())
            info = ydl.extract_info(url, download=False)

    if info is None:
        if ydl.error_message:
            log_message(f"Failed to extract video information: {ydl.error_message}")
        return send_results([error_result()])

    formats = _build_formats(info)

    if active_cookie_file_path and not formats and _get_raw_formats(info or {}):
        fallback_ydl = CustomYoutubeDL(params=_build_ydl_opts())
        fallback_info = fallback_ydl.extract_info(url, download=False)
        fallback_formats = _build_formats(fallback_info or {})
        if fallback_info is not None and fallback_formats:
            ydl = fallback_ydl
            info = fallback_info
            formats = fallback_formats
            active_cookie_file_path = ""

    if not formats:
        if ydl.error_message:
            log_message(f"Failed to build formats: {ydl.error_message}")
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
    download_context = DownloadContext(
        url=url,
        download_path=plugin_settings.download_path,
        pref_video_path=plugin_settings.preferred_video_format,
        pref_audio_path=plugin_settings.preferred_audio_format,
        auto_open_folder=plugin_settings.auto_open_folder,
        overwrite_existing_files=plugin_settings.overwrite_existing_files,
        cookie_file_path=active_cookie_file_path,
        download_section=download_section,
        trim_start_time=query_request.start_time,
        trim_end_time=query_request.end_time,
        trim_mode=trim_mode,
        delete_original_after_trim=plugin_settings.delete_original_after_trim,
    )

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
                    download_context,
                    thumbnail,
                    best_video,
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
                    download_context,
                    thumbnail,
                    best_audio,
                )
            )
        except (ValueError, TypeError) as e:
            log_exception("Failed to determine best audio format", e)

    results.extend(
        [
            query_result(
                download_context,
                thumbnail,
                title,
                format,
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
    download_section: str = "",
    trim_start_time: str = "",
    trim_end_time: str = "",
    trim_mode: str = TRIM_MODE_OFF,
    delete_original_after_trim: bool = False,
) -> None:
    if check_ytdlp_version(CHECK_INTERVAL_DAYS):
        update_ytdlp_library()

    exe_path = os.path.join(os.path.dirname(__file__), "yt-dlp.exe")
    ffmpeg_path = get_binaries_paths() or ""
    format_choices = _build_format_choices(format_id, is_audio)

    trim_mode = _normalize_trim_mode(trim_mode)
    download_section = str(download_section or "").strip()
    has_trim_range = bool(download_section)
    marker_path = ""

    command = [exe_path, url]

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
        "--no-mtime",
        "--no-playlist",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--file-access-retries",
        "5",
        "--extractor-retries",
        "3",
        "--retry-sleep",
        "http:exp=1:20",
        "--retry-sleep",
        "fragment:exp=1:20",
        "--http-chunk-size",
        "10M",
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

    if has_trim_range and trim_mode == TRIM_MODE_NATIVE_SECTION:
        command += [
            "--progress",
            "--newline",
            "--download-sections",
            download_section,
            "--downloader-args",
            "ffmpeg:-stats -stats_period 1 -progress pipe:2",
        ]
    elif has_trim_range and trim_mode == TRIM_MODE_DOWNLOAD_THEN_TRIM:
        marker_path = _create_trim_marker_path()
        command += [
            "--quiet",
            "--progress",
            "--print-to-file",
            "after_move:filepath",
            marker_path,
        ]
    else:
        command += ["--quiet", "--progress"]

    if _node_js_runtime_available():
        command += ["--js-runtimes", "node"]

    if ffmpeg_path:
        command += ["--ffmpeg-location", ffmpeg_path]

    command.append("-U")

    command = [arg for arg in command if arg is not None and arg != ""]

    try:
        result = None
        attempted_formats = []
        for format_choice in format_choices:
            attempt_command = command[:2] + ["-f", format_choice] + command[2:]
            attempted_formats.append(format_choice)

            if marker_path:
                _delete_file_if_exists(marker_path)

            result = subprocess.run(attempt_command)
            if result.returncode == 0:
                break

        if result.returncode != 0:
            log_message(
                "All download attempts failed. Last exit code "
                f"{result.returncode}. Formats tried: {', '.join(attempted_formats)}"
            )
        elif has_trim_range and trim_mode == TRIM_MODE_DOWNLOAD_THEN_TRIM:
            final_path = _read_final_path_marker(marker_path)
            if final_path:
                _run_post_trim(
                    final_path,
                    trim_start_time,
                    trim_end_time,
                    ffmpeg_path,
                    overwrite_existing_files,
                    delete_original_after_trim,
                )
            else:
                log_message("Post-trim skipped. Downloaded file path was not reported.")

        if result.returncode == 0 and auto_open_folder and os.path.isdir(download_path):
            os.startfile(download_path)
    except Exception as e:
        log_exception("Download command failed", e)
    finally:
        _delete_file_if_exists(marker_path)


if __name__ == "__main__":
    plugin.run()
