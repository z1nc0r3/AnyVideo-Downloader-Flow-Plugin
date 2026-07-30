from pyflowlauncher import Result


DOWNLOAD_METHOD = "download"


def _download_action(parameters):
    return {
        "Method": DOWNLOAD_METHOD,
        "Parameters": parameters,
        "DontHideAfterAction": False,
    }


def init_results(download_path) -> Result:
    return Result(
        title="Please input the video URL",
        subtitle=f"Download path: {download_path}",
        icon="Images/app.png",
    )


def invalid_result() -> Result:
    return Result(title="Please check the URL for errors.", icon="Images/error.png")


def ffmpeg_not_found_result() -> Result:
    return Result(
        title="FFmpeg binaries not found!",
        subtitle="Some features may not work as expected.",
        icon="Images/error.png",
    )


def error_result() -> Result:
    return Result(
        title="Something went wrong!",
        subtitle="Couldn't extract video information.",
        icon="Images/error.png",
    )


def empty_result() -> Result:
    return Result(title="Couldn't find any video formats.", icon="Images/error.png")


def cookie_file_error_result(issue) -> Result:
    return Result(
        title="Cookie file setting needs attention",
        subtitle=issue or "Please check the configured cookies.txt path.",
        icon="Images/error.png",
    )


def ffmpeg_setup_result(issue) -> Result:
    return Result(
        title="FFmpeg setup in progress...",
        subtitle=issue or "Please wait a few seconds and try again.",
        icon="Images/error.png",
    )


def plugin_setup_in_progress_result() -> Result:
    return Result(
        title="Plugin setup in progress...",
        subtitle="FFmpeg and yt-dlp are being installed. Please wait and try again.",
        icon="Images/app.png",
    )


def ytdlp_update_in_progress_result() -> Result:
    return Result(
        title="yt-dlp is being updated...",
        subtitle="Please wait a moment and try again.",
        icon="Images/app.png",
    )


def best_video_result(
    query,
    thumbnail,
    format,
    download_path,
    pref_video_path,
    pref_audio_path,
    auto_open_folder=False,
    overwrite_existing_files=True,
    cookie_file_path="",
) -> Result:
    result_title = "\u2605 BEST VIDEO QUALITY"
    if format.get("resolution"):
        result_title = f"\u2605 BEST VIDEO QUALITY [{format['resolution']}]"

    return Result(
        title=result_title,
        icon=thumbnail or "Images/app.png",
        json_rpc_action=_download_action(
            [
                query,
                f"{format['format_id']}",
                download_path,
                pref_video_path,
                pref_audio_path,
                False,
                auto_open_folder,
                overwrite_existing_files,
                cookie_file_path,
            ]
        ),
    )


def best_audio_result(
    query,
    thumbnail,
    format,
    download_path,
    pref_video_path,
    pref_audio_path,
    auto_open_folder=False,
    overwrite_existing_files=True,
    cookie_file_path="",
) -> Result:
    result_title = "\u2605 BEST AUDIO ONLY"
    if format.get("tbr"):
        result_title = f"\u2605 BEST AUDIO ONLY ({round(format['tbr'], 2)} kbps)"

    return Result(
        title=result_title,
        icon=thumbnail or "Images/app.png",
        json_rpc_action=_download_action(
            [
                query,
                f"{format['format_id']}",
                download_path,
                pref_video_path,
                pref_audio_path,
                True,
                auto_open_folder,
                overwrite_existing_files,
                cookie_file_path,
            ]
        ),
    )


def query_result(
    query,
    thumbnail,
    title,
    format,
    download_path,
    pref_video_path,
    pref_audio_path,
    auto_open_folder=False,
    overwrite_existing_files=True,
    cookie_file_path="",
) -> Result:
    subtitle_parts = [f"Res: {format['resolution']}"]

    if format.get("tbr") is not None:
        subtitle_parts.append(f"({round(format['tbr'], 2)} kbps)")

    if format.get("filesize"):
        size_mb = round(format["filesize"] / 1024 / 1024, 2)
        subtitle_parts.append(f"Size: {size_mb}MB")

    if format.get("fps"):
        subtitle_parts.append(f"FPS: {int(format['fps'])}")

    return Result(
        title=title,
        subtitle=" \u2503 ".join(subtitle_parts),
        icon=thumbnail or "Images/app.png",
        json_rpc_action=_download_action(
            [
                query,
                f"{format['format_id']}",
                download_path,
                pref_video_path,
                pref_audio_path,
                format["resolution"] == "audio only",
                auto_open_folder,
                overwrite_existing_files,
                cookie_file_path,
            ]
        ),
    )
