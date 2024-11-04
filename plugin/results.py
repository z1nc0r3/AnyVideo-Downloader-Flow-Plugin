from pyflowlauncher import Result


def init_results(download_path) -> Result:
    return Result(
        Title="Please input the video URL",
        SubTitle=f"Download path: {download_path}",
        IcoPath="Images/app.png",
    )


def invalid_result() -> Result:
    return Result(Title="Please check the URL for errors.", IcoPath="Images/error.png")


def error_result() -> Result:
    return Result(
        Title="Something went wrong!",
        SubTitle="Couldn't extract video information.",
        IcoPath="Images/error.png",
    )


def empty_result() -> Result:
    return Result(Title="Couldn't find any video formats.", IcoPath="Images/error.png")


def query_result(
    query, thumbnail, title, format, download_path, pref_video_path, pref_audio_path
) -> Result:
    return Result(
        Title=title,
        SubTitle=f"Res: {format['resolution']} ({round(format['tbr'], 2)} kbps) {'┃ Size: ' + str(round(format['filesize'] / 1024 / 1024, 2)) + 'MB' if format.get('filesize') else ''} {'┃ FPS: ' + str(int(format['fps'])) if format.get('fps') else ''}",
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
            ],
        },
    )
