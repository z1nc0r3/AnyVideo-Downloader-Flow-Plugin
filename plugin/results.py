from pyflowlauncher import Result


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


def query_result(query, info, format) -> Result:
    return Result(
        Title=info["title"],
        SubTitle=f"{format['resolution']} ({round(format['tbr'])} kbps) {'┃ Format: ' + str(format['ext']) if format.get('ext') else ''} {'┃ FPS: ' + str(format['fps']) if format.get('fps') else ''}",
        IcoPath=info.get("thumbnail") or "Images/app.png",
        JsonRPCAction={
            "method": "download",
            "parameters": [query, f"{format['format_id']}"],
        },
    )
