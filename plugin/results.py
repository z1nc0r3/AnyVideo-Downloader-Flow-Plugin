from pyflowlauncher import Result


def init_results(download_path) -> Result:
    return Result(
        Title="Please input the video URL",
        SubTitle=f"Download path: {download_path}",
        IcoPath="Images/app.png",
    )


def invalid_result() -> Result:
    return Result(Title="Please check the URL for errors.", IcoPath="Images/error.png")


def ffmpeg_not_found_result() -> Result:
    return Result(
        Title="FFmpeg binaries not found!",
        SubTitle="Some features may not work as expected.",
        IcoPath="Images/error.png",
    )


def error_result() -> Result:
    return Result(
        Title="Something went wrong!",
        SubTitle=f"Couldn't extract video information.",
        IcoPath="Images/error.png",
    )


def empty_result() -> Result:
    return Result(Title="Couldn't find any video formats.", IcoPath="Images/error.png")


def download_ffmpeg_result(dest_path, issue=None) -> Result:
    subtitle = "Click this to download FFmpeg binaries."
    title = "FFmpeg binaries not found!"
    if issue:
        subtitle = f"{issue} Click this to download FFmpeg binaries."
        title = "FFmpeg binaries issue!"
    return Result(
        Title=title,
        SubTitle=subtitle,
        IcoPath="Images/error.png",
        JsonRPCAction={"method": "download_ffmpeg_binaries", "parameters": [dest_path]},
    )


def ffmpeg_setup_result(issue) -> Result:
    return Result(
        Title="FFmpeg setup in progress...",
        SubTitle=issue or "Please wait a few seconds and try again.",
        IcoPath="Images/error.png",
    )


def setup_all_result(dest_path, issue=None) -> Result:
    subtitle = "Click to download FFmpeg and update yt-dlp in one step."
    title = "Initial setup required!"
    if issue:
        subtitle = f"{issue} Click to set up all dependencies."
    return Result(
        Title=title,
        SubTitle=subtitle,
        IcoPath="Images/error.png",
        JsonRPCAction={"method": "setup_all_action", "parameters": [dest_path]},
    )


def update_ytdlp_result(current_version=None) -> list:
    """Returns a list of results: update option and skip option."""
    subtitle = "Click to update yt-dlp library to the latest version."
    if current_version:
        subtitle = f"Current version: {current_version}. Click to update."

    update_result = Result(
        Title="yt-dlp library update available!",
        SubTitle=subtitle,
        IcoPath="Images/app.png",
        JsonRPCAction={"method": "update_ytdlp_library_action", "parameters": []},
    )

    skip_result = Result(
        Title="Skip update (use current version)",
        SubTitle="Continue using the bundled yt-dlp. Will check again in 5 days.",
        IcoPath="Images/app.png",
        JsonRPCAction={"method": "skip_ytdlp_update_action", "parameters": []},
    )

    return [update_result, skip_result]


def ytdlp_update_in_progress_result() -> Result:
    return Result(
        Title="yt-dlp update in progress...",
        SubTitle="Please wait a moment and try again.",
        IcoPath="Images/app.png",
    )


def best_video_result(
    query,
    thumbnail,
    format,
    download_path,
    pref_video_path,
    pref_audio_path,
    auto_open_folder=False,
) -> Result:
    result_title = "★ BEST VIDEO QUALITY"
    if format.get("resolution"):
        result_title = f"★ BEST VIDEO QUALITY [{format['resolution']}]"
    
    return Result(
        Title=result_title,
        IcoPath=thumbnail or "Images/app.png",
        JsonRPCAction={
            "method": "download",
            "parameters": [
                query,
                f"{format['format_id']}",
                download_path,
                pref_video_path,
                pref_audio_path,
                False,
                auto_open_folder,
            ],
        },
    )


def best_audio_result(
    query,
    thumbnail,
    format,
    download_path,
    pref_video_path,
    pref_audio_path,
    auto_open_folder=False,
) -> Result:
    result_title = "★ BEST AUDIO ONLY"
    if format.get("tbr"):
        result_title = f"★ BEST AUDIO ONLY ({round(format['tbr'], 2)} kbps)"
    
    return Result(
        Title=result_title,
        IcoPath=thumbnail or "Images/app.png",
        JsonRPCAction={
            "method": "download",
            "parameters": [
                query,
                f"{format['format_id']}",
                download_path,
                pref_video_path,
                pref_audio_path,
                True,
                auto_open_folder,
            ],
        },
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
) -> Result:
    # Build subtitle with consistent spacing
    subtitle_parts = [f"Res: {format['resolution']}"]

    if format.get("tbr") is not None:
        subtitle_parts.append(f"({round(format['tbr'], 2)} kbps)")

    if format.get("filesize"):
        size_mb = round(format["filesize"] / 1024 / 1024, 2)
        subtitle_parts.append(f"Size: {size_mb}MB")

    if format.get("fps"):
        subtitle_parts.append(f"FPS: {int(format['fps'])}")

    subtitle = " ┃ ".join(subtitle_parts)

    return Result(
        Title=title,
        SubTitle=subtitle,
        IcoPath=thumbnail or "Images/app.png",
        JsonRPCAction={
            "method": "download",
            "parameters": [
                query,
                f"{format['format_id']}",
                download_path,
                pref_video_path,
                pref_audio_path,
                format["resolution"] == "audio only",
                auto_open_folder,
            ],
        },
    )
