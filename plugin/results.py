from pyflowlauncher import Result
import os
from datetime import datetime, timedelta

parent_folder_path = os.path.abspath(os.path.dirname(__file__))
EXE_PATH = os.path.join(parent_folder_path, "yt-dlp.exe")
CHECK_INTERVAL_DAYS = 10


def init_results() -> Result:
    return Result(Title="Please input the URL of the video", IcoPath="Images/app.png")


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


def query_result(info, format, download) -> Result:
    return Result(
        Title=info["title"],
        SubTitle=f"{format['resolution']} ({round(format['tbr'])} kbps) {'┃ Format: ' + str(format['ext']) if format.get('ext') else ''} {'┃ FPS: ' + str(format['fps']) if format.get('fps') else ''}",
        IcoPath=info.get("thumbnail") or "Images/app.png",
        JsonRPCAction={
            "method": "download",
            "parameters": [download, f"{format['format_id']}"],
        }
    )


# def download(url: str, format_id: str) -> None:
#     last_modified_time = datetime.fromtimestamp(os.path.getmtime(EXE_PATH))
#     base_command = f'yt-dlp "{url}" -f {format_id}+ba -P ~/Downloads/AnyDownloader --windows-filenames --restrict-filenames --trim-filenames 50 --quiet --progress --no-mtime --force-overwrites --no-part'
#     command = (
#         f"{base_command} -U"
#         if datetime.now() - last_modified_time >= timedelta(days=CHECK_INTERVAL_DAYS)
#         else base_command
#     )
#     os.system(command)
