from dataclasses import dataclass

from pyflowlauncher import Result


DOWNLOAD_METHOD = "download"
APP_ICON = "Images/app.png"
ERROR_ICON = "Images/error.png"


@dataclass(frozen=True)
class DownloadContext:
    url: str
    download_path: str
    pref_video_path: str
    pref_audio_path: str
    auto_open_folder: bool = False
    overwrite_existing_files: bool = True
    cookie_file_path: str = ""
    download_section: str = ""
    trim_start_time: str = ""
    trim_end_time: str = ""
    trim_mode: str = "Off"
    delete_original_after_trim: bool = False


def _download_action(parameters):
    return {
        "Method": DOWNLOAD_METHOD,
        "Parameters": parameters,
        "DontHideAfterAction": False,
    }


def _open_settings_action():
    return {
        "Method": "Flow.Launcher.OpenSettingDialog",
        "Parameters": [],
        "DontHideAfterAction": False,
    }


def _trim_subtitle(download_section):
    if not download_section:
        return None
    return f"Trim: {str(download_section).lstrip('*')}"


def _download_parameters(
    context,
    format_info,
    is_audio,
):
    return [
        context.url,
        f"{format_info['format_id']}",
        context.download_path,
        context.pref_video_path,
        context.pref_audio_path,
        is_audio,
        context.auto_open_folder,
        context.overwrite_existing_files,
        context.cookie_file_path,
        context.download_section,
        context.trim_start_time,
        context.trim_end_time,
        context.trim_mode,
        context.delete_original_after_trim,
    ]


def init_results(download_path) -> Result:
    return Result(
        title="Please input the video URL",
        subtitle=f"Download path: {download_path}",
        icon=APP_ICON,
    )


def invalid_result() -> Result:
    return Result(title="Please check the URL for errors.", icon=ERROR_ICON)


def ffmpeg_not_found_result() -> Result:
    return Result(
        title="FFmpeg binaries not found!",
        subtitle="Some features may not work as expected.",
        icon=ERROR_ICON,
    )


def error_result() -> Result:
    return Result(
        title="Something went wrong!",
        subtitle="Couldn't extract video information.",
        icon=ERROR_ICON,
    )


def empty_result() -> Result:
    return Result(title="Couldn't find any video formats.", icon=ERROR_ICON)


def cookie_file_error_result(issue) -> Result:
    return Result(
        title="Cookie file setting needs attention",
        subtitle=issue or "Please check the configured cookies.txt path.",
        icon=ERROR_ICON,
    )


def ffmpeg_setup_result(issue) -> Result:
    return Result(
        title="FFmpeg setup in progress...",
        subtitle=issue or "Please wait a few seconds and try again.",
        icon=ERROR_ICON,
    )


def trim_disabled_result() -> Result:
    return Result(
        title="Video trimming is disabled",
        subtitle="Press Enter to open Flow Launcher settings.",
        icon=ERROR_ICON,
        json_rpc_action=_open_settings_action(),
    )


def plugin_setup_in_progress_result() -> Result:
    return Result(
        title="Plugin setup in progress...",
        subtitle="FFmpeg and yt-dlp are being installed. Please wait and try again.",
        icon=APP_ICON,
    )


def ytdlp_update_in_progress_result() -> Result:
    return Result(
        title="yt-dlp is being updated...",
        subtitle="Please wait a moment and try again.",
        icon=APP_ICON,
    )


def best_video_result(context, thumbnail, format_info) -> Result:
    result_title = "\u2605 BEST VIDEO QUALITY"
    if format_info.get("resolution"):
        result_title = f"\u2605 BEST VIDEO QUALITY [{format_info['resolution']}]"

    return Result(
        title=result_title,
        subtitle=_trim_subtitle(context.download_section),
        icon=thumbnail or APP_ICON,
        json_rpc_action=_download_action(
            _download_parameters(
                context,
                format_info,
                False,
            )
        ),
    )


def best_audio_result(context, thumbnail, format_info) -> Result:
    result_title = "\u2605 BEST AUDIO ONLY"
    if format_info.get("tbr"):
        result_title = f"\u2605 BEST AUDIO ONLY ({round(format_info['tbr'], 2)} kbps)"

    return Result(
        title=result_title,
        subtitle=_trim_subtitle(context.download_section),
        icon=thumbnail or APP_ICON,
        json_rpc_action=_download_action(
            _download_parameters(
                context,
                format_info,
                True,
            )
        ),
    )


def query_result(context, thumbnail, title, format_info) -> Result:
    subtitle_parts = [f"Res: {format_info['resolution']}"]

    if format_info.get("tbr") is not None:
        subtitle_parts.append(f"({round(format_info['tbr'], 2)} kbps)")

    if format_info.get("filesize"):
        size_mb = round(format_info["filesize"] / 1024 / 1024, 2)
        subtitle_parts.append(f"Size: {size_mb}MB")

    if format_info.get("fps"):
        subtitle_parts.append(f"FPS: {int(format_info['fps'])}")

    if context.download_section:
        subtitle_parts.append(_trim_subtitle(context.download_section))

    return Result(
        title=title,
        subtitle=" \u2503 ".join(subtitle_parts),
        icon=thumbnail or APP_ICON,
        json_rpc_action=_download_action(
            _download_parameters(
                context,
                format_info,
                format_info["resolution"] == "audio only",
            )
        ),
    )
