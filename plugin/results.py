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
        SubTitle="Couldn't extract video information.",
        IcoPath="Images/error.png",
    )


def empty_result() -> Result:
    return Result(Title="Couldn't find any video formats.", IcoPath="Images/error.png")


def ffmpeg_setup_result(issue) -> Result:
    return Result(
        Title="FFmpeg setup in progress...",
        SubTitle=issue or "Please wait a few seconds and try again.",
        IcoPath="Images/error.png",
    )


def plugin_setup_in_progress_result() -> Result:
    return Result(
        Title="Plugin setup in progress...",
        SubTitle="FFmpeg and yt-dlp are being installed. Please wait and try again.",
        IcoPath="Images/app.png",
    )


def ytdlp_update_in_progress_result() -> Result:
    return Result(
        Title="yt-dlp is being updated...",
        SubTitle="Please wait a moment and try again.",
        IcoPath="Images/app.png",
    )


def best_video_result(
    title,
    subtitle,
    query,
    thumbnail,
    format,
    download_path,
    pref_video_path,
    pref_audio_path,
    auto_open_folder=False,
) -> Result:
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
                False,
                auto_open_folder,
            ],
        },
    )


def best_audio_result(
    title,
    subtitle,
    query,
    thumbnail,
    format,
    download_path,
    pref_video_path,
    pref_audio_path,
    auto_open_folder=False,
) -> Result:
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
                True,
                auto_open_folder,
            ],
        },
    )


def query_result(
    title,
    subtitle,
    query,
    thumbnail,
    format,
    download_path,
    pref_video_path,
    pref_audio_path,
    auto_open_folder=False,
) -> Result:
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
